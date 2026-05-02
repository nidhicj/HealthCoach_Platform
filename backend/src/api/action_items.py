"""Action item endpoints. HC-facing CRUD. All routes scoped to JWT hc_id."""
from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from src.api.deps import DbDep, HcClaimsDep, LimitDep, PaginatedList, TenantDep, decode_cursor, encode_cursor
from src.db.models import ActionItem, Client, Session

router = APIRouter(prefix="/api/action-items", tags=["action-items"])


# ── schemas ────────────────────────────────────────────────────────────────────


class ActionItemCreate(BaseModel):
    client_id: UUID
    session_id: UUID | None = None
    description: str
    due_date: date | None = None  # D-4: manual entry only, no auto-default


class ActionItemPatch(BaseModel):
    status: str | None = None
    due_date: date | None = None


class ActionItemOut(BaseModel):
    id: UUID
    client_id: UUID
    session_id: UUID | None
    hc_user_id: UUID
    description: str
    due_date: date | None
    status: str
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── routes ─────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_action_item(
    body: ActionItemCreate,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> ActionItemOut:
    # Verify client belongs to this HC
    client = (await db.execute(
        select(Client).where(Client.id == body.client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=422, detail="Client not found or not owned by this HC")

    # If session_id provided, verify it belongs to this HC and client
    if body.session_id is not None:
        sess = (await db.execute(
            select(Session).where(
                Session.id == body.session_id,
                Session.hc_user_id == UUID(hc_id),
                Session.client_id == body.client_id,
            )
        )).scalar_one_or_none()
        if sess is None:
            raise HTTPException(status_code=422, detail="Session not found or does not match client/HC")

    item = ActionItem(
        client_id=body.client_id,
        session_id=body.session_id,
        hc_user_id=UUID(hc_id),
        description=body.description,
        due_date=body.due_date,
    )
    db.add(item)
    await db.flush()
    await db.commit()
    return _to_out(item)


@router.get("")
async def list_action_items(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
    client_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> PaginatedList[ActionItemOut]:
    q = select(ActionItem).where(ActionItem.hc_user_id == UUID(hc_id))

    if client_id is not None:
        q = q.where(ActionItem.client_id == client_id)
    if status is not None:
        q = q.where(ActionItem.status == status)

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

    return PaginatedList(items=[_to_out(r) for r in rows], next_cursor=next_cursor)


@router.get("/{item_id}")
async def get_action_item(
    item_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> ActionItemOut:
    item = await _get_owned_item(db, item_id, hc_id)
    return _to_out(item)


@router.patch("/{item_id}")
async def patch_action_item(
    item_id: UUID,
    body: ActionItemPatch,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> ActionItemOut:
    item = await _get_owned_item(db, item_id, hc_id)

    if body.status is not None:
        item.status = body.status
        if body.status == "completed":
            item.completed_at = datetime.now(timezone.utc)
        else:
            item.completed_at = None

    if body.due_date is not None:
        item.due_date = body.due_date  # type: ignore[assignment]

    await db.flush()
    await db.commit()
    return _to_out(item)


# ── helpers ────────────────────────────────────────────────────────────────────


async def _get_owned_item(db: DbDep, item_id: UUID, hc_id: str) -> ActionItem:
    row = (await db.execute(
        select(ActionItem).where(ActionItem.id == item_id, ActionItem.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Action item not found")
    return row


def _to_out(item: ActionItem) -> ActionItemOut:
    return ActionItemOut.model_validate(item)
