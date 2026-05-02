"""Integration tests for check-in routes (HC flag + list, client submit). P3."""
import uuid

import pytest

from tests.integration.conftest import auth_headers


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_client(http_client, headers) -> dict:
    r = await http_client.post("/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 201
    return r.json()


async def _submit_check_in(http_client, headers, payload: dict | None = None) -> dict:
    r = await http_client.post(
        "/api/me/check-ins", headers=headers,
        json={"payload": payload or {"mood": "good", "note": "Feeling great"}},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── GET /api/clients/{id}/check-ins ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_client_check_ins_empty(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/check-ins", headers=hc_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_client_check_ins_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/check-ins", headers=hc2_headers)
    assert r.status_code == 404


# ── PATCH /api/check-ins/{id}/flag ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_flag_check_in_sets_sentiment(http_client, hc_headers, hc_user, db):
    """Create a check-in directly in DB (client submit not yet needed), then flag it."""
    from src.db.models import CheckIn

    client_rec = await _make_client(http_client, hc_headers)

    # Create check-in directly — client submit is tested in test_me.py
    ci = CheckIn(
        client_id=uuid.UUID(client_rec["id"]),
        hc_user_id=hc_user.id,
        payload={"mood": "ok"},
    )
    db.add(ci)
    await db.flush()
    await db.commit()

    r = await http_client.patch(
        f"/api/check-ins/{ci.id}/flag", headers=hc_headers,
        json={"sentiment_flag": "concern"},
    )
    assert r.status_code == 200
    assert r.json()["sentiment_flag"] == "concern"


@pytest.mark.asyncio
async def test_flag_check_in_clears_sentiment(http_client, hc_headers, hc_user, db):
    from src.db.models import CheckIn

    client_rec = await _make_client(http_client, hc_headers)
    ci = CheckIn(
        client_id=uuid.UUID(client_rec["id"]),
        hc_user_id=hc_user.id,
        payload={"mood": "ok"},
        sentiment_flag="concern",
    )
    db.add(ci)
    await db.flush()
    await db.commit()

    r = await http_client.patch(
        f"/api/check-ins/{ci.id}/flag", headers=hc_headers,
        json={"sentiment_flag": None},
    )
    assert r.status_code == 200
    assert r.json()["sentiment_flag"] is None


@pytest.mark.asyncio
async def test_flag_check_in_cross_tenant_returns_404(http_client, hc_headers, hc2_headers, hc_user, db):
    from src.db.models import CheckIn

    client_rec = await _make_client(http_client, hc_headers)
    ci = CheckIn(
        client_id=uuid.UUID(client_rec["id"]),
        hc_user_id=hc_user.id,
        payload={"mood": "ok"},
    )
    db.add(ci)
    await db.flush()
    await db.commit()

    r = await http_client.patch(
        f"/api/check-ins/{ci.id}/flag", headers=hc2_headers,
        json={"sentiment_flag": "concern"},
    )
    assert r.status_code == 404
