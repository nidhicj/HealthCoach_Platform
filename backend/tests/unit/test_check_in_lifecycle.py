import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api._check_in_lifecycle import get_or_create_pending_check_in
from src.db.models import CheckIn


@pytest.mark.asyncio
async def test_creates_pending_row_when_none_exists():
    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    client_id, hc_id = uuid.uuid4(), uuid.uuid4()

    row, created = await get_or_create_pending_check_in(db, client_id, hc_id)

    assert created is True
    assert row.client_id == client_id
    assert row.hc_user_id == hc_id
    assert row.payload is None
    assert row.requested_at is not None
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_returns_existing_pending_row_without_creating_new_one():
    existing = CheckIn(
        id=uuid.uuid4(), client_id=uuid.uuid4(), hc_user_id=uuid.uuid4(),
        payload=None, requested_at=datetime.now(timezone.utc),
    )
    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = existing

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    row, created = await get_or_create_pending_check_in(db, existing.client_id, existing.hc_user_id)

    assert created is False
    assert row is existing
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_gracefully_handles_multiple_pending_rows_by_returning_oldest():
    """Regression test: if multiple pending rows exist for the same client
    (race condition upstream), the function should gracefully return the
    oldest one (by requested_at) instead of crashing with MultipleResultsFound.
    """
    client_id = uuid.uuid4()
    hc_id = uuid.uuid4()

    # Create two pending rows with different requested_at times
    older = CheckIn(
        id=uuid.uuid4(), client_id=client_id, hc_user_id=hc_id,
        payload=None, requested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = CheckIn(
        id=uuid.uuid4(), client_id=client_id, hc_user_id=hc_id,
        payload=None, requested_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    result_mock = MagicMock()
    # Simulate query returning oldest row when .limit(1) and .scalars().first() are used
    result_mock.scalars.return_value.first.return_value = older

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    row, created = await get_or_create_pending_check_in(db, client_id, hc_id)

    # Should return the oldest one and not create a new row
    assert created is False
    assert row is older
    db.add.assert_not_called()
