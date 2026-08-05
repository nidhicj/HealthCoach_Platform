"""Integration tests for google_calendar_connections — encrypted credential roundtrip."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import GoogleCalendarConnection, User


@pytest.mark.asyncio
async def test_connection_round_trips_encrypted_credentials(db: AsyncSession, hc_user: User) -> None:
    conn = GoogleCalendarConnection(
        hc_user_id=hc_user.id,
        google_account_email="coach@example.com",
        scope_granted="openid email profile https://www.googleapis.com/auth/calendar.events",
        credentials={"access_token": "at-123", "refresh_token": "rt-456"},
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    assert conn.credentials == {"access_token": "at-123", "refresh_token": "rt-456"}
