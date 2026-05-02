"""Check-in endpoints. HC reads/flags; client submission lives in src/api/me.py."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.db.models import CheckIn, Client

router = APIRouter(tags=["check-ins"])


# ── schemas ────────────────────────────────────────────────────────────────────


class CheckInOut(BaseModel):
    id: UUID
    client_id: UUID
    hc_user_id: UUID
    payload: dict
    sentiment_flag: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckInFlagPatch(BaseModel):
    sentiment_flag: str | None = None


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/api/clients/{client_id}/check-ins")
async def list_client_check_ins(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: str | None = None,
) -> PaginatedList[CheckInOut]:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    q = select(CheckIn).where(CheckIn.client_id == client_id)

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


@router.patch("/api/check-ins/{check_in_id}/flag")
async def flag_check_in(
    check_in_id: UUID,
    body: CheckInFlagPatch,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> CheckInOut:
    ci = (await db.execute(
        select(CheckIn).where(CheckIn.id == check_in_id, CheckIn.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if ci is None:
        raise HTTPException(status_code=404, detail="Check-in not found")

    if "sentiment_flag" in body.model_fields_set:
        ci.sentiment_flag = body.sentiment_flag

    await db.flush()
    await db.commit()
    return CheckInOut.model_validate(ci)
