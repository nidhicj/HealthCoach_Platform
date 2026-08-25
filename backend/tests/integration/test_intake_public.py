"""Integration tests: GET/POST /api/intake/:slug (public, unauthenticated).

PHASE-02 (original), PHASE-04 (Stage 3 replaced: AI-drafted test recommendation
+ HC review, rule-based recommendation/upload-token-issuance/immediate Lead
email removed).
"""
import uuid as uuid_mod
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import Lead, LeadQuestionnaireResponse, LeadUploadToken

# Every test below that drives a POST past Stage 2 (i.e. gets a 201, or a 409
# that required a prior successful 201) must mock both of these — this
# codebase's established convention (see `tests/integration/test_upload_public.py`'s
# `generate_lead_brief` patches) for any endpoint that calls into
# `src.llm_service`/`src.lib.email`: real API keys are present in this repo's
# local `.env` (`OPENROUTER_API_KEY`, `RESEND_API_KEY`), so an unmocked call
# would be a real, slow, non-deterministic network request, not a test double.
_PATCH_GENERATE = "src.llm_service.generate_lead_test_recommendation"
_PATCH_REVIEW_EMAIL = "src.api.intake.send_test_recommendation_review_email"

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

    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=None), \
         patch(_PATCH_REVIEW_EMAIL):
        resp = await http_client.post(f"/api/intake/{config['hc_slug']}", json=_valid_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Stage 3 (PHASE-04) fires inline in the same request/response cycle and
    # advances the Lead to "tests_drafted" before this response is built — the
    # response body must reflect that actual final state, not the pre-Stage-3
    # "questionnaire_submitted" snapshot (SPEC-0001 Stage 3 step 4).
    assert body["status"] == "tests_drafted"
    lead_id = UUID(body["lead_id"])

    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.hc_user_id == hc_user.id
    assert lead.full_name == "Jane Doe"
    assert lead.email == "jane@example.com"
    assert lead.phone == "9876543210"
    assert lead.status == "tests_drafted"

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

    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=None), \
         patch(_PATCH_REVIEW_EMAIL):
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

    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=None), \
         patch(_PATCH_REVIEW_EMAIL):
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

    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=None), \
         patch(_PATCH_REVIEW_EMAIL):
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


# ── Stage 3 orchestration (PHASE-04: AI-drafted test recommendation, HC review
# email) ──────────────────────────────────────────────────────────────────────


