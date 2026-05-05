"""Integration tests for /api/sessions (including MOMs and brief). P3 acceptance criteria."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.conftest import auth_headers


# ── helpers ────────────────────────────────────────────────────────────────────


async def _create_client(http_client, headers) -> dict:
    r = await http_client.post(
        "/api/clients", headers=headers,
        json={"full_name": f"Client {uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 201
    return r.json()


async def _create_session(http_client, headers, client_id: str, session_number: int = 1) -> dict:
    r = await http_client.post(
        "/api/sessions", headers=headers,
        json={
            "client_id": client_id,
            "session_number": session_number,
            "scheduled_at": "2026-06-01T10:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_mom(http_client, headers, session_id: str, draft_text: str = "Test MOM") -> dict:
    r = await http_client.post(
        f"/api/sessions/{session_id}/mom",
        headers=headers,
        json={"draft_text": draft_text},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── POST /api/sessions ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_session_returns_201(http_client, hc_headers, hc_user):
    client = await _create_client(http_client, hc_headers)
    r = await http_client.post(
        "/api/sessions", headers=hc_headers,
        json={
            "client_id": client["id"],
            "session_number": 0,
            "scheduled_at": "2026-06-01T10:00:00Z",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["client_id"] == client["id"]
    assert body["session_number"] == 0
    assert body["hc_user_id"] == str(hc_user.id)
    assert body["ended_at"] is None


@pytest.mark.asyncio
async def test_create_session_for_unowned_client_returns_422(http_client, hc_headers, hc2_headers):
    client = await _create_client(http_client, hc2_headers)  # belongs to hc2
    r = await http_client.post(
        "/api/sessions", headers=hc_headers,
        json={"client_id": client["id"], "session_number": 1, "scheduled_at": "2026-06-01T10:00:00Z"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_session_number_returns_409(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    await _create_session(http_client, hc_headers, client["id"], session_number=1)
    r = await http_client.post(
        "/api/sessions", headers=hc_headers,
        json={"client_id": client["id"], "session_number": 1, "scheduled_at": "2026-06-02T10:00:00Z"},
    )
    assert r.status_code == 409


# ── GET /api/sessions ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sessions_returns_own(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    await _create_session(http_client, hc_headers, client["id"], 1)
    await _create_session(http_client, hc_headers, client["id"], 2)

    r = await http_client.get("/api/sessions", headers=hc_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


@pytest.mark.asyncio
async def test_list_sessions_cross_tenant_isolation(http_client, hc_headers, hc2_headers):
    client = await _create_client(http_client, hc_headers)
    await _create_session(http_client, hc_headers, client["id"], 1)

    r = await http_client.get("/api/sessions", headers=hc2_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_sessions_filter_by_client(http_client, hc_headers):
    c1 = await _create_client(http_client, hc_headers)
    c2 = await _create_client(http_client, hc_headers)
    await _create_session(http_client, hc_headers, c1["id"], 1)
    await _create_session(http_client, hc_headers, c2["id"], 1)

    r = await http_client.get("/api/sessions", headers=hc_headers, params={"client_id": c1["id"]})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["client_id"] == c1["id"]


# ── GET /api/sessions/{id} ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_session_detail(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    r = await http_client.get(f"/api/sessions/{sess['id']}", headers=hc_headers)
    assert r.status_code == 200
    assert r.json()["id"] == sess["id"]


@pytest.mark.asyncio
async def test_get_session_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    r = await http_client.get(f"/api/sessions/{sess['id']}", headers=hc2_headers)
    assert r.status_code == 404


# ── POST /api/sessions/{id}/end ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_end_session_sets_ended_at(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    assert sess["ended_at"] is None

    r = await http_client.post(f"/api/sessions/{sess['id']}/end", headers=hc_headers)
    assert r.status_code == 200
    assert r.json()["ended_at"] is not None


@pytest.mark.asyncio
async def test_end_session_idempotent(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])

    r1 = await http_client.post(f"/api/sessions/{sess['id']}/end", headers=hc_headers)
    r2 = await http_client.post(f"/api/sessions/{sess['id']}/end", headers=hc_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["ended_at"] == r2.json()["ended_at"]


# ── GET /api/sessions/{id}/brief ──────────────────────────────────────────────
# Brief generation (P4) replaces the P3 stub. The full brief happy-path is
# covered by test_mom_draft.py::test_get_brief_generates_and_caches.


# ── POST /api/sessions/{id}/mom (create MOM) ──────────────────────────────────


@pytest.mark.asyncio
async def test_create_mom_returns_draft(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])

    r = await http_client.post(
        f"/api/sessions/{sess['id']}/mom",
        headers=hc_headers,
        json={"draft_text": "Session went well. Client is progressing."},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft"
    assert body["draft_text"] == "Session went well. Client is progressing."
    assert body["session_id"] == sess["id"]


@pytest.mark.asyncio
async def test_create_mom_duplicate_returns_409(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    await _create_mom(http_client, hc_headers, sess["id"])
    r = await http_client.post(
        f"/api/sessions/{sess['id']}/mom", headers=hc_headers,
        json={"draft_text": "Second MOM"},
    )
    assert r.status_code == 409


# ── GET /api/sessions/{id}/mom ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_mom_returns_any_status(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    mom = await _create_mom(http_client, hc_headers, sess["id"])

    r = await http_client.get(f"/api/sessions/{sess['id']}/mom", headers=hc_headers)
    assert r.status_code == 200
    assert r.json()["id"] == mom["id"]
    assert r.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_get_mom_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    await _create_mom(http_client, hc_headers, sess["id"])

    r = await http_client.get(f"/api/sessions/{sess['id']}/mom", headers=hc2_headers)
    assert r.status_code == 404


# ── PATCH /api/sessions/{id}/mom ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_mom_updates_text(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    await _create_mom(http_client, hc_headers, sess["id"])

    r = await http_client.patch(
        f"/api/sessions/{sess['id']}/mom", headers=hc_headers,
        json={"draft_text": "Updated draft text"},
    )
    assert r.status_code == 200
    assert r.json()["draft_text"] == "Updated draft text"


@pytest.mark.asyncio
async def test_patch_mom_cannot_set_sent_status(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    await _create_mom(http_client, hc_headers, sess["id"])

    r = await http_client.patch(
        f"/api/sessions/{sess['id']}/mom", headers=hc_headers,
        json={"status": "sent"},
    )
    assert r.status_code == 422


# ── POST /api/sessions/{id}/mom/send ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_mom_transitions_to_sent(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    await _create_mom(http_client, hc_headers, sess["id"], draft_text="Original draft")

    r = await http_client.post(f"/api/sessions/{sess['id']}/mom/send", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "sent"
    assert body["sent_at"] is not None
    assert body["final_text"] == "Original draft"  # copied from draft_text when final_text was null


@pytest.mark.asyncio
async def test_send_mom_idempotent(http_client, hc_headers):
    client = await _create_client(http_client, hc_headers)
    sess = await _create_session(http_client, hc_headers, client["id"])
    await _create_mom(http_client, hc_headers, sess["id"])

    r1 = await http_client.post(f"/api/sessions/{sess['id']}/mom/send", headers=hc_headers)
    r2 = await http_client.post(f"/api/sessions/{sess['id']}/mom/send", headers=hc_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["sent_at"] == r2.json()["sent_at"]
