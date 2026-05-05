"""HC client management endpoints. All routes scoped to JWT hc_id (tenant)."""
import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, or_, select, text

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.config import get_settings
from src.db.models import ActionItem, CheckIn, Client, ClientInviteToken

router = APIRouter(prefix="/api/clients", tags=["clients"])

_VALID_JOURNEY_STAGES = {"onboarding", "active", "plateau", "off_track", "completed"}
_INVITE_TTL_DAYS = 30  # D-3: confirmed 30 days


# ── schemas ────────────────────────────────────────────────────────────────────


class ClientCreate(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    timezone: str | None = None
    journey_stage: str = "onboarding"
    course_start_date: datetime | None = None
    course_end_date: datetime | None = None
    course_goal: str | None = None

    @field_validator("journey_stage")
    @classmethod
    def _validate_stage(cls, v: str) -> str:
        if v not in _VALID_JOURNEY_STAGES:
            raise ValueError(f"journey_stage must be one of {_VALID_JOURNEY_STAGES}")
        return v


class ClientOut(BaseModel):
    id: UUID
    hc_user_id: UUID
    full_name: str
    code: str | None
    email: str | None
    phone: str | None
    timezone: str | None
    journey_stage: str
    course_start_date: datetime | None
    course_end_date: datetime | None
    course_goal: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientDetailOut(ClientOut):
    ast: None = None  # P3 stub — full AST computation in P5
    open_action_items_count: int = 0
    last_session_at: datetime | None = None


class ActionItemOut(BaseModel):
    id: UUID
    description: str
    due_date: date | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AstOut(BaseModel):
    open_items: list[ActionItemOut]
    missed_items: list[ActionItemOut]
    status_summary: str
    trend_tags: list[str]
    triage_flags: list[str]


class InviteOut(BaseModel):
    invite_token: str
    expires_at: datetime
    invite_url: str


# ── routes ─────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_client(
    body: ClientCreate,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> ClientOut:
    # Compute next CP<NNNN> code for this HC. UNIQUE constraint on (hc_user_id, code)
    # guards against concurrent races at the DB level.
    result = await db.execute(
        text(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(code FROM 3) AS INTEGER)), 0) + 1 "
            "FROM clients WHERE hc_user_id = :hc_id AND code LIKE 'CP%'"
        ),
        {"hc_id": hc_id},
    )
    next_num: int = result.scalar() or 1
    code = f"CP{next_num:04d}"

    client = Client(
        hc_user_id=UUID(hc_id),
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        timezone=body.timezone,
        journey_stage=body.journey_stage,
        course_start_date=body.course_start_date,
        course_end_date=body.course_end_date,
        course_goal=body.course_goal,
        code=code,
    )
    db.add(client)
    await db.flush()
    await db.commit()
    return ClientOut.model_validate(client)


@router.post("/{client_id}/invite", status_code=status.HTTP_201_CREATED)
async def create_invite(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> InviteOut:
    client = await _get_owned_client(db, client_id, hc_id)

    # Invalidate any existing unused tokens for this client
    existing = (await db.execute(
        select(ClientInviteToken).where(
            ClientInviteToken.client_id == client_id,
            ClientInviteToken.used_at.is_(None),
        )
    )).scalars().all()
    for tok in existing:
        tok.used_at = datetime.now(timezone.utc)  # mark consumed

    raw_token = os.urandom(32).hex()
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=_INVITE_TTL_DAYS)

    invite = ClientInviteToken(
        client_id=client.id,
        hc_user_id=UUID(hc_id),
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()
    await db.commit()

    settings = get_settings()
    invite_url = f"{settings.api_base_url}/api/auth/client/start?invite={raw_token}"
    return InviteOut(invite_token=raw_token, expires_at=expires_at, invite_url=invite_url)


@router.get("")
async def list_clients(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
    journey_stage: Annotated[str | None, Query()] = None,
) -> PaginatedList[ClientOut]:
    q = select(Client).where(Client.hc_user_id == UUID(hc_id))

    if journey_stage is not None:
        q = q.where(Client.journey_stage == journey_stage)

    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                Client.created_at < cur_ts,
                and_(Client.created_at == cur_ts, Client.id < cur_id),
            )
        )

    q = q.order_by(Client.created_at.desc(), Client.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    return PaginatedList(items=[ClientOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.get("/{client_id}")
async def get_client(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> ClientDetailOut:
    client = await _get_owned_client(db, client_id, hc_id)
    return ClientDetailOut.model_validate(client)


@router.get("/{client_id}/ast")
async def get_client_ast(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> AstOut:
    await _get_owned_client(db, client_id, hc_id)  # ownership check / 404

    # Open action items
    open_items = (await db.execute(
        select(ActionItem)
        .where(ActionItem.client_id == client_id, ActionItem.status == "open")
        .order_by(ActionItem.created_at.desc())
        .limit(10)
    )).scalars().all()

    # Missed action items
    missed_items = (await db.execute(
        select(ActionItem)
        .where(ActionItem.client_id == client_id, ActionItem.status == "missed")
        .order_by(ActionItem.created_at.desc())
        .limit(10)
    )).scalars().all()

    # Recent check-ins (last 14 days) for status_summary
    cutoff_14d = datetime.now(timezone.utc) - timedelta(days=14)
    recent_checkins = (await db.execute(
        select(CheckIn)
        .where(CheckIn.client_id == client_id, CheckIn.created_at >= cutoff_14d)
        .order_by(CheckIn.created_at.desc())
    )).scalars().all()

    if recent_checkins:
        lines = [f"- {ci.payload.get('note', '(no note)')}" for ci in recent_checkins]
        status_summary = "Recent check-ins:\n" + "\n".join(lines)
    else:
        status_summary = "No recent check-ins."

    # Triage flags
    triage_flags: list[str] = []
    if missed_items:
        triage_flags.append("missed_action_item")
    if not recent_checkins:
        triage_flags.append("no_recent_checkin")

    # manual_sentiment_flag: any check_in with sentiment_flag set in last 30 days
    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)
    sentiment_flagged = (await db.execute(
        select(CheckIn)
        .where(
            CheckIn.client_id == client_id,
            CheckIn.created_at >= cutoff_30d,
            CheckIn.sentiment_flag.isnot(None),
        )
        .limit(1)
    )).scalar_one_or_none()
    if sentiment_flagged is not None:
        triage_flags.append("manual_sentiment_flag")

    return AstOut(
        open_items=[ActionItemOut.model_validate(i) for i in open_items],
        missed_items=[ActionItemOut.model_validate(i) for i in missed_items],
        status_summary=status_summary,
        trend_tags=[],
        triage_flags=triage_flags,
    )


# ── shared helper ──────────────────────────────────────────────────────────────


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    row = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return row
