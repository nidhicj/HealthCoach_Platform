"""Shared HC-request/client-answer check-in lifecycle helper. Used by both
check_ins.py (HC-side request) and me.py (client-side submit + Saturday
cron in scheduler.py). Split out to avoid check_ins.py <-> me.py importing
each other directly.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CheckIn


async def get_or_create_pending_check_in(
    db: AsyncSession, client_id: UUID, hc_user_id: UUID,
) -> tuple[CheckIn, bool]:
    """Return (row, created). A pending row is requested_at IS NOT NULL AND
    payload IS NULL. If one already exists for this client, return it
    unchanged (created=False) rather than creating a second one.
    """
    existing = (await db.execute(
        select(CheckIn).where(
            CheckIn.client_id == client_id,
            CheckIn.requested_at.is_not(None),
            CheckIn.payload.is_(None),
        ).order_by(CheckIn.requested_at).limit(1)
    )).scalars().first()
    if existing is not None:
        return existing, False

    row = CheckIn(
        client_id=client_id,
        hc_user_id=hc_user_id,
        payload=None,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row, True
