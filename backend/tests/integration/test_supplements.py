"""Integration tests for /api/clients/{client_id}/supplements. SPEC-0001 acceptance criteria."""
import uuid

import pytest


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_client(http_client, headers) -> dict:
    r = await http_client.post(
        "/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"}
    )
    assert r.status_code == 201
    return r.json()


async def _make_supplement(http_client, headers, client_id: str, **overrides) -> dict:
    payload = {
        "name": "Vitamin D3",
        "dosage": "2000 IU daily",
        "duration_days": 30,
        "notes": "for gut health",
    } | overrides
    r = await http_client.post(
        f"/api/clients/{client_id}/supplements", headers=headers, json=payload
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── POST ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_supplement_returns_201(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc_headers,
        json={"name": "Omega-3 / Fish Oil", "dosage": "1g daily", "duration_days": 60},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Omega-3 / Fish Oil"
    assert body["dosage"] == "1g daily"
    assert body["duration_days"] == 60
    assert body["notes"] is None
    assert "id" in body
    assert "recommended_at" in body


@pytest.mark.asyncio
async def test_create_supplement_missing_name_returns_422(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc_headers,
        json={"dosage": "1g daily"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_supplement_invalid_duration_returns_422(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc_headers,
        json={"name": "Zinc", "duration_days": 0},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_supplement_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc2_headers,
        json={"name": "Zinc"},
    )
    assert r.status_code == 404


# ── GET ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_supplements_returns_newest_first(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    await _make_supplement(http_client, hc_headers, client["id"], name="Iron")
    await _make_supplement(http_client, hc_headers, client["id"], name="Zinc")

    r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc_headers
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert items[0]["name"] == "Zinc"   # newest first
    assert items[1]["name"] == "Iron"


@pytest.mark.asyncio
async def test_list_supplements_excludes_archived(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc_headers
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_supplements_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc2_headers
    )
    assert r.status_code == 404


# ── PATCH ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_supplement_updates_fields(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.patch(
        f"/api/clients/{client['id']}/supplements/{s['id']}",
        headers=hc_headers,
        json={"dosage": "4000 IU daily", "duration_days": 60},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dosage"] == "4000 IU daily"
    assert body["duration_days"] == 60
    assert body["name"] == s["name"]   # unchanged


@pytest.mark.asyncio
async def test_patch_archived_supplement_returns_404(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    r = await http_client.patch(
        f"/api/clients/{client['id']}/supplements/{s['id']}",
        headers=hc_headers,
        json={"dosage": "new"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_supplement_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.patch(
        f"/api/clients/{client['id']}/supplements/{s['id']}",
        headers=hc2_headers,
        json={"dosage": "new"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_supplement_can_clear_optional_field(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"], dosage="2000 IU daily")
    r = await http_client.patch(
        f"/api/clients/{client['id']}/supplements/{s['id']}",
        headers=hc_headers,
        json={"dosage": None},
    )
    assert r.status_code == 200
    assert r.json()["dosage"] is None


# ── DELETE ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_supplement_returns_204_and_soft_deletes(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    assert r.status_code == 204
    # Must no longer appear in list
    list_r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc_headers
    )
    assert list_r.json() == []


@pytest.mark.asyncio
async def test_delete_already_archived_returns_404(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    r = await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_supplement_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc2_headers
    )
    assert r.status_code == 404
