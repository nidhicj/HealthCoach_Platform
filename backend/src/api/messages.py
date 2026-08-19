"""HC-side client_messages endpoints. Client-side counterpart lives in me.py."""
from datetime import datetime
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, computed_field
from sqlalchemy import and_, or_, select

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.config import get_settings
from src.db.models import Client, ClientMessage, User
from src.lib.email import send_message_notification_email
from src.lib.s3 import build_message_attachment_key, s3_get, s3_put
from src.telemetry.log import get_logger

router = APIRouter(tags=["messages"])

ALLOWED_ATTACHMENT_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ── schemas ────────────────────────────────────────────────────────────────────


class MessageOut(BaseModel):
    id: UUID
    client_id: UUID
    hc_user_id: UUID
    direction: str
    body: str
    attachment_original_filename: str | None
    attachment_mime_type: str | None
    sent_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def has_attachment(self) -> bool:
        return self.attachment_original_filename is not None


# ── shared helper (this module's own copy — see Global Constraints) ────────────


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


async def _get_hc_display_name(db: DbDep, hc_id: str) -> str:
    """Best-effort coach display name for client-facing emails. display_name is
    nullable (set from Google profile at signup), so fall back to a generic label
    rather than ever exposing the HC's internal user id."""
    hc_user = (await db.execute(select(User).where(User.id == UUID(hc_id)))).scalar_one_or_none()
    if hc_user is not None and hc_user.display_name:
        return hc_user.display_name
    return "Your coach"


# ── routes ─────────────────────────────────────────────────────────────────────


@router.post("/api/clients/{client_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_client_message(
    client_id: UUID,
    request: Request,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    body: str = Form(..., min_length=1),
    attachment: UploadFile | None = None,
) -> MessageOut:
    if not body.strip():
        raise HTTPException(status_code=422, detail="Message body cannot be empty or whitespace-only")

    client = await _get_owned_client(db, client_id, hc_id)

    msg = ClientMessage(client_id=client_id, hc_user_id=UUID(hc_id), direction="coach", body=body)

    if attachment is not None:
        if not attachment.content_type or attachment.content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type. Allowed: {sorted(ALLOWED_ATTACHMENT_MIME_TYPES)}",
            )
        # Starlette populates .size from the multipart part before the body is
        # read into memory — check it first so an oversized upload is rejected
        # without forcing a full read/allocation. Keep the post-read check below
        # too as a fallback for any case where .size isn't populated.
        if attachment.size is not None and attachment.size > MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Attachment exceeds the 10 MB limit")
        content = await attachment.read()
        if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Attachment exceeds the 10 MB limit")

        db.add(msg)
        await db.flush()  # need msg.id for the storage key
        key = build_message_attachment_key(client_id, msg.id, attachment.filename or "unnamed")
        await s3_put(key, content, attachment.content_type)
        msg.attachment_storage_path = key
        msg.attachment_original_filename = attachment.filename or "unnamed"
        msg.attachment_mime_type = attachment.content_type
    else:
        db.add(msg)
        await db.flush()

    await db.commit()
    await db.refresh(msg)

    # Notify the client the HC replied. The DB write above is already durable,
    # so a missing API key or a transient Resend outage must not turn a
    # successful send into an error response — messages are immutable once
    # sent (D-25, no PATCH/DELETE), so a client-side retry on a 500 here would
    # create a permanent duplicate message with no way to clean it up.
    if client.email:
        coach_name = await _get_hc_display_name(db, hc_id)
        logger = get_logger(request_id=getattr(request.state, "request_id", ""), hc_id=hc_id)
        try:
            send_message_notification_email(
                to=client.email,
                client_name=client.full_name,
                coach_name=coach_name,
                preview=body[:200],
                portal_url=f"{get_settings().frontend_url}/me/chat",
            )
        except Exception:
            logger.error("message_notification_email_failed", client_id=str(client_id))

    return MessageOut.model_validate(msg)


@router.get("/api/clients/{client_id}/messages")
async def list_client_messages(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: str | None = None,
) -> PaginatedList[MessageOut]:
    await _get_owned_client(db, client_id, hc_id)

    q = select(ClientMessage).where(ClientMessage.client_id == client_id)
    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                ClientMessage.sent_at < cur_ts,
                and_(ClientMessage.sent_at == cur_ts, ClientMessage.id < cur_id),
            )
        )
    q = q.order_by(ClientMessage.sent_at.desc(), ClientMessage.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].sent_at, rows[-1].id)

    return PaginatedList(items=[MessageOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/api/clients/{client_id}/messages/{message_id}/attachment")
async def get_client_message_attachment(
    client_id: UUID,
    message_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> Response:
    await _get_owned_client(db, client_id, hc_id)
    msg = (await db.execute(
        select(ClientMessage).where(ClientMessage.id == message_id, ClientMessage.client_id == client_id)
    )).scalar_one_or_none()
    if msg is None or msg.attachment_storage_path is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    content = await s3_get(msg.attachment_storage_path)
    # RFC 5987 encoding: attachment_original_filename is stored raw/unsanitized
    # (only the S3 key goes through _sanitize()), and Starlette encodes response
    # headers as latin-1 — a plain `filename="{name}"` header raises
    # UnicodeEncodeError and 500s this endpoint for any non-Latin-1 filename
    # (e.g. Devanagari characters, common for phone-camera uploads).
    filename = msg.attachment_original_filename or "attachment"
    return Response(
        content=content,
        media_type=msg.attachment_mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}"},
    )
