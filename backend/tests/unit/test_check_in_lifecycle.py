import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api._check_in_lifecycle import get_or_create_pending_check_in
from src.db.models import CheckIn


@pytest.mark.asyncio
async def test_creates_pending_row_when_none_exists():
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)

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
    result_mock.scalar_one_or_none = MagicMock(return_value=existing)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    row, created = await get_or_create_pending_check_in(db, existing.client_id, existing.hc_user_id)

    assert created is False
    assert row is existing
    db.add.assert_not_called()
