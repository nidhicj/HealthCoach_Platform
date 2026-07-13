"""Integration tests for calendar-data endpoints (PHASE-01e Task 5).

Distinct from the OAuth-flow routes in src/auth/router.py (tested in
test_calendar_oauth_routes.py) — this file tests the data-facing
GET /api/calendar/status endpoint in src/api/calendar.py.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import GoogleCalendarConnection, User

_CONNECTED_AT = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)


async def _make_connection(
    db: AsyncSession,
    hc_user: User,
    *,
    revoked_at: datetime | None = None,
) -> GoogleCalendarConnection:
    conn = GoogleCalendarConnection(
        hc_user_id=hc_user.id,
        google_account_email="coach@example.com",
        scope_granted="https://www.googleapis.com/auth/calendar.events",
        credentials={"access_token": "at-123", "refresh_token": "rt-456"},
        access_token_expires_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        connected_at=_CONNECTED_AT,
        revoked_at=revoked_at,
    )
    db.add(conn)
    await db.flush()
    return conn


# ── GET /api/calendar/status ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_not_connected(http_client, hc_headers):
    r = await http_client.get("/api/calendar/status", headers=hc_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "connected": False,
        "google_account_email": None,
        "connected_at": None,
        "needs_reauth": False,
    }


@pytest.mark.asyncio
async def test_status_connected(http_client, hc_headers, hc_user: User, db: AsyncSession):
    await _make_connection(db, hc_user)

    r = await http_client.get("/api/calendar/status", headers=hc_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] is True
    assert body["google_account_email"] == "coach@example.com"
    assert body["connected_at"] is not None
    assert body["needs_reauth"] is False


@pytest.mark.asyncio
async def test_status_needs_reauth_when_revoked(http_client, hc_headers, hc_user: User, db: AsyncSession):
    await _make_connection(db, hc_user, revoked_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc))

    r = await http_client.get("/api/calendar/status", headers=hc_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] is True
    assert body["needs_reauth"] is True
    assert body["google_account_email"] == "coach@example.com"
