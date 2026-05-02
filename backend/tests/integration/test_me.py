"""Integration tests for /api/me/* client-facing endpoints. P3."""
import uuid

import pytest


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_session(http_client, headers, client_id: str, num: int = 1) -> dict:
    r = await http_client.post(
        "/api/sessions", headers=headers,
        json={"client_id": client_id, "session_number": num, "scheduled_at": "2026-06-01T10:00:00Z"},
    )
    assert r.status_code == 201
    return r.json()


async def _make_mom_sent(http_client, headers, session_id: str) -> dict:
    r = await http_client.post(
        f"/api/sessions/{session_id}/mom", headers=headers,
        json={"draft_text": "Session recap draft"},
    )
    assert r.status_code == 201
    r2 = await http_client.post(f"/api/sessions/{session_id}/mom/send", headers=headers)
    assert r2.status_code == 200
    return r2.json()


# ── POST /api/me/check-ins ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_submit_check_in_returns_201(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/check-ins", headers=client_headers,
        json={"payload": {"mood": "good", "energy": 8}},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["client_id"] == str(client_rec.id)
    assert body["payload"] == {"mood": "good", "energy": 8}
    assert body["sentiment_flag"] is None


@pytest.mark.asyncio
async def test_hc_token_cannot_submit_check_in(http_client, hc_headers):
    r = await http_client.post(
        "/api/me/check-ins", headers=hc_headers,
        json={"payload": {"mood": "ok"}},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_client_without_linked_record_returns_404(http_client, hc_user, client_user):
    """Client user with no Client record in the DB gets 404."""
    from tests.integration.conftest import auth_headers
    unlinked_headers = auth_headers(client_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.post(
        "/api/me/check-ins", headers=unlinked_headers,
        json={"payload": {"mood": "ok"}},
    )
    assert r.status_code == 404


# ── GET /api/me/moms ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_sees_sent_moms(http_client, hc_headers, client_headers, client_rec):
    sess = await _make_session(http_client, hc_headers, str(client_rec.id))
    await _make_mom_sent(http_client, hc_headers, sess["id"])

    r = await http_client.get("/api/me/moms", headers=client_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "sent"
    assert items[0]["client_id"] == str(client_rec.id)


@pytest.mark.asyncio
async def test_client_cannot_see_draft_moms(http_client, hc_headers, client_headers, client_rec):
    sess = await _make_session(http_client, hc_headers, str(client_rec.id))
    await http_client.post(
        f"/api/sessions/{sess['id']}/mom", headers=hc_headers,
        json={"draft_text": "Draft only"},
    )

    r = await http_client.get("/api/me/moms", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_client_sees_empty_moms_list(http_client, client_headers, client_rec):
    r = await http_client.get("/api/me/moms", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


# ── GET /api/me/action-items ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_sees_own_action_items(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": str(client_rec.id), "description": "Walk 30 min daily"},
    )

    r = await http_client.get("/api/me/action-items", headers=client_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["description"] == "Walk 30 min daily"


@pytest.mark.asyncio
async def test_client_sees_empty_action_items(http_client, client_headers, client_rec):
    r = await http_client.get("/api/me/action-items", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []
