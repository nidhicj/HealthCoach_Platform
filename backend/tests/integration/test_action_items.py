"""Integration tests for /api/action-items. P3 acceptance criteria."""
import uuid

import pytest


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_client(http_client, headers) -> dict:
    r = await http_client.post("/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 201
    return r.json()


async def _make_session(http_client, headers, client_id: str, num: int = 1) -> dict:
    r = await http_client.post(
        "/api/sessions", headers=headers,
        json={"client_id": client_id, "session_number": num, "scheduled_at": "2026-06-01T10:00:00Z"},
    )
    assert r.status_code == 201
    return r.json()


async def _make_action_item(http_client, headers, client_id: str, session_id: str | None = None, **extra) -> dict:
    payload: dict = {
        "client_id": client_id,
        "description": extra.pop("description", "Walk 30 min daily"),
    }
    if session_id:
        payload["session_id"] = session_id
    payload |= extra
    r = await http_client.post("/api/action-items", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── POST /api/action-items ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_action_item_returns_201(http_client, hc_headers, hc_user):
    client = await _make_client(http_client, hc_headers)
    sess = await _make_session(http_client, hc_headers, client["id"])

    r = await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={
            "client_id": client["id"],
            "session_id": sess["id"],
            "description": "Drink 2L water daily",
            "due_date": "2026-06-08",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "open"
    assert body["description"] == "Drink 2L water daily"
    assert body["client_id"] == client["id"]
    assert body["hc_user_id"] == str(hc_user.id)


@pytest.mark.asyncio
async def test_create_action_item_without_session(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": client["id"], "description": "No session needed"},
    )
    assert r.status_code == 201
    assert r.json()["session_id"] is None


@pytest.mark.asyncio
async def test_create_action_item_due_date_manual_no_default(http_client, hc_headers):
    """D-4: due_date is manual — no auto-default."""
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": client["id"], "description": "No due date"},
    )
    assert r.status_code == 201
    assert r.json()["due_date"] is None


@pytest.mark.asyncio
async def test_create_action_item_for_unowned_client_returns_422(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc2_headers)
    r = await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": client["id"], "description": "Should fail"},
    )
    assert r.status_code == 422


# ── GET /api/action-items ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_action_items_own_only(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    await _make_action_item(http_client, hc_headers, client["id"])

    r = await http_client.get("/api/action-items", headers=hc2_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_action_items_filter_by_client(http_client, hc_headers):
    c1 = await _make_client(http_client, hc_headers)
    c2 = await _make_client(http_client, hc_headers)
    await _make_action_item(http_client, hc_headers, c1["id"])
    await _make_action_item(http_client, hc_headers, c2["id"])

    r = await http_client.get("/api/action-items", headers=hc_headers, params={"client_id": c1["id"]})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["client_id"] == c1["id"]


@pytest.mark.asyncio
async def test_list_action_items_filter_by_status(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    ai = await _make_action_item(http_client, hc_headers, client["id"])

    # Mark in_progress
    await http_client.patch(f"/api/action-items/{ai['id']}", headers=hc_headers, json={"status": "in_progress"})

    r_open = await http_client.get("/api/action-items", headers=hc_headers, params={"status": "open"})
    r_in_prog = await http_client.get("/api/action-items", headers=hc_headers, params={"status": "in_progress"})

    assert r_open.status_code == 200
    assert r_in_prog.status_code == 200
    assert len(r_open.json()["items"]) == 0
    assert len(r_in_prog.json()["items"]) == 1


# ── PATCH /api/action-items/{id} ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_action_item_status_open_to_completed(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    ai = await _make_action_item(http_client, hc_headers, client["id"])

    r = await http_client.patch(
        f"/api/action-items/{ai['id']}", headers=hc_headers,
        json={"status": "completed"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None


@pytest.mark.asyncio
async def test_patch_action_item_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    ai = await _make_action_item(http_client, hc_headers, client["id"])

    r = await http_client.patch(
        f"/api/action-items/{ai['id']}", headers=hc2_headers,
        json={"status": "completed"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_action_item_completed_clears_on_transition_back(http_client, hc_headers):
    """HC can freely change status; completed_at is cleared when moving away from completed."""
    client = await _make_client(http_client, hc_headers)
    ai = await _make_action_item(http_client, hc_headers, client["id"])

    await http_client.patch(f"/api/action-items/{ai['id']}", headers=hc_headers, json={"status": "completed"})
    r = await http_client.patch(f"/api/action-items/{ai['id']}", headers=hc_headers, json={"status": "open"})
    assert r.status_code == 200
    assert r.json()["completed_at"] is None
