"""HC file upload/list/delete endpoints. All routes tenant-scoped (hc_user_id)."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models import Client, ClientFile, Session
from src.lib.s3 import _get_session_date_ist, build_session_file_key, s3_delete, s3_put
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/sessions", tags=["files"])

ALLOWED_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


# ── schema ─────────────────────────────────────────────────────────────────────


class ClientFileOut(BaseModel):
    id: UUID
    session_id: UUID
    original_filename: str
    storage_path: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime
    is_zoom_summary: bool

    model_config = {"from_attributes": True}


# ── helpers ────────────────────────────────────────────────────────────────────


async def _get_owned_session(db: DbDep, session_id: UUID, hc_id: str) -> Session:
    row = (await db.execute(
        select(Session).where(Session.id == session_id, Session.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


# ── routes ─────────────────────────────────────────────────────────────────────


@router.post("/{session_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_files(
    session_id: UUID,
    files: list[UploadFile],
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    request: Request,
    is_zoom_summary: bool = Form(False),
) -> list[ClientFileOut]:
    logger = get_logger(request_id=getattr(request.state, "request_id", ""))

    session = await _get_owned_session(db, session_id, hc_id)

    client = (await db.execute(
        select(Client).where(Client.id == session.client_id)
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    session_date = _get_session_date_ist(session.scheduled_at)

    created_files: list[ClientFile] = []

    for file in files:
        # Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{file.content_type}'. Allowed: {sorted(ALLOWED_MIME_TYPES)}",
            )

        content = await file.read()

        # Validate size
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' exceeds the 25 MB limit ({len(content)} bytes)",
            )

        # Auto-detect Zoom summary
        zoom = is_zoom_summary or (file.filename or "").startswith("zoom_ai_summary_")

        # Build S3 key and upload
        key = build_session_file_key(
            UUID(hc_id),
            client.code,
            client.full_name,
            session_date,
            session.session_number,
            file.filename or "unnamed",
        )
        await s3_put(key, content, file.content_type)
        logger.info("s3_upload_ok", extra={"key": key, "size_bytes": len(content)})

        cf = ClientFile(
            session_id=session_id,
            hc_user_id=UUID(hc_id),
            client_id=session.client_id,
            original_filename=file.filename or "unnamed",
            storage_path=key,
            mime_type=file.content_type,
            size_bytes=len(content),
            is_zoom_summary=zoom,
        )
        db.add(cf)
        created_files.append(cf)

    await db.commit()

    # Refresh all created rows to populate server-side defaults (id, uploaded_at)
    for cf in created_files:
        await db.refresh(cf)

    return [ClientFileOut.model_validate(cf) for cf in created_files]


@router.get("/{session_id}/files")
async def list_files(
    session_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> list[ClientFileOut]:
    await _get_owned_session(db, session_id, hc_id)

    rows = (await db.execute(
        select(ClientFile).where(
            ClientFile.session_id == session_id,
            ClientFile.hc_user_id == UUID(hc_id),
        )
    )).scalars().all()

    return [ClientFileOut.model_validate(r) for r in rows]


@router.delete("/{session_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    session_id: UUID,
    file_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    request: Request,
) -> None:
    logger = get_logger(request_id=getattr(request.state, "request_id", ""))

    await _get_owned_session(db, session_id, hc_id)

    cf = (await db.execute(
        select(ClientFile).where(
            ClientFile.id == file_id,
            ClientFile.hc_user_id == UUID(hc_id),
            ClientFile.session_id == session_id,
        )
    )).scalar_one_or_none()
    if cf is None:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        await s3_delete(cf.storage_path)
    except Exception as exc:
        logger.warning("s3_delete_failed", extra={"key": cf.storage_path, "error": str(exc)})

    await db.delete(cf)
    await db.commit()
