"""Integration tests: GET /api/intake/:slug (public, unauthenticated). PHASE-02."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _init_leadgen_config(http_client: AsyncClient, hc_user, hc_headers, db) -> dict:
    """Sets first/last name and initializes leadgen config via the existing HC-facing
    endpoint, returning the created config body (includes hc_slug)."""
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()

    resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_valid_configured_slug_returns_200_with_expected_fields(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _init_leadgen_config(http_client, hc_user, hc_headers, db)

    # No Authorization header at all — this is a public endpoint.
    resp = await http_client.get(f"/api/intake/{config['hc_slug']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["hc_name"] == "Asha Rao"
    assert body["hc_photo_url"] is None
    assert body["questionnaire"] == config["questionnaire"]


async def test_nonexistent_slug_returns_404(http_client: AsyncClient):
    resp = await http_client.get("/api/intake/this-slug-does-not-exist-00000")
    assert resp.status_code == 404


async def test_plausible_but_unmatched_slug_returns_same_404_as_nonexistent(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """A slug that looks like a real generated slug (name-name-suffix shape) but
    doesn't match any HcLeadgenConfig row must 404 identically to a slug that never
    existed at all — no existence-leaking."""
    await _init_leadgen_config(http_client, hc_user, hc_headers, db)

    plausible_resp = await http_client.get("/api/intake/asha-rao-zzzzz")
    nonexistent_resp = await http_client.get("/api/intake/totally-unrelated-99999")

    assert plausible_resp.status_code == 404
    assert nonexistent_resp.status_code == 404
    assert plausible_resp.json() == nonexistent_resp.json()


async def test_response_contains_only_allowlisted_fields(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """The core security property of this endpoint: the response body must contain
    exactly {hc_name, hc_photo_url, questionnaire} and nothing else — no hc_slug,
    no hc_user_id, no test_panel, no consultation fields, etc."""
    config = await _init_leadgen_config(http_client, hc_user, hc_headers, db)

    resp = await http_client.get(f"/api/intake/{config['hc_slug']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == {"hc_name", "hc_photo_url", "questionnaire"}
