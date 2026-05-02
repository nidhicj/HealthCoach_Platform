"""Integration tests for /api/clients. P3 acceptance criteria."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Client, User
from tests.integration.conftest import auth_headers


# ── helpers ────────────────────────────────────────────────────────────────────


async def _create_client(http_client, headers, **extra) -> dict:
    payload = {"full_name": extra.pop("full_name", f"Client {uuid.uuid4().hex[:6]}")} | extra
    r = await http_client.post("/api/clients", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── POST /api/clients ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_client_returns_201(http_client, hc_headers, hc_user):
    r = await http_client.post(
        "/api/clients",
        headers=hc_headers,
        json={"full_name": "Priya Sharma"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["full_name"] == "Priya Sharma"
    assert body["hc_user_id"] == str(hc_user.id)
    assert body["journey_stage"] == "onboarding"
    assert "id" in body


@pytest.mark.asyncio
async def test_create_client_with_all_fields(http_client, hc_headers):
    r = await http_client.post(
        "/api/clients",
        headers=hc_headers,
        json={
            "full_name": "Rahul Gupta",
            "email": "rahul@example.com",
            "phone": "+91-9876543210",
            "timezone": "Asia/Kolkata",
            "journey_stage": "active",
            "course_goal": "Lose 10 kg in 3 months",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "rahul@example.com"
    assert body["journey_stage"] == "active"


@pytest.mark.asyncio
async def test_create_client_requires_auth(http_client):
    r = await http_client.post("/api/clients", json={"full_name": "Ghost"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_client_requires_hc_role(http_client, hc_user):
    client_headers = auth_headers(hc_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.post("/api/clients", headers=client_headers, json={"full_name": "X"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_client_rejects_invalid_journey_stage(http_client, hc_headers):
    r = await http_client.post(
        "/api/clients",
        headers=hc_headers,
        json={"full_name": "Bad Stage", "journey_stage": "invalid_stage"},
    )
    assert r.status_code == 422


# ── GET /api/clients ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_clients_empty(http_client, hc_headers):
    r = await http_client.get("/api/clients", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


@pytest.mark.asyncio
async def test_list_clients_returns_own_clients(http_client, hc_headers, hc_user):
    await _create_client(http_client, hc_headers, full_name="Alice")
    await _create_client(http_client, hc_headers, full_name="Bob")

    r = await http_client.get("/api/clients", headers=hc_headers)
    assert r.status_code == 200
    names = {c["full_name"] for c in r.json()["items"]}
    assert {"Alice", "Bob"} == names


@pytest.mark.asyncio
async def test_list_clients_cross_tenant_isolation(http_client, hc_headers, hc2_headers):
    """HC1's clients are invisible to HC2."""
    await _create_client(http_client, hc_headers, full_name="HC1 Client")

    r = await http_client.get("/api/clients", headers=hc2_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_clients_pagination_cursor(http_client, hc_headers):
    """25 clients → first page has next_cursor; second page has the rest."""
    for i in range(25):
        await _create_client(http_client, hc_headers, full_name=f"Client {i:02d}")

    r1 = await http_client.get("/api/clients", headers=hc_headers, params={"limit": 20})
    assert r1.status_code == 200
    body1 = r1.json()
    assert len(body1["items"]) == 20
    assert body1["next_cursor"] is not None

    r2 = await http_client.get(
        "/api/clients", headers=hc_headers,
        params={"limit": 20, "cursor": body1["next_cursor"]},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["items"]) == 5
    assert body2["next_cursor"] is None

    ids1 = {c["id"] for c in body1["items"]}
    ids2 = {c["id"] for c in body2["items"]}
    assert ids1.isdisjoint(ids2), "Pages must not overlap"


@pytest.mark.asyncio
async def test_list_clients_invalid_cursor(http_client, hc_headers):
    r = await http_client.get("/api/clients", headers=hc_headers, params={"cursor": "notvalidbase64!!!"})
    assert r.status_code == 400


# ── GET /api/clients/{id} ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_client_detail(http_client, hc_headers):
    created = await _create_client(http_client, hc_headers, full_name="Detail Test")
    r = await http_client.get(f"/api/clients/{created['id']}", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == created["id"]
    assert body["full_name"] == "Detail Test"
    assert "ast" in body  # stub — null at P3
    assert body["ast"] is None


@pytest.mark.asyncio
async def test_get_client_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    """HC1's client is 404 for HC2 — never 403 (don't leak existence)."""
    created = await _create_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{created['id']}", headers=hc2_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_client_not_found(http_client, hc_headers):
    r = await http_client.get(f"/api/clients/{uuid.uuid4()}", headers=hc_headers)
    assert r.status_code == 404
