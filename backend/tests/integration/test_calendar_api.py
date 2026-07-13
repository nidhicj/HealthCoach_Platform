"""Integration tests for calendar-data endpoints (PHASE-01e Task 5, Task 6).

Distinct from the OAuth-flow routes in src/auth/router.py (tested in
test_calendar_oauth_routes.py) — this file tests the data-facing
GET /api/calendar/status endpoint and the _get_valid_access_token helper
in src/api/calendar.py.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.calendar_oauth import CalendarReauthRequired
from src.db.models import GoogleCalendarConnection, User

_CONNECTED_AT = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
_DEFAULT_EXPIRES_AT = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)


async def _make_connection(
    db: AsyncSession,
    hc_user: User,
    *,
    revoked_at: datetime | None = None,
    access_token_expires_at: datetime = _DEFAULT_EXPIRES_AT,
    credentials: dict | None = None,
) -> GoogleCalendarConnection:
    conn = GoogleCalendarConnection(
        hc_user_id=hc_user.id,
        google_account_email="coach@example.com",
        scope_granted="https://www.googleapis.com/auth/calendar.events",
        credentials=credentials or {"access_token": "at-123", "refresh_token": "rt-456"},
        access_token_expires_at=access_token_expires_at,
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


# ── _get_valid_access_token ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_valid_access_token_raises_not_connected_when_no_row(
    hc_user: User, db: AsyncSession,
):
    from src.api.calendar import _get_valid_access_token

    with pytest.raises(HTTPException) as exc_info:
        await _get_valid_access_token(db, hc_user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "calendar_not_connected"


@pytest.mark.asyncio
async def test_get_valid_access_token_raises_reauth_required_when_revoked(
    hc_user: User, db: AsyncSession,
):
    from src.api.calendar import _get_valid_access_token

    await _make_connection(db, hc_user, revoked_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc))

    with pytest.raises(HTTPException) as exc_info:
        await _get_valid_access_token(db, hc_user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "calendar_reauth_required"


@pytest.mark.asyncio
async def test_get_valid_access_token_returns_existing_token_when_not_expired(
    hc_user: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch,
):
    from src.api import calendar as calendar_module

    async def _fail_if_called(**kwargs):
        raise AssertionError("refresh_calendar_access_token should not be called for a valid token")

    monkeypatch.setattr(calendar_module, "refresh_calendar_access_token", _fail_if_called)

    await _make_connection(
        db, hc_user,
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        credentials={"access_token": "at-still-valid", "refresh_token": "rt-456"},
    )

    token = await calendar_module._get_valid_access_token(db, hc_user.id)

    assert token == "at-still-valid"


@pytest.mark.asyncio
async def test_get_valid_access_token_refreshes_expired_token_and_updates_row(
    hc_user: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch,
):
    from src.api import calendar as calendar_module

    async def _fake_refresh(*, refresh_token, client_id, client_secret):
        assert refresh_token == "rt-456"
        return "at-new-789", 3599

    monkeypatch.setattr(calendar_module, "refresh_calendar_access_token", _fake_refresh)

    conn = await _make_connection(
        db, hc_user,
        access_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        credentials={"access_token": "at-old", "refresh_token": "rt-456"},
    )

    token = await calendar_module._get_valid_access_token(db, hc_user.id)

    assert token == "at-new-789"

    # Force a real reload from the database (expire_on_commit=False means
    # `conn` would otherwise still show the correct value even if the code
    # had only mutated the in-memory dict in place — a plain EncryptedJSON
    # column isn't wrapped in MutableDict, so SQLAlchemy wouldn't detect an
    # in-place mutation and nothing would actually be persisted). This
    # proves the encrypted column round-tripped through the DB.
    await db.refresh(conn)

    assert conn.credentials["access_token"] == "at-new-789"
    assert conn.credentials["refresh_token"] == "rt-456"
    assert conn.access_token_expires_at > datetime.now(timezone.utc) + timedelta(minutes=50)


@pytest.mark.asyncio
async def test_get_valid_access_token_marks_revoked_on_failed_refresh(
    hc_user: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch,
):
    from src.api import calendar as calendar_module

    async def _fake_refresh_fails(*, refresh_token, client_id, client_secret):
        raise CalendarReauthRequired("Google rejected the refresh_token")

    monkeypatch.setattr(calendar_module, "refresh_calendar_access_token", _fake_refresh_fails)

    conn = await _make_connection(
        db, hc_user,
        access_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    with pytest.raises(HTTPException) as exc_info:
        await calendar_module._get_valid_access_token(db, hc_user.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "calendar_reauth_required"
    assert conn.revoked_at is not None


@pytest.mark.asyncio
async def test_get_valid_access_token_logs_and_reraises_on_unexpected_refresh_error(
    hc_user: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
):
    """A non-CalendarReauthRequired failure (Google 5xx, timeout, malformed
    response, etc.) must still emit the google_calendar_api_call log line and
    must propagate the original exception unchanged (not be swallowed)."""
    from src.api import calendar as calendar_module

    async def _fake_refresh_raises_unexpected(*, refresh_token, client_id, client_secret):
        raise RuntimeError("boom: simulated Google 5xx / malformed response")

    monkeypatch.setattr(calendar_module, "refresh_calendar_access_token", _fake_refresh_raises_unexpected)

    await _make_connection(
        db, hc_user,
        access_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    with pytest.raises(RuntimeError, match="boom"):
        await calendar_module._get_valid_access_token(db, hc_user.id)

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines() if line]
    matches = [line for line in lines if line["event"] == "google_calendar_api_call"]
    assert len(matches) == 1
    assert matches[0]["extra"]["operation"] == "get_valid_access_token"
    assert matches[0]["extra"]["hc_id"] == str(hc_user.id)
    assert matches[0]["extra"]["outcome"] == "error"
    assert "latency_ms" in matches[0]["extra"]


@pytest.mark.asyncio
async def test_get_valid_access_token_emits_log_line(
    hc_user: User, db: AsyncSession, capsys: pytest.CaptureFixture[str],
):
    from src.api.calendar import _get_valid_access_token

    with pytest.raises(HTTPException):
        await _get_valid_access_token(db, hc_user.id)

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines() if line]
    matches = [line for line in lines if line["event"] == "google_calendar_api_call"]
    assert len(matches) == 1
    assert matches[0]["extra"]["operation"] == "get_valid_access_token"
    assert matches[0]["extra"]["hc_id"] == str(hc_user.id)
    assert matches[0]["extra"]["outcome"] == "calendar_not_connected"
    assert "latency_ms" in matches[0]["extra"]