async def _configure_with_test_panel(
    http_client: AsyncClient, hc_user, hc_headers, db
) -> dict:
    """Extends `_configure_with_custom_questions` with a `test_panel` (standard
    baseline tests) via `PATCH /api/leadgen/config`, so Stage 3's
    `draft_test_recommendation` has a real HC-configured baseline to fall back
    to / build on top of."""
    await _configure_with_custom_questions(http_client, hc_user, hc_headers, db)
    resp = await http_client.patch(
        "/api/leadgen/config",
        headers=hc_headers,
        json={"test_panel": {"standard_tests": ["CBC", "HbA1c", "TSH", "Lipid Profile"]}},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_successful_submission_drafts_recommendation_from_ai_additions_and_emails_hc(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """AI drafting succeeds (mocked): `draft_test_recommendation` combines the
    HC's standard baseline with the AI's additions, status advances to
    `tests_drafted` (not `tests_recommended` — that only happens once the HC
    reviews and sends, per D-5/Task 5, not built by this endpoint), and the HC
    (not the Lead) receives the review-request email."""
    config = await _configure_with_test_panel(http_client, hc_user, hc_headers, db)
    ai_additions = [
        {"test": "Hormonal Panel (LH, FSH, AMH)", "rationale": "Lead reports PCOD symptoms"},
    ]

    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=ai_additions) as mock_gen, \
         patch(_PATCH_REVIEW_EMAIL) as mock_email:
        resp = await http_client.post(
            f"/api/intake/{config['hc_slug']}",
            json=_valid_payload(current_health_concerns="Diagnosed with PCOD last year"),
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Response body must report the Lead's actual final status, not the
    # pre-Stage-3 "questionnaire_submitted" snapshot.
    assert body["status"] == "tests_drafted"
    lead_id = UUID(body["lead_id"])
    mock_gen.assert_awaited_once()
    assert mock_gen.call_args.kwargs["lead_id"] == lead_id
    assert mock_gen.call_args.kwargs["hc_user_id"] == hc_user.id

    lead = await db.get(Lead, lead_id)
    assert lead.status == "tests_drafted"
    assert lead.draft_test_recommendation == {
        "standard": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
        "additions": ai_additions,
        "all_tests": [
            "CBC", "HbA1c", "TSH", "Lipid Profile", "Hormonal Panel (LH, FSH, AMH)"
        ],
    }
    # Never sent/exposed to the Lead by this endpoint (SPEC-0001 acceptance
    # criterion: draft is never visible to or sent to the Lead).
    assert lead.test_recommendation is None

    mock_email.assert_called_once()
    kwargs = mock_email.call_args.kwargs
    assert kwargs["to"] == hc_user.email
    assert kwargs["hc_name"] == "Asha Rao"
    assert kwargs["lead_name"] == "Jane Doe"
    assert kwargs["review_link"] == f"http://localhost:3000/leads/{lead_id}/test-recommendation"


async def test_ai_drafting_returns_none_falls_back_to_standard_baseline_only(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """AI drafting fails (returns None, its documented failure signal per Task 2's
    contract — never an exception). Per SPEC-0001's edge case, this is NOT a
    blocking failure: `draft_test_recommendation` falls back to the standard
    baseline with an empty `additions` list, `leads.status` still advances to
    `tests_drafted`, and the HC still gets the review email (so they know to
    build/send a panel manually)."""
    config = await _configure_with_test_panel(http_client, hc_user, hc_headers, db)

    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=None) as mock_gen, \
         patch(_PATCH_REVIEW_EMAIL) as mock_email:
        resp = await http_client.post(
            f"/api/intake/{config['hc_slug']}",
            json=_valid_payload(email="fallback-lead@example.com"),
        )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "tests_drafted"
    lead_id = UUID(resp.json()["lead_id"])
    mock_gen.assert_awaited_once()

    lead = await db.get(Lead, lead_id)
    assert lead.status == "tests_drafted"
    assert lead.draft_test_recommendation == {
        "standard": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
        "additions": [],
        "all_tests": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
    }

    mock_email.assert_called_once()  # HC still notified — can send a manual panel.


async def test_ai_drafting_raises_submission_still_succeeds_with_fallback_draft(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """The single most important regression this task exists to prevent: a
    Lead's questionnaire submission must succeed end-to-end (correct status
    code, `leads` row created) even if `generate_lead_test_recommendation`
    violates its own never-raise contract and actually raises. Defensive
    try/except at this call site (mirroring `src.api.upload`'s call to
    `generate_lead_brief`) must catch it and fall back exactly like the
    documented `None` case above — the Lead must never see a 500 because of
    an AI-drafting failure."""
    config = await _configure_with_test_panel(http_client, hc_user, hc_headers, db)

    with patch(
        _PATCH_GENERATE, new_callable=AsyncMock, side_effect=RuntimeError("openrouter outage"),
    ) as mock_gen, patch(_PATCH_REVIEW_EMAIL) as mock_email:
        resp = await http_client.post(
            f"/api/intake/{config['hc_slug']}",
            json=_valid_payload(email="resilient-lead@example.com"),
        )
    assert resp.status_code == 201, resp.text
    mock_gen.assert_awaited_once()

    body = resp.json()
    assert body["status"] == "tests_drafted"
    lead_id = UUID(body["lead_id"])

    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.status == "tests_drafted"
    assert lead.draft_test_recommendation == {
        "standard": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
        "additions": [],
        "all_tests": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
    }

    mock_email.assert_called_once()  # HC still notified, same as the documented-None case.

    # No lead_upload_tokens row — that issuance moved to PHASE-05 and no longer
    # happens anywhere in this endpoint.
    tokens = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead_id)
    )).scalars().all()
    assert tokens == []


async def test_review_email_delivery_failure_does_not_fail_request_and_draft_persists(
    http_client: AsyncClient, hc_user, hc_headers, db
):
    """Mirrors PHASE-02 Decision D-2 (non-blocking outbound email): an HC
    review-email send failure is caught and logged, never re-raised — the HTTP
    response still indicates success, and the already-committed Lead +
    `draft_test_recommendation` are not rolled back."""
    config = await _configure_with_test_panel(http_client, hc_user, hc_headers, db)
    ai_additions = [{"test": "Vitamin D", "rationale": "Reported fatigue"}]

    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=ai_additions), \
         patch(
             _PATCH_REVIEW_EMAIL, side_effect=RuntimeError("resend outage"),
         ) as mock_email:
        resp = await http_client.post(
            f"/api/intake/{config['hc_slug']}",
            json=_valid_payload(email="email-outage-lead@example.com"),
        )
    assert resp.status_code == 201, resp.text
    mock_email.assert_called_once()

    body = resp.json()
    # Even when the email send fails, the response status must still reflect
    # Stage 3's actual outcome (already committed before the email is attempted).
    assert body["status"] == "tests_drafted"
    lead_id = UUID(body["lead_id"])
    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.status == "tests_drafted"
    assert lead.draft_test_recommendation is not None
    assert lead.draft_test_recommendation["standard"] == ["CBC", "HbA1c", "TSH", "Lipid Profile"]
    assert lead.draft_test_recommendation["additions"] == ai_additions

    tokens = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead_id)
    )).scalars().all()
    assert tokens == []
