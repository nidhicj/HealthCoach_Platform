"""Integration tests: /api/leadgen/config* endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import text

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


async def test_get_config_returns_setup_incomplete_when_not_configured(http_client: AsyncClient, hc_headers):
    resp = await http_client.get("/api/leadgen/config", headers=hc_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False


async def test_get_config_returns_full_config_when_configured(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    init_resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert init_resp.status_code == 201

    resp = await http_client.get("/api/leadgen/config", headers=hc_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["hc_slug"] == init_resp.json()["hc_slug"]


async def test_get_config_cross_tenant_isolation(http_client: AsyncClient, hc_user, hc_headers, hc2_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.get("/api/leadgen/config", headers=hc2_headers)
    assert resp.status_code == 200
    assert resp.json()["configured"] is False  # HC2 sees their own (nonexistent) config, never HC1's


async def test_patch_updates_settings_fields(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.patch(
        "/api/leadgen/config", headers=hc_headers,
        json={"consultation_fee_inr": 2000, "scheduling_link": "https://calendly.com/asha"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["consultation_fee_inr"] == 2000
    assert body["scheduling_link"] == "https://calendly.com/asha"


async def test_patch_ignores_hc_slug_field(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    init_resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    original_slug = init_resp.json()["hc_slug"]

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"hc_slug": "hacked-slug-00000"})
    assert resp.status_code == 200
    assert resp.json()["hc_slug"] == original_slug  # unchanged


async def test_patch_rejects_removing_fixed_question(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"questionnaire": []})
    assert resp.status_code == 422


async def test_patch_rejects_marking_fixed_question_removable(http_client: AsyncClient, hc_user, hc_headers, db):
    from src.api.leadgen import _FIXED_QUESTIONS

    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    tampered = [dict(q) for q in _FIXED_QUESTIONS]
    tampered[0]["removable"] = True  # full_name — key still present, but defanged

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"questionnaire": tampered})
    assert resp.status_code == 422


async def test_patch_returns_404_when_not_configured(http_client: AsyncClient, hc_headers):
    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"consultation_fee_inr": 1000})
    assert resp.status_code == 404


async def test_patch_rejects_retyping_fixed_question(http_client: AsyncClient, hc_user, hc_headers, db):
    """D-1/D-2: a fixed question's type/required/text must not be changeable via PATCH,
    not just its key/removable — PHASE-02's render path depends on fixed questions
    staying free_text/required."""
    from src.api.leadgen import _FIXED_QUESTIONS

    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    tampered = [dict(q) for q in _FIXED_QUESTIONS]
    tampered[0]["type"] = "scale"  # full_name — key present, not marked removable, but retyped
    tampered[0]["required"] = False

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"questionnaire": tampered})
    assert resp.status_code == 422

    # confirm nothing was persisted
    get_resp = await http_client.get("/api/leadgen/config", headers=hc_headers)
    full_name_q = next(q for q in get_resp.json()["questionnaire"] if q["key"] == "full_name")
    assert full_name_q["type"] == "free_text"
    assert full_name_q["required"] is True


async def test_patch_rejects_explicit_null_on_not_null_field(http_client: AsyncClient, hc_user, hc_headers, db):
    """consultation_duration_min backs a NOT NULL column. An explicit null in the PATCH
    body must be rejected with a clean 422, not reach the DB and raise a raw 500."""
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"consultation_duration_min": None})
    assert resp.status_code == 422


async def test_patch_rejects_malformed_questionnaire_entry(http_client: AsyncClient, hc_user, hc_headers, db):
    """A questionnaire entry missing required Question fields (e.g. no 'type') must be
    rejected at the request-validation layer, not persisted — a malformed persisted
    questionnaire later breaks the frontend's Zod parse on GET."""
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    from src.api.leadgen import _FIXED_QUESTIONS

    malformed = [dict(q) for q in _FIXED_QUESTIONS]
    malformed.append({"key": "custom_bad", "text": "Missing type field"})  # no 'type', 'required', 'removable'

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"questionnaire": malformed})
    assert resp.status_code == 422


async def test_patch_rejects_explicit_null_on_questionnaire_without_corrupting_row(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """N-1: JSONB columns don't get NOT NULL protection for free the way scalar columns
    do — SQLAlchemy's JSONB writes Python None as the JSON literal `null`, which
    satisfies the SQL NOT NULL constraint and commits successfully, corrupting the row
    (every later GET/PATCH 500s on response serialization, no API-level recovery).
    An explicit null must be rejected with 422 before the commit happens at all."""
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"questionnaire": None})
    assert resp.status_code == 422

    # row must still be intact — GET still works and questionnaire is a real JSON array,
    # not JSON null (which is what a corrupted row would look like).
    get_resp = await http_client.get("/api/leadgen/config", headers=hc_headers)
    assert get_resp.status_code == 200
    assert len(get_resp.json()["questionnaire"]) == 6

    type_result = await db.execute(
        text("SELECT jsonb_typeof(questionnaire) FROM hc_leadgen_config WHERE hc_user_id = :hc_id"),
        {"hc_id": hc_user.id},
    )
    assert type_result.scalar_one() == "array"


async def test_patch_rejects_explicit_null_on_test_panel_without_corrupting_row(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """Same as above for test_panel — the other JSONB NOT NULL column."""
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"test_panel": None})
    assert resp.status_code == 422

    get_resp = await http_client.get("/api/leadgen/config", headers=hc_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["test_panel"] == {"standard_tests": [], "condition_rules": []}

    type_result = await db.execute(
        text("SELECT jsonb_typeof(test_panel) FROM hc_leadgen_config WHERE hc_user_id = :hc_id"),
        {"hc_id": hc_user.id},
    )
    assert type_result.scalar_one() == "object"
