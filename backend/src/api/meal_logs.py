"""HC-side meal_logs list/react endpoints. Client-side submit lives in me.py."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.db.models import Client, MealLog

router = APIRouter(tags=["meal-logs"])

ALLOWED_MEAL_PHOTO_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_MEAL_PHOTO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB — matches PHASE-02c's message-attachment cap
VALID_REACTIONS = {"happy", "neutral", "sad"}


# ── schemas ────────────────────────────────────────────────────────────────────


class MealLogOut(BaseModel):
    id: UUID
    client_id: UUID
    hc_user_id: UUID
    meal_slot: str
    description: str | None
    photo_original_filename: str
    photo_mime_type: str
    captured_at: datetime | None
    logged_at: datetime
    hc_reaction: str | None
    reacted_at: datetime | None

    model_config = {"from_attributes": True}


class MealLogReactIn(BaseModel):
    reaction: str


# ── shared helper (this module's own copy — see Global Constraints) ────────────


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/api/clients/{client_id}/meal-logs")
async def list_client_meal_logs(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 40,  # higher default than messages/check-ins — day-grouping wants more per page
    cursor: str | None = None,
) -> PaginatedList[MealLogOut]:
    await _get_owned_client(db, client_id, hc_id)

    q = select(MealLog).where(MealLog.client_id == client_id)
    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                MealLog.logged_at < cur_ts,
                and_(MealLog.logged_at == cur_ts, MealLog.id < cur_id),
            )
        )
    q = q.order_by(MealLog.logged_at.desc(), MealLog.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].logged_at, rows[-1].id)

    return PaginatedList(items=[MealLogOut.model_validate(r) for r in rows], next_cursor=next_cursor)


@router.post("/api/clients/{client_id}/meal-logs/{meal_log_id}/react")
async def react_to_meal_log(
    client_id: UUID,
    meal_log_id: UUID,
    body: MealLogReactIn,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> MealLogOut:
    await _get_owned_client(db, client_id, hc_id)

    if body.reaction not in VALID_REACTIONS:
        raise HTTPException(status_code=422, detail=f"reaction must be one of {sorted(VALID_REACTIONS)}")

    meal_log = (await db.execute(
        select(MealLog).where(MealLog.id == meal_log_id, MealLog.client_id == client_id)
    )).scalar_one_or_none()
    if meal_log is None:
        raise HTTPException(status_code=404, detail="Meal log not found")

    meal_log.hc_reaction = body.reaction
    meal_log.reacted_at = datetime.now(tz=meal_log.logged_at.tzinfo)

    await db.commit()
    await db.refresh(meal_log)
    return MealLogOut.model_validate(meal_log)
