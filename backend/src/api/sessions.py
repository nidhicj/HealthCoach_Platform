"""HC session management endpoints, including MOMs and brief. All routes tenant-scoped."""
from datetime import datetime, timezone
from datetime import date as date_type
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.db.models import ActionItem, Brief, Client, ClientFile, Mom, Session
from src.lib.email import send_action_items_email
from src.lib.s3 import _get_session_date_ist, build_session_file_key, s3_put
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ── schemas ────────────────────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    client_id: UUID
    session_number: int
    scheduled_at: datetime
    zoom_meeting_id: str | None = None
    notes_internal: str | None = None


class SessionOut(BaseModel):
    id: UUID
    hc_user_id: UUID
    client_id: UUID
    session_number: int
    scheduled_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    zoom_meeting_id: str | None
    notes_internal: str | None
    session_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionPatch(BaseModel):
    notes_internal: str | None = None
    session_notes: str | None = None


class MomCreate(BaseModel):
    draft_text: str


class MomDraftRequest(BaseModel):
    session_notes: str


class MomPatch(BaseModel):
    draft_text: str | None = None
    final_text: str | None = None
    action_items_draft: list[dict] | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _no_sent_via_patch(cls, v: str | None) -> str | None:
        if v == "sent":
            raise ValueError("Use POST /mom/send to transition to 'sent' status")
        return v


class MomSendRequest(BaseModel):
    message: str


class MomOut(BaseModel):
    id: UUID
    session_id: UUID
    client_id: UUID
    draft_text: str
    final_text: str | None
    action_items_draft: list[dict] | None
    status: str
    llm_call_id: UUID | None = None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BriefOut(BaseModel):
    id: UUID
    session_id: UUID
    client_id: UUID
    brief_text: str
    triage_flags: list[str] | None
    llm_call_id: UUID | None = None
    generated_at: datetime

    model_config = {"from_attributes": True}


