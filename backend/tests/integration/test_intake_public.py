"""Integration tests: GET/POST /api/intake/:slug (public, unauthenticated). PHASE-02."""
import uuid as uuid_mod
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import Lead, LeadQuestionnaireResponse

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


# ── POST /api/intake/:slug — questionnaire submission ───────────────────────────


async def _configure_with_custom_questions(
    http_client: AsyncClient, hc_user, hc_headers, db
) -> dict:
    """Sets up base leadgen config (six fixed questions), then PATCHes in one
    multiple_choice and one scale custom question so the type-specific validation
    branches can be exercised, not just the fixed free_text ones."""
    config = await _init_leadgen_config(http_client, hc_user, hc_headers, db)
    questionnaire = [
        *config["questionnaire"],
        {
            "key": "diet_type",
            "text": "What is your diet type?",
            "type": "multiple_choice",
            "required": True,
            "removable": True,
            "options": ["Vegetarian", "Non-vegetarian", "Vegan"],
        },
        {
            "key": "energy_level",
            "text": "Rate your energy level (1-10)",
            "type": "scale",
            "required": True,
            "removable": True,
        },
    ]
    resp = await http_client.patch(
        "/api/leadgen/config", headers=hc_headers, json={"questionnaire": questionnaire}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _valid_payload(**overrides) -> dict:
    payload = {
        "consent_ack": True,
        "full_name": "Jane Doe",
        "age": "34",
        "email": "jane@example.com",
        "phone": "9876543210",
        "primary_health_goal": "Weight loss",
        "current_health_concerns": "None",
        "diet_type": "Vegetarian",
        "energy_level": 7,
    }
    payload.update(overrides)
    return payload


async def test_successful_submission_creates_lead_and_all_response_rows(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    resp = await http_client.post(f"/api/intake/{config['hc_slug']}", json=_valid_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "questionnaire_submitted"
    lead_id = UUID(body["lead_id"])

    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.hc_user_id == hc_user.id
    assert lead.full_name == "Jane Doe"
    assert lead.email == "jane@example.com"
    assert lead.phone == "9876543210"
    assert lead.status == "questionnaire_submitted"

    responses = (await db.execute(
        select(LeadQuestionnaireResponse).where(LeadQuestionnaireResponse.lead_id == lead_id)
    )).scalars().all()
    assert len(responses) == len(config["questionnaire"])
    by_key = {r.question_key: r for r in responses}
    assert by_key["full_name"].response_text == "Jane Doe"
    assert by_key["full_name"].question_text == "Full name"  # verbatim from config
    assert by_key["diet_type"].response_text == "Vegetarian"
    assert by_key["energy_level"].response_text == "7"


async def test_consent_fields_set_on_lead_row_in_same_transaction(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    resp = await http_client.post(f"/api/intake/{config['hc_slug']}", json=_valid_payload())
    assert resp.status_code == 201, resp.text

    lead = await db.get(Lead, UUID(resp.json()["lead_id"]))
    assert lead.consent_given_at is not None
    assert lead.consent_purpose == (
        "Your responses will be shared only with Asha Rao for the purpose of your "
        "initial health consultation. We do not share your information with any third "
        "party."
    )


async def test_missing_required_question_returns_422(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)
    payload = _valid_payload()
    del payload["primary_health_goal"]

    resp = await http_client.post(f"/api/intake/{config['hc_slug']}", json=payload)
    assert resp.status_code == 422


async def test_invalid_multiple_choice_answer_returns_422(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    resp = await http_client.post(
        f"/api/intake/{config['hc_slug']}", json=_valid_payload(diet_type="Carnivore")
    )
    assert resp.status_code == 422


async def test_out_of_range_scale_answer_returns_422(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    resp = await http_client.post(
        f"/api/intake/{config['hc_slug']}", json=_valid_payload(energy_level=11)
    )
    assert resp.status_code == 422


async def test_non_integer_scale_answer_returns_422(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    resp = await http_client.post(
        f"/api/intake/{config['hc_slug']}", json=_valid_payload(energy_level="high")
    )
    assert resp.status_code == 422


async def test_missing_consent_ack_returns_422(http_client: AsyncClient, hc_user, hc_headers, db):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)
    payload = _valid_payload()
    del payload["consent_ack"]

    resp = await http_client.post(f"/api/intake/{config['hc_slug']}", json=payload)
    assert resp.status_code == 422


async def test_false_consent_ack_returns_422(http_client: AsyncClient, hc_user, hc_headers, db):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    resp = await http_client.post(
        f"/api/intake/{config['hc_slug']}", json=_valid_payload(consent_ack=False)
    )
    assert resp.status_code == 422


async def test_duplicate_email_returns_409_with_spec_message(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)
    payload = _valid_payload()

    first = await http_client.post(f"/api/intake/{config['hc_slug']}", json=payload)
    assert first.status_code == 201, first.text

    second = await http_client.post(f"/api/intake/{config['hc_slug']}", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == (
        "Our records show you've already submitted your intake form for this coach. "
        "If you have questions, please contact Asha Rao directly."
    )

    # No duplicate leads row — only the original submission persisted.
    leads = (await db.execute(select(Lead).where(Lead.email == "jane@example.com"))).scalars().all()
    assert len(leads) == 1


async def test_submission_transaction_is_atomic_on_mid_flow_failure(
    http_client: AsyncClient, hc_user, hc_headers, db, monkeypatch
):
    """Forces a genuine FK-violation IntegrityError on one LeadQuestionnaireResponse
    insert (not the email-uniqueness constraint) after the Lead row has already been
    flushed mid-transaction. Confirms the whole transaction rolls back — no orphaned
    Lead row survives even though it was flushed to the DB before the failure was
    triggered, and no LeadQuestionnaireResponse rows persist either."""
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    original_add = db.add

    def _add_with_fk_violation(instance, *args, **kwargs):
        if isinstance(instance, LeadQuestionnaireResponse) and instance.question_key == "phone":
            instance.lead_id = uuid_mod.uuid4()  # references no existing lead -> FK violation
        return original_add(instance, *args, **kwargs)

    monkeypatch.setattr(db, "add", _add_with_fk_violation)

    with pytest.raises(Exception):  # noqa: B017 — unhandled IntegrityError propagates through the test client
        await http_client.post(f"/api/intake/{config['hc_slug']}", json=_valid_payload())

    leads = (await db.execute(select(Lead).where(Lead.email == "jane@example.com"))).scalars().all()
    assert leads == []
    responses = (await db.execute(select(LeadQuestionnaireResponse))).scalars().all()
    assert responses == []


async def test_unconfigured_slug_returns_404_not_422(http_client: AsyncClient):
    resp = await http_client.post(
        "/api/intake/this-slug-does-not-exist-00000",
        json={"consent_ack": True, "full_name": "Jane Doe"},
    )
    assert resp.status_code == 404


async def test_sixth_submission_within_an_hour_from_same_ip_returns_429(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """SPEC-0001 acceptance criterion: 6th submission from the same IP within 1 hour
    returns 429. This runs against the real registered `app` (via `http_client`,
    which wraps `src.main.app` — the same app object that has `app.state.limiter`
    and the `RateLimitExceeded` handler wired in `main.py`), not a throwaway test
    app, so it proves the `@limiter.limit("5/hour")` decorator on the real route is
    genuinely enforced end-to-end. Each request uses a distinct email so the 6th
    request is rejected for rate-limiting specifically, not the duplicate-email 409
    path. `httpx.ASGITransport`'s default fake client IP is the same for every
    request in this test, so all six land in the same rate-limit bucket.
    `reset_rate_limiter` (autouse, tests/conftest.py) guarantees this test starts
    with a clean bucket regardless of test execution order."""
    config = await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)

    for i in range(5):
        resp = await http_client.post(
            f"/api/intake/{config['hc_slug']}",
            json=_valid_payload(email=f"lead{i}@example.com"),
        )
        assert resp.status_code == 201, f"request {i + 1} failed: {resp.text}"

    sixth = await http_client.post(
        f"/api/intake/{config['hc_slug']}",
        json=_valid_payload(email="lead-sixth@example.com"),
    )
    assert sixth.status_code == 429, sixth.text
    assert "detail" in sixth.json()
