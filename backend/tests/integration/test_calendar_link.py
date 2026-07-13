"""Integration tests for POST /api/sessions/{session_id}/calendar-link (PHASE-01e Task 15).

Distinct from test_calendar_api.py (GET /api/calendar/events, Task 7 — read-only
proxy for a time-range list of events) and test_sessions.py (general session
CRUD) — this file tests the endpoint that lets an HC attach a specific Google
Calendar event (and its Meet link) to a session. The event is re-fetched
server-side via the calling HC's own token rather than trusting any
client-supplied event data, per this file's own single-event `events.get`
proxy in src/api/calendar.py's `_fetch_calendar_event`.

Per test_calendar_api.py's established convention, Google's HTTP responses
are mocked via httpx.MockTransport at the make_http_client() factory
boundary — no real network, no respx dependency.
"""
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import GoogleCalendarConnection, User

_GOOGLE_EVENT_WITH_MEET = {
    "id": "evt-meet-1",
    "summary": "1:1 with Priya",
    "start": {"dateTime": "2026-07-13T09:00:00+05:30", "timeZone": "Asia/Kolkata"},
    "end": {"dateTime": "2026-07-13T09:30:00+05:30", "timeZone": "Asia/Kolkata"},
    "hangoutLink": "https://meet.google.com/abc-defg-hij",
    "htmlLink": "https://calendar.google.com/event?eid=evt-meet-1",
}

_GOOGLE_EVENT_NO_MEET = {
    "id": "evt-no-meet-1",
    "summary": "Plain call",
    "start": {"dateTime": "2026-07-14T09:00:00+05:30", "timeZone": "Asia/Kolkata"},
    "end": {"dateTime": "2026-07-14T09:30:00+05:30", "timeZone": "Asia/Kolkata"},
    "htmlLink": "https://calendar.google.com/event?eid=evt-no-meet-1",
}


async def _make_connection(db: AsyncSession, hc_user: User) -> GoogleCalendarConnection:
    conn = GoogleCalendarConnection(
        hc_user_id=hc_user.id,
        google_account_email="coach@example.com",
        scope_granted="https://www.googleapis.com/auth/calendar.events",
        credentials={"access_token": "at-still-valid", "refresh_token": "rt-456"},
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        connected_at=datetime.now(timezone.utc),
    )
    db.add(conn)
    await db.flush()
    return conn


async def _create_client(http_client, headers) -> dict:
    r = await http_client.post(
        "/api/clients", headers=headers,
        json={"full_name": f"Client {uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_session(http_client, headers, client_id: str) -> dict:
    r = await http_client.post(
        "/api/sessions", headers=headers,
        json={
            "client_id": client_id,
            "session_number": 1,
            "scheduled_at": "2026-06-01T10:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _mock_google_get_event_transport(response_json: dict, *, expected_status: int = 200):
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(expected_status, json=response_json)

    return handler, captured_requests


@pytest.mark.asyncio
async def test_link_calendar_event_with_meet_link_sets_session_fields(
    http_client, hc_headers, hc_user: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch,
):
    await _make_connection(db, hc_user)
    client = await _create_client(http_client, hc_headers)
    session = await _create_session(http_client, hc_headers, client["id"])

    handler, captured_requests = _mock_google_get_event_transport(_GOOGLE_EVENT_WITH_MEET)
    monkeypatch.setattr(
        "src.api.calendar.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    r = await http_client.post(
        f"/api/sessions/{session['id']}/calendar-link",
        headers=hc_headers,
        json={"google_event_id": "evt-meet-1"},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["google_calendar_event_id"] == "evt-meet-1"
    assert body["meeting_url"] == "https://meet.google.com/abc-defg-hij"

    # The re-fetch must hit the single-event endpoint (not the list endpoint)
    # with the calling HC's own bearer token.
    assert len(captured_requests) == 1
    sent = captured_requests[0]
    assert sent.url.path.endswith("/events/evt-meet-1")
    assert sent.headers["authorization"] == "Bearer at-still-valid"


@pytest.mark.asyncio
async def test_link_calendar_event_without_meet_link_returns_422_and_leaves_session_unchanged(
    http_client, hc_headers, hc_user: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch,
):
    await _make_connection(db, hc_user)
    client = await _create_client(http_client, hc_headers)
    session = await _create_session(http_client, hc_headers, client["id"])
    assert session["google_calendar_event_id"] is None
    assert session["meeting_url"] is None

    handler, _ = _mock_google_get_event_transport(_GOOGLE_EVENT_NO_MEET)
    monkeypatch.setattr(
        "src.api.calendar.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    r = await http_client.post(
        f"/api/sessions/{session['id']}/calendar-link",
        headers=hc_headers,
        json={"google_event_id": "evt-no-meet-1"},
    )

    assert r.status_code == 422, r.text
    assert r.json()["detail"] == (
        "Selected event has no Google Meet link. Add one in Calendar, or create a new event with Meet enabled."
    )

    get_r = await http_client.get(f"/api/sessions/{session['id']}", headers=hc_headers)
    assert get_r.status_code == 200, get_r.text
    assert get_r.json()["google_calendar_event_id"] is None
    assert get_r.json()["meeting_url"] is None


@pytest.mark.asyncio
async def test_unlink_calendar_event_clears_event_id_leaves_meeting_url(
    http_client, hc_headers, hc_user: User, db: AsyncSession, monkeypatch: pytest.MonkeyPatch,
):
    await _make_connection(db, hc_user)
    client = await _create_client(http_client, hc_headers)
    session = await _create_session(http_client, hc_headers, client["id"])

    handler, _ = _mock_google_get_event_transport(_GOOGLE_EVENT_WITH_MEET)
    monkeypatch.setattr(
        "src.api.calendar.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    link_r = await http_client.post(
        f"/api/sessions/{session['id']}/calendar-link",
        headers=hc_headers,
        json={"google_event_id": "evt-meet-1"},
    )
    assert link_r.status_code == 200, link_r.text
    assert link_r.json()["meeting_url"] == "https://meet.google.com/abc-defg-hij"

    unlink_r = await http_client.post(
        f"/api/sessions/{session['id']}/calendar-link",
        headers=hc_headers,
        json={"google_event_id": None},
    )

    assert unlink_r.status_code == 200, unlink_r.text
    body = unlink_r.json()
    assert body["google_calendar_event_id"] is None
    # meeting_url must be left untouched by an unlink.
    assert body["meeting_url"] == "https://meet.google.com/abc-defg-hij"


@pytest.mark.asyncio
async def test_link_calendar_event_cross_tenant_returns_404(
    http_client, hc_headers, hc2_headers, hc_user: User, db: AsyncSession,
):
    await _make_connection(db, hc_user)
    client = await _create_client(http_client, hc_headers)
    session = await _create_session(http_client, hc_headers, client["id"])

    # No Google transport mocked and no GoogleCalendarConnection row for hc2 —
    # if ownership were checked after the Google call (or not at all), this
    # would attempt a real network request and fail loudly rather than
    # silently pass.
    r = await http_client.post(
        f"/api/sessions/{session['id']}/calendar-link",
        headers=hc2_headers,
        json={"google_event_id": "evt-meet-1"},
    )

    assert r.status_code == 404, r.text
