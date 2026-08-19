"""HC-side client_messages endpoints. Client-side counterpart lives in me.py."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, computed_field
from sqlalchemy import and_, or_, select

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.config import get_settings
from src.db.models import Client, ClientMessage, User
from src.lib.email import send_message_notification_email
from src.lib.s3 import build_message_attachment_key, s3_get, s3_put

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

    if client.email:
        coach_name = await _get_hc_display_name(db, hc_id)
        send_message_notification_email(
            to=client.email,
            client_name=client.full_name,
            coach_name=coach_name,
            preview=body[:200],
            portal_url=f"{get_settings().frontend_url}/me/chat",
        )

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
    return Response(
        content=content,
        media_type=msg.attachment_mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{msg.attachment_original_filename}"'},
    )
