"""Client-facing /api/me/* endpoints. Requires role=client JWT."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from src.api.action_items import ActionItemOut
from src.api.check_ins import CheckInOut
from src.api.deps import ClientClaimsDep, DbDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.api.sessions import MomOut
from src.db.models import ActionItem, CheckIn, Client, Mom

router = APIRouter(prefix="/api/me", tags=["me"])


# ── schemas ────────────────────────────────────────────────────────────────────


class CheckInSubmit(BaseModel):
    payload: dict


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
    ci = CheckIn(
        client_id=client.id,
        hc_user_id=UUID(hc_id),
        payload=body.payload,
    )
    db.add(ci)
    await db.flush()
    await db.commit()
    return CheckInOut.model_validate(ci)


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
