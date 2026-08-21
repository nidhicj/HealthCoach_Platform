"""Integration tests for /api/settings/profile. Unit_006 PHASE-01."""
import pytest


@pytest.mark.asyncio
async def test_get_profile_returns_authenticated_hc(http_client, hc_user, hc_headers):
    r = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == hc_user.email
    assert body["business_name"] is None
    assert body["first_name"] is None
    assert body["last_name"] is None
    assert body["display_name"] is None
    assert body["photo_url"] is None


@pytest.mark.asyncio
async def test_get_profile_returns_first_and_last_name_when_set(
    http_client, db, hc_user, hc_headers
):
    hc_user.first_name = "Jane"
    hc_user.last_name = "Doe"
    await db.commit()

    r = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Doe"


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
async def test_patch_updates_first_and_last_name(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": "Jane", "last_name": "Doe"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Doe"

    r2 = await http_client.get("/api/settings/profile", headers=hc_headers)
    body2 = r2.json()
    assert body2["first_name"] == "Jane"
    assert body2["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_patch_first_name_trims_leading_and_trailing_whitespace(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile",
        headers=hc_headers,
        json={"first_name": "  Jane  ", "last_name": "  Doe  "},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_patch_first_name_empty_string_returns_422_and_preserves_existing_value(
    http_client, hc_headers
):
    await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": "Jane"}
    )

    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": ""}
    )
    assert r.status_code == 422

    r2 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r2.json()["first_name"] == "Jane"


@pytest.mark.asyncio
async def test_patch_first_name_whitespace_only_returns_422_and_preserves_existing_value(
    http_client, hc_headers
):
    await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": "Jane"}
    )

    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": "   "}
    )
    assert r.status_code == 422

    r2 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r2.json()["first_name"] == "Jane"


@pytest.mark.asyncio
async def test_patch_last_name_empty_string_returns_422_and_preserves_existing_value(
    http_client, hc_headers
):
    await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"last_name": "Doe"}
    )

    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"last_name": ""}
    )
    assert r.status_code == 422

    r2 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r2.json()["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_patch_first_name_explicit_null_returns_422_and_preserves_existing_value(
    http_client, hc_headers
):
    """first_name/last_name are 'required once set' and cannot be cleared back to
    null via this endpoint, unlike business_name — an explicit JSON null is rejected
    the same as an empty string, rather than silently clearing the field."""
    await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": "Jane"}
    )

    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": None}
    )
    assert r.status_code == 422

    r2 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r2.json()["first_name"] == "Jane"


@pytest.mark.asyncio
async def test_patch_omitting_first_name_preserves_existing_value_on_partial_update(
    http_client, hc_headers
):
    """Regression coverage for the Task 2 bug history: omitting a field from the PATCH
    body must be a genuine no-op, not silent data loss. Sets both fields, then PATCHes
    only last_name, and confirms first_name survives on a subsequent GET."""
    r1 = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": "Jane", "last_name": "Doe"}
    )
    assert r1.status_code == 200

    r2 = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"last_name": "Smith"}
    )
    assert r2.status_code == 200
    assert r2.json()["last_name"] == "Smith"
    assert r2.json()["first_name"] == "Jane"

    r3 = await http_client.get("/api/settings/profile", headers=hc_headers)
    body = r3.json()
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Smith"


@pytest.mark.asyncio
async def test_patch_first_name_exceeding_max_length_returns_422(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"first_name": "x" * 201}
    )
    assert r.status_code == 422


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
    that still isolates HC-A's profile writes from HC-B's. Covers every writable
    field, not just business_name, so isolation coverage doesn't silently narrow
    as fields are added."""
    r1 = await http_client.patch(
        "/api/settings/profile",
        headers=hc_headers,
        json={"business_name": "HC-A Wellness", "first_name": "Asha", "last_name": "Verma"},
    )
    assert r1.status_code == 200
    assert r1.json()["business_name"] == "HC-A Wellness"
    assert r1.json()["first_name"] == "Asha"
    assert r1.json()["last_name"] == "Verma"

    r2 = await http_client.get("/api/settings/profile", headers=hc2_headers)
    assert r2.status_code == 200
    assert r2.json()["business_name"] is None
    assert r2.json()["first_name"] is None
    assert r2.json()["last_name"] is None

    r3 = await http_client.patch(
        "/api/settings/profile",
        headers=hc2_headers,
        json={"business_name": "HC-B Coaching", "first_name": "Bina", "last_name": "Rao"},
    )
    assert r3.status_code == 200
    assert r3.json()["business_name"] == "HC-B Coaching"
    assert r3.json()["first_name"] == "Bina"
    assert r3.json()["last_name"] == "Rao"

    r4 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r4.status_code == 200
    assert r4.json()["business_name"] == "HC-A Wellness"
    assert r4.json()["first_name"] == "Asha"
    assert r4.json()["last_name"] == "Verma"
