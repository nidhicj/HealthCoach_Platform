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
async def test_patch_empty_body_is_noop_preserves_existing_value(http_client, hc_headers):
    r1 = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "Sunrise Wellness"}
    )
    assert r1.status_code == 200
    assert r1.json()["business_name"] == "Sunrise Wellness"

    r2 = await http_client.patch("/api/settings/profile", headers=hc_headers, json={})
    assert r2.status_code == 200

    r3 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r3.json()["business_name"] == "Sunrise Wellness"


@pytest.mark.asyncio
async def test_patch_exceeding_max_length_returns_422(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "x" * 201}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_trims_leading_and_trailing_whitespace(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "  Acme  "}
    )
    assert r.status_code == 200
    assert r.json()["business_name"] == "Acme"


@pytest.mark.asyncio
async def test_patch_whitespace_only_normalizes_to_null(http_client, hc_headers):
    await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "Something"}
    )
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "   "}
    )
    assert r.status_code == 200
    assert r.json()["business_name"] is None


@pytest.mark.asyncio
async def test_get_profile_unauthenticated_returns_401(http_client):
    r = await http_client.get("/api/settings/profile")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_client_role_forbidden(http_client, client_headers):
    r = await http_client.get("/api/settings/profile", headers=client_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_hc_profile_isolation(http_client, hc_headers, hc2_headers):
    """This endpoint deliberately keys off claims.sub instead of TenantDep — verify
    that still isolates HC-A's profile writes from HC-B's."""
    r1 = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "HC-A Wellness"}
    )
    assert r1.status_code == 200
    assert r1.json()["business_name"] == "HC-A Wellness"

    r2 = await http_client.get("/api/settings/profile", headers=hc2_headers)
    assert r2.status_code == 200
    assert r2.json()["business_name"] is None

    r3 = await http_client.patch(
        "/api/settings/profile", headers=hc2_headers, json={"business_name": "HC-B Coaching"}
    )
    assert r3.status_code == 200
    assert r3.json()["business_name"] == "HC-B Coaching"

    r4 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r4.status_code == 200
    assert r4.json()["business_name"] == "HC-A Wellness"