# ── session routes ─────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> SessionOut:
    # Verify client belongs to this HC
    client = (await db.execute(
        select(Client).where(Client.id == body.client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=422, detail="Client not found or does not belong to this HC")

    session = Session(
        hc_user_id=UUID(hc_id),
        client_id=body.client_id,
        session_number=body.session_number,
        scheduled_at=body.scheduled_at,
        zoom_meeting_id=body.zoom_meeting_id,
        notes_internal=body.notes_internal,
    )
    db.add(session)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Session number already exists for this client")
    await db.commit()
    return SessionOut.model_validate(session)


@router.get("")
async def list_sessions(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
    client_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedList[SessionOut]:
    q = select(Session).where(Session.hc_user_id == UUID(hc_id), Session.deleted_at.is_(None))

    if client_id is not None:
        q = q.where(Session.client_id == client_id)

    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                Session.created_at < cur_ts,
                and_(Session.created_at == cur_ts, Session.id < cur_id),
            )
        )

    q = q.order_by(Session.created_at.desc(), Session.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)

    return PaginatedList(items=[SessionOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> SessionOut:
    sess = await _get_owned_session(db, session_id, hc_id)
    return SessionOut.model_validate(sess)


@router.post("/{session_id}/end")
async def end_session(
    session_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> SessionOut:
    sess = await _get_owned_session(db, session_id, hc_id)
    if sess.ended_at is None:
        sess.ended_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()
    return SessionOut.model_validate(sess)


@router.patch("/{session_id}")
async def patch_session(
    session_id: UUID,
    body: SessionPatch,
    request: Request,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> SessionOut:
    logger = get_logger(request_id=getattr(request.state, "request_id", ""), hc_id=hc_id)
    sess = await _get_owned_session(db, session_id, hc_id)
    if body.notes_internal is not None:
        sess.notes_internal = body.notes_internal
    if body.session_notes is not None:
        sess.session_notes = body.session_notes
    await db.flush()
    await db.commit()

    # Mirror session_notes to S3 after successful DB commit (S3 is read-only mirror; DB is canonical)
    if body.session_notes is not None:
        client = (await db.execute(
            select(Client).where(Client.id == sess.client_id)
        )).scalar_one_or_none()
        if client is not None and client.code is not None:
            key = build_session_file_key(
                hc_user_id=UUID(hc_id),
                client_code=client.code,
                client_full_name=client.full_name,
                session_date=_get_session_date_ist(sess.scheduled_at),
                session_number=sess.session_number,
                filename="session_notes.txt",
            )
            try:
                await s3_put(key, sess.session_notes.encode("utf-8"), "text/plain")
            except Exception as exc:
                logger.warn("session_notes_s3_mirror_failed", session_id=str(session_id), error=str(exc))

    return SessionOut.model_validate(sess)


@router.get("/{session_id}/brief")
async def get_brief(
    session_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> BriefOut:
    sess = await _get_owned_session(db, session_id, hc_id)

    brief = (await db.execute(
        select(Brief).where(Brief.session_id == session_id)
    )).scalar_one_or_none()

    if brief is not None:
        return BriefOut.model_validate(brief)

    from src.llm_service import generate_brief
    brief_text, triage_flags, llm_call_id = await generate_brief(
        db,
        session_id=session_id,
        hc_user_id=UUID(hc_id),
        client_id=sess.client_id,
    )

    brief = Brief(
        session_id=session_id,
        hc_user_id=UUID(hc_id),
        client_id=sess.client_id,
        brief_text=brief_text,
        triage_flags=triage_flags or [],
        llm_call_id=llm_call_id,
    )
    db.add(brief)
    await db.flush()
    await db.commit()
    return BriefOut.model_validate(brief)


@router.post("/{session_id}/brief")
async def regenerate_brief(
    session_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> BriefOut:
    sess = await _get_owned_session(db, session_id, hc_id)

    existing = (await db.execute(
        select(Brief).where(Brief.session_id == session_id)
    )).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.flush()

    from src.llm_service import generate_brief
    brief_text, triage_flags, llm_call_id = await generate_brief(
        db,
        session_id=session_id,
        hc_user_id=UUID(hc_id),
        client_id=sess.client_id,
    )

    brief = Brief(
        session_id=session_id,
        hc_user_id=UUID(hc_id),
        client_id=sess.client_id,
        brief_text=brief_text,
        triage_flags=triage_flags or [],
        llm_call_id=llm_call_id,
    )
    db.add(brief)
    await db.flush()
    await db.commit()
    return BriefOut.model_validate(brief)


# ── MOM routes ─────────────────────────────────────────────────────────────────


@router.post("/{session_id}/mom/draft")
async def draft_mom(
    session_id: UUID,
    body: MomDraftRequest,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MomOut:
    sess = await _get_owned_session(db, session_id, hc_id)

    # Persist session_notes to DB before LLM call — protects notes against timeout loss
    sess.session_notes = body.session_notes
    await db.flush()

    from src.llm_service import generate_mom_draft
    draft_text, action_items, llm_call_id = await generate_mom_draft(
        db,
        session_id=session_id,
        hc_user_id=UUID(hc_id),
        client_id=sess.client_id,
        session_notes=body.session_notes,
    )

    existing = (await db.execute(
        select(Mom).where(Mom.session_id == session_id)
    )).scalar_one_or_none()

    if existing is None:
        mom = Mom(
            session_id=session_id,
            hc_user_id=UUID(hc_id),
            client_id=sess.client_id,
            draft_text=draft_text,
            action_items_draft=action_items,
            llm_call_id=llm_call_id,
        )
        db.add(mom)
    else:
        existing.draft_text = draft_text
        existing.action_items_draft = action_items
        existing.llm_call_id = llm_call_id
        existing.final_text = None
        existing.status = "draft"
        existing.updated_at = datetime.now(timezone.utc)
        mom = existing

    await db.flush()
    await db.commit()
    return MomOut.model_validate(mom)


@router.post("/{session_id}/mom", status_code=status.HTTP_201_CREATED)
async def create_mom(
    session_id: UUID,
    body: MomCreate,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MomOut:
    sess = await _get_owned_session(db, session_id, hc_id)

    existing = (await db.execute(
        select(Mom).where(Mom.session_id == session_id)
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="MOM already exists for this session")

    mom = Mom(
        session_id=session_id,
        hc_user_id=UUID(hc_id),
        client_id=sess.client_id,
        draft_text=body.draft_text,
    )
    db.add(mom)
    await db.flush()
    await db.commit()
    return MomOut.model_validate(mom)


@router.get("/{session_id}/mom")
async def get_mom(
    session_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MomOut:
    await _get_owned_session(db, session_id, hc_id)  # ownership check
    mom = (await db.execute(
        select(Mom).where(Mom.session_id == session_id)
    )).scalar_one_or_none()
    if mom is None:
        raise HTTPException(status_code=404, detail="MOM not found")
    return MomOut.model_validate(mom)


@router.patch("/{session_id}/mom")
async def patch_mom(
    session_id: UUID,
    body: MomPatch,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MomOut:
    await _get_owned_session(db, session_id, hc_id)
    mom = await _get_session_mom(db, session_id)

    if body.draft_text is not None:
        mom.draft_text = body.draft_text

    if body.final_text is not None:
        # Snippet capture gate: only when MOM was AI-generated and text actually changed
        # and the session had no Zoom summary file (Zoom output is not HC voice)
        if mom.llm_call_id is not None and body.final_text != mom.draft_text:
            zoom_file_exists = (await db.execute(
                select(ClientFile.id)
                .where(ClientFile.session_id == session_id, ClientFile.is_zoom_summary == True)  # noqa: E712
                .limit(1)
            )).scalar_one_or_none()
            if not zoom_file_exists:
                from src.llm_service.snippets import capture
                await capture(
                    db,
                    original_text=mom.draft_text,
                    hc_modified_text=body.final_text,
                    hc_user_id=UUID(hc_id),
                    client_id=mom.client_id,
                )
        mom.final_text = body.final_text

    if body.action_items_draft is not None:
        mom.action_items_draft = body.action_items_draft

    if body.status is not None:
        mom.status = body.status

    mom.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    return MomOut.model_validate(mom)


@router.post("/{session_id}/mom/freeze")
async def freeze_mom(
    session_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MomOut:
    sess = await _get_owned_session(db, session_id, hc_id)
    mom = await _get_session_mom(db, session_id)

    if mom.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MOM must be in draft status to freeze",
        )

    draft_items = mom.action_items_draft or []

    # Validate every item before creating any rows — a bad item anywhere in the
    # list must reject the whole freeze, not partially apply it.
    parsed_items: list[tuple[str, date_type | None]] = []
    for idx, item in enumerate(draft_items):
        raw_description = item.get("description") if isinstance(item, dict) else None
        description = (raw_description or "").strip()
        if not description:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Action item at index {idx} has a missing or empty description",
            )

        raw_due_date = item.get("due_date") if isinstance(item, dict) else None
        due_date: date_type | None = None
        if raw_due_date:
            try:
                due_date = date_type.fromisoformat(raw_due_date)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Action item at index {idx} ('{description}') has an "
                        f"invalid due_date: {raw_due_date!r}"
                    ),
                )

        parsed_items.append((description, due_date))

    for description, due_date in parsed_items:
        db.add(ActionItem(
            session_id=session_id,
            client_id=sess.client_id,
            hc_user_id=UUID(hc_id),
            description=description,
            due_date=due_date,
        ))

    mom.status = "reviewed"
    mom.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    return MomOut.model_validate(mom)


@router.post("/{session_id}/mom/send")
async def send_mom(
    session_id: UUID,
    body: MomSendRequest,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MomOut:
    sess = await _get_owned_session(db, session_id, hc_id)
    mom = await _get_session_mom(db, session_id)

    if mom.status == "sent":
        return MomOut.model_validate(mom)

    if mom.status != "reviewed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MOM must be frozen (reviewed) before it can be sent",
        )

    client = (await db.execute(
        select(Client).where(Client.id == sess.client_id)
    )).scalar_one_or_none()
    if client is None or not client.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client has no email address on record. Add one in the client settings before sending.",
        )

    action_items = (await db.execute(
        select(ActionItem).where(ActionItem.session_id == session_id)
    )).scalars().all()

    from src.db.models import User
    hc = (await db.execute(
        select(User).where(User.id == UUID(hc_id))
    )).scalar_one_or_none()
    coach_name = hc.display_name if (hc and hc.display_name) else "Your coach"

    session_date = sess.scheduled_at.strftime("%-d %B %Y")

    send_action_items_email(
        to=client.email,
        coach_name=coach_name,
        client_name=client.full_name,
        session_date=session_date,
        action_items=[
            {"description": item.description, "due_date": item.due_date.isoformat() if item.due_date else None}
            for item in action_items
        ],
        message=body.message,
    )

    mom.status = "sent"
    mom.sent_at = datetime.now(timezone.utc)
    mom.sent_to_email = client.email
    mom.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    return MomOut.model_validate(mom)


# ── shared helpers ─────────────────────────────────────────────────────────────


async def _get_owned_session(db: DbDep, session_id: UUID, hc_id: str) -> Session:
    row = (await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.hc_user_id == UUID(hc_id),
            Session.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


async def _get_session_mom(db: DbDep, session_id: UUID) -> Mom:
    mom = (await db.execute(
        select(Mom).where(Mom.session_id == session_id)
    )).scalar_one_or_none()
    if mom is None:
        raise HTTPException(status_code=404, detail="MOM not found")
    return mom
