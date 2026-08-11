"""Integration tests for Calendar connect/callback OAuth routes (PHASE-01e Task 4).

Google's HTTP responses are never hit for real. Following this repo's established
router-integration-test convention (see test_client_auth.py's use of
`patch("src.auth.router.exchange_code_for_userinfo", new=AsyncMock(...))`), the
calendar_oauth.py functions imported by name into src/auth/router.py are patched
directly at that import site — not mocked at the httpx-transport level (that
transport-level approach is what test_calendar_oauth.py already uses to unit-test
calendar_oauth.py itself; this file tests the router wiring on top of it).
"""
import urllib.parse
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.calendar_oauth import _CALENDAR_SCOPES, GoogleCalendarTokens, MissingRefreshTokenError
from src.db.models import GoogleCalendarConnection, User

_FAKE_TOKENS = GoogleCalendarTokens(
    access_token="cal-at-123",
    refresh_token="cal-rt-456",
    expires_in=3599,
    scope=_CALENDAR_SCOPES,
)


def _query(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    return {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}


async def _get_state(http_client, hc_headers) -> str:
    r = await http_client.get("/api/auth/google/calendar/connect", headers=hc_headers)
    assert r.status_code == 200, r.text
    return _query(r.json()["auth_url"])["state"]


# ── GET /api/auth/google/calendar/connect ─────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_returns_auth_url_with_calendar_scope(http_client, hc_headers):
    r = await http_client.get("/api/auth/google/calendar/connect", headers=hc_headers)
    assert r.status_code == 200, r.text
    params = _query(r.json()["auth_url"])
    assert params["scope"] == _CALENDAR_SCOPES
    assert params["prompt"] == "consent"


@pytest.mark.asyncio
async def test_connect_rejects_client_role(http_client, client_headers):
    r = await http_client.get("/api/auth/google/calendar/connect", headers=client_headers)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_connect_requires_auth(http_client):
    r = await http_client.get("/api/auth/google/calendar/connect")
    assert r.status_code == 401, r.text


# ── GET /api/auth/google/calendar/callback ────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_creates_connection_and_redirects_connected_1(
    http_client, hc_headers, hc_user: User, db: AsyncSession
):
    state = await _get_state(http_client, hc_headers)

    with patch("src.auth.router.exchange_code_for_calendar_tokens", new=AsyncMock(return_value=_FAKE_TOKENS)), \
         patch("src.auth.router.fetch_calendar_account_email", new=AsyncMock(return_value="coach@example.com")):
        r = await http_client.get(
            "/api/auth/google/calendar/callback",
            params={"code": "fake-code", "state": state},
            follow_redirects=False,
        )

    assert r.status_code == 302, r.text
    location = r.headers["location"]
    assert "/settings/calendar" in location
    assert "connected=1" in location

    conn = (await db.execute(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.hc_user_id == hc_user.id)
    )).scalar_one()
    assert conn.google_account_email == "coach@example.com"
    assert conn.scope_granted == _CALENDAR_SCOPES
    assert conn.credentials == {"access_token": "cal-at-123", "refresh_token": "cal-rt-456"}
    assert conn.revoked_at is None


@pytest.mark.asyncio
async def test_callback_invalid_state_returns_400(http_client):
    r = await http_client.get(
        "/api/auth/google/calendar/callback",
        params={"code": "x", "state": "not-a-real-state"},
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_callback_token_exchange_failure_redirects_connected_0(http_client, hc_headers):
    state = await _get_state(http_client, hc_headers)

    with patch(
        "src.auth.router.exchange_code_for_calendar_tokens",
        new=AsyncMock(side_effect=MissingRefreshTokenError("no refresh_token in response")),
    ):
        r = await http_client.get(
            "/api/auth/google/calendar/callback",
            params={"code": "fake-code", "state": state},
            follow_redirects=False,
        )

    assert r.status_code == 302, r.text
    location = r.headers["location"]
    assert "/settings/calendar" in location
    assert "connected=0" in location
    assert "error=" in location


@pytest.mark.asyncio
async def test_callback_second_call_updates_existing_row_not_duplicate(
    http_client, hc_headers, hc_user: User, db: AsyncSession
):
    state1 = await _get_state(http_client, hc_headers)
    with patch("src.auth.router.exchange_code_for_calendar_tokens", new=AsyncMock(return_value=_FAKE_TOKENS)), \
         patch("src.auth.router.fetch_calendar_account_email", new=AsyncMock(return_value="coach@example.com")):
        r1 = await http_client.get(
            "/api/auth/google/calendar/callback",
            params={"code": "fake-code-1", "state": state1},
            follow_redirects=False,
        )
    assert r1.status_code == 302, r1.text

    new_tokens = GoogleCalendarTokens(
        access_token="cal-at-999", refresh_token="cal-rt-999", expires_in=3599, scope=_CALENDAR_SCOPES,
    )
    state2 = await _get_state(http_client, hc_headers)
    with patch("src.auth.router.exchange_code_for_calendar_tokens", new=AsyncMock(return_value=new_tokens)), \
         patch("src.auth.router.fetch_calendar_account_email", new=AsyncMock(return_value="coach2@example.com")):
        r2 = await http_client.get(
            "/api/auth/google/calendar/callback",
            params={"code": "fake-code-2", "state": state2},
            follow_redirects=False,
        )
    assert r2.status_code == 302, r2.text

    rows = (await db.execute(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.hc_user_id == hc_user.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].credentials == {"access_token": "cal-at-999", "refresh_token": "cal-rt-999"}
    assert rows[0].google_account_email == "coach2@example.com"
