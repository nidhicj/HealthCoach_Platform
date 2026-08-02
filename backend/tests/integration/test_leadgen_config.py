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


async def test_init_returns_conflict_not_500_when_hc_user_id_races_during_insert(
    http_client: AsyncClient, hc_user, hc_headers, db, monkeypatch
):
    """Simulates two concurrent POST /config/init requests for the same hc_user_id
    (e.g. a double-click on the one-time setup button). The second request's insert
    fails on the hc_user_id UNIQUE constraint, not the hc_slug one — the retry loop
    must recognize this via a re-query rather than misdiagnosing it as a slug
    collision (which would burn all retries and return a misleading 500)."""
    from src.db.models import HcLeadgenConfig

    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()

    original_execute = db.execute
    call_count = {"n": 0}

    async def _execute_with_late_insert(*args, **kwargs):
        call_count["n"] += 1
        result = await original_execute(*args, **kwargs)
        if call_count["n"] == 1:
            # This is the handler's pre-check (sees no existing config yet). Simulate
            # a competing request winning the race right after: it inserts and commits
            # its own config for the same hc_user_id before this request's insert runs.
            competing = HcLeadgenConfig(
                hc_user_id=hc_user.id,
                hc_slug="asha-rao-raced",
                questionnaire=[],
            )
            db.add(competing)
            await db.flush()
            await db.commit()
        return result

    monkeypatch.setattr(db, "execute", _execute_with_late_insert)

    resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "already_configured"
