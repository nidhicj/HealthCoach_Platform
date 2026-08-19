"""Client-facing /api/me/* endpoints. Requires role=client JWT."""
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from src.api.action_items import ActionItemOut
from src.api.check_ins import CheckInOut
from src.api.deps import ClientClaimsDep, DbDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.api.meal_logs import ALLOWED_MEAL_PHOTO_MIME_TYPES, MAX_MEAL_PHOTO_SIZE_BYTES, MealLogOut
from src.api.messages import ALLOWED_ATTACHMENT_MIME_TYPES, MAX_ATTACHMENT_SIZE_BYTES, MessageOut
from src.api.sessions import MomOut
from src.db.models import ActionItem, CheckIn, Client, ClientMessage, MealLog, Mom
from src.lib.exif import extract_capture_time
from src.lib.s3 import build_meal_photo_key, build_message_attachment_key, s3_get, s3_put

router = APIRouter(prefix="/api/me", tags=["me"])


# ── schemas ────────────────────────────────────────────────────────────────────


class CheckInSubmit(BaseModel):
    payload: dict


class ClientActionItemPatch(BaseModel):
    status: str


# ── shared helper ──────────────────────────────────────────────────────────────


async def _resolve_client(db: DbDep, claims: ClientClaimsDep, hc_id: str) -> Client:
    client = (await db.execute(
        select(Client).where(
            Client.user_id == UUID(claims.sub),
            Client.hc_user_id == UUID(hc_id),
        )
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client record not found")
    return client


# ── routes ─────────────────────────────────────────────────────────────────────


@router.post("/check-ins", status_code=status.HTTP_201_CREATED)
async def submit_check_in(
    body: CheckInSubmit,
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> CheckInOut:
    client = await _resolve_client(db, claims, hc_id)

    pending = (await db.execute(
        select(CheckIn).where(
            CheckIn.client_id == client.id,
            CheckIn.requested_at.is_not(None),
            CheckIn.payload.is_(None),
        ).order_by(CheckIn.requested_at).limit(1)
    )).scalars().first()

    if pending is not None:
        pending.payload = body.payload
        ci = pending
    else:
        ci = CheckIn(
            client_id=client.id,
            hc_user_id=UUID(hc_id),
            payload=body.payload,
        )
        db.add(ci)

    await db.flush()
    await db.commit()
    return CheckInOut.model_validate(ci)


@router.get("/check-ins")
async def list_my_check_ins(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[CheckInOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(CheckIn).where(CheckIn.client_id == client.id)

    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                CheckIn.created_at < cur_ts,
                and_(CheckIn.created_at == cur_ts, CheckIn.id < cur_id),
            )
        )

    q = q.order_by(CheckIn.created_at.desc(), CheckIn.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    return PaginatedList(items=[CheckInOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/moms")
async def list_my_moms(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[MomOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(Mom).where(Mom.client_id == client.id, Mom.status == "sent")

    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                Mom.created_at < cur_ts,
                and_(Mom.created_at == cur_ts, Mom.id < cur_id),
            )
        )

    q = q.order_by(Mom.created_at.desc(), Mom.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    return PaginatedList(items=[MomOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/action-items")
async def list_my_action_items(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[ActionItemOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(ActionItem).where(ActionItem.client_id == client.id)

    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                ActionItem.created_at < cur_ts,
                and_(ActionItem.created_at == cur_ts, ActionItem.id < cur_id),
            )
        )

    q = q.order_by(ActionItem.created_at.desc(), ActionItem.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    return PaginatedList(items=[ActionItemOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/moms/{mom_id}")
async def get_my_mom(
    mom_id: UUID,
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MomOut:
    client = await _resolve_client(db, claims, hc_id)
    mom = (await db.execute(
        select(Mom).where(Mom.id == mom_id, Mom.client_id == client.id, Mom.status == "sent")
    )).scalar_one_or_none()
    if mom is None:
        raise HTTPException(status_code=404, detail="MOM not found")
    return MomOut.model_validate(mom)


@router.patch("/action-items/{item_id}")
async def patch_my_action_item(
    item_id: UUID,
    body: ClientActionItemPatch,
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> ActionItemOut:
    client = await _resolve_client(db, claims, hc_id)
    item = (await db.execute(
        select(ActionItem).where(ActionItem.id == item_id, ActionItem.client_id == client.id)
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Action item not found")

    item.status = body.status
    if body.status == "completed":
        item.completed_at = datetime.now(timezone.utc)
    else:
        item.completed_at = None

    await db.flush()
    await db.commit()
    return ActionItemOut.model_validate(item)


@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def submit_my_message(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    body: str = Form(..., min_length=1),
    attachment: UploadFile | None = None,
) -> MessageOut:
    if not body.strip():
        raise HTTPException(status_code=422, detail="Message body cannot be empty or whitespace-only")

    client = await _resolve_client(db, claims, hc_id)

    msg = ClientMessage(client_id=client.id, hc_user_id=UUID(hc_id), direction="client", body=body)

    if attachment is not None:
        if not attachment.content_type or attachment.content_type not in ALLOWED_ATTACHMENT_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type. Allowed: {sorted(ALLOWED_ATTACHMENT_MIME_TYPES)}",
            )
        # Starlette populates .size from the multipart part before the body is
        # read into memory — check it first so a client (untrusted) can't force
        # a large allocation before the size limit is enforced. Keep the
        # post-read check below too as a fallback for any case where .size
        # isn't populated.
        if attachment.size is not None and attachment.size > MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Attachment exceeds the 10 MB limit")
        content = await attachment.read()
        if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Attachment exceeds the 10 MB limit")

        db.add(msg)
        await db.flush()
        key = build_message_attachment_key(client.id, msg.id, attachment.filename or "unnamed")
        await s3_put(key, content, attachment.content_type)
        msg.attachment_storage_path = key
        msg.attachment_original_filename = attachment.filename or "unnamed"
        msg.attachment_mime_type = attachment.content_type
    else:
        db.add(msg)
        await db.flush()

    await db.commit()
    await db.refresh(msg)
    return MessageOut.model_validate(msg)


@router.get("/messages")
async def list_my_messages(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[MessageOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(ClientMessage).where(ClientMessage.client_id == client.id)
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


@router.get("/messages/{message_id}/attachment")
async def get_my_message_attachment(
    message_id: UUID,
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> Response:
    client = await _resolve_client(db, claims, hc_id)
    msg = (await db.execute(
        select(ClientMessage).where(ClientMessage.id == message_id, ClientMessage.client_id == client.id)
    )).scalar_one_or_none()
    if msg is None or msg.attachment_storage_path is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    content = await s3_get(msg.attachment_storage_path)
    # RFC 5987 encoding — see the matching comment in src/api/messages.py's
    # get_client_message_attachment for why a plain filename="{name}" header
    # 500s on non-Latin-1 filenames (Starlette encodes response headers as
    # latin-1, and attachment_original_filename is stored raw/unsanitized).
    filename = msg.attachment_original_filename or "attachment"
    return Response(
        content=content,
        media_type=msg.attachment_mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/meal-logs", status_code=status.HTTP_201_CREATED)
async def submit_my_meal_log(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    meal_slot: str = Form(...),
    description: str | None = Form(None),
    photo: UploadFile = File(...),  # required — D-26, no optional-photo path
) -> MealLogOut:
    client = await _resolve_client(db, claims, hc_id)

    valid_slots = {"breakfast", "morning_snack", "lunch", "evening_snack", "dinner"}
    if meal_slot not in valid_slots:
        raise HTTPException(status_code=422, detail=f"meal_slot must be one of {sorted(valid_slots)}")

    if not photo.content_type or photo.content_type not in ALLOWED_MEAL_PHOTO_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported photo type. Allowed: {sorted(ALLOWED_MEAL_PHOTO_MIME_TYPES)}",
        )
    # Starlette populates .size from the multipart part before the body is
    # read into memory — check it first so a client (untrusted) can't force
    # a large allocation before the size limit is enforced. Keep the
    # post-read check below too as a fallback for any case where .size
    # isn't populated.
    if photo.size is not None and photo.size > MAX_MEAL_PHOTO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Photo exceeds the 10 MB limit")
    content = await photo.read()
    if len(content) > MAX_MEAL_PHOTO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Photo exceeds the 10 MB limit")

    captured_at = extract_capture_time(content, photo.content_type)  # None per Decision 1 if absent/HEIC/corrupt

    # Unlike ClientMessage.attachment_storage_path (nullable — attachments are
    # optional), MealLog.photo_storage_path/photo_original_filename/photo_mime_type
    # are all NOT NULL (a meal log always has a photo, D-26). That rules out the
    # flush-then-set-storage-fields two-phase pattern used for message attachments
    # in submit_my_message: flushing before the photo fields are set would insert
    # a row with those columns NULL and violate the NOT NULL constraint. Instead,
    # generate the id client-side so the storage key is known before the one
    # insert that creates the row with every required field already populated.
    meal_log_id = uuid4()
    key = build_meal_photo_key(client.id, meal_log_id, photo.filename or "unnamed")
    await s3_put(key, content, photo.content_type)

    meal_log = MealLog(
        id=meal_log_id,
        client_id=client.id,
        hc_user_id=UUID(hc_id),
        meal_slot=meal_slot,
        description=description,
        photo_storage_path=key,
        photo_original_filename=photo.filename or "unnamed",
        photo_mime_type=photo.content_type,
        captured_at=captured_at,
    )
    db.add(meal_log)
    await db.commit()
    await db.refresh(meal_log)
    return MealLogOut.model_validate(meal_log)
