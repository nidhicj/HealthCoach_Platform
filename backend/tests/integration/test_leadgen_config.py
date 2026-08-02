"""Integration tests: /api/leadgen/config* endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_init_fails_when_profile_incomplete(http_client: AsyncClient, hc_headers):
    # hc_user fixture has no first_name/last_name set by default
    resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["error"] == "profile_incomplete"


async def test_init_succeeds_and_generates_slug(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()

    resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp.status_code == 201
    body = resp.json()
    import re
    assert re.match(r"^asha-rao-[a-z0-9]{5}$", body["hc_slug"])
    assert len(body["questionnaire"]) == 6
    assert all(q["removable"] is False for q in body["questionnaire"])
    assert body["test_panel"] == {"standard_tests": [], "condition_rules": []}


async def test_init_conflicts_if_already_configured(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    resp1 = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp1.status_code == 201

    resp2 = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["error"] == "already_configured"
