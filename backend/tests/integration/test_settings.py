"""Integration tests for /api/settings/profile. Unit_006 PHASE-01."""
import pytest


@pytest.mark.asyncio
async def test_get_profile_returns_authenticated_hc(http_client, hc_user, hc_headers):
    r = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == hc_user.email
    assert body["business_name"] is None
    assert body["display_name"] is None
    assert body["photo_url"] is None


@pytest.mark.asyncio
async def test_patch_updates_business_name(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "Sunrise Wellness"}
    )
    assert r.status_code == 200
    assert r.json()["business_name"] == "Sunrise Wellness"

    r2 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r2.json()["business_name"] == "Sunrise Wellness"


@pytest.mark.asyncio
async def test_patch_empty_string_normalizes_to_null(http_client, hc_headers):
    await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "Something"}
    )
    r = await http_client.patch("/api/settings/profile", headers=hc_headers, json={"business_name": ""})
    assert r.status_code == 200
    assert r.json()["business_name"] is None


@pytest.mark.asyncio
async def test_patch_empty_body_is_noop_returns_200(http_client, hc_headers):
    r = await http_client.patch("/api/settings/profile", headers=hc_headers, json={})
    assert r.status_code == 200
    assert r.json()["business_name"] is None


@pytest.mark.asyncio
async def test_patch_exceeding_max_length_returns_422(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "x" * 201}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_profile_unauthenticated_returns_401(http_client):
    r = await http_client.get("/api/settings/profile")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_client_role_forbidden(http_client, client_headers):
    r = await http_client.get("/api/settings/profile", headers=client_headers)
    assert r.status_code == 403
