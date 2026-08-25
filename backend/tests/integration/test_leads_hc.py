"""Integration tests for HC-facing Lead test-recommendation endpoints.
Unit_003 PHASE-04 Task 5:
  GET  /api/leads/:id/test-recommendation
  POST /api/leads/:id/test-recommendation/send
"""
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Lead, LeadQuestionnaireResponse, User
from tests.integration.conftest import auth_headers

pytestmark = pytest.mark.asyncio

# This codebase's established convention for mocking outbound email in an
# integration test (see tests/integration/test_intake_public.py's
# `_PATCH_REVIEW_EMAIL`): patch the name as imported into the api module, not
# the definition in src.lib.email — leads.py imports it at module level.
_PATCH_SEND_EMAIL = "src.api.leads.send_finalized_test_recommendation_email"

_DRAFT = {
    "standard": ["CBC", "HbA1c", "TSH"],
    "additions": [
        {"test": "Vitamin D", "rationale": "Lead reports fatigue and low sun exposure."},
    ],
    "all_tests": ["CBC", "HbA1c", "TSH", "Vitamin D"],
}


# ── fixtures / helpers ───────────────────────────────────────────────────────


async def _make_lead(
    db: AsyncSession,
    hc_user: User,
    *,
    draft_test_recommendation: dict | None = _DRAFT,
    status_: str = "tests_drafted",
) -> Lead:
    lead = Lead(
        hc_user_id=hc_user.id,
        full_name="Jane Doe",
        email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
        phone="+91-9876543210",
        status=status_,
        draft_test_recommendation=draft_test_recommendation,
    )
    db.add(lead)
    await db.flush()
    db.add(LeadQuestionnaireResponse(
        lead_id=lead.id,
        question_key="current_health_concerns",
        question_text="Any current health concerns?",
        response_text="Fatigue, low energy in the afternoons",
    ))
    db.add(LeadQuestionnaireResponse(
        lead_id=lead.id,
        question_key="sleep_quality",
        question_text="How is your sleep quality?",
        response_text=None,
    ))
    await db.flush()
    return lead


async def _set_hc_name(
    db: AsyncSession, hc_user: User, first: str = "Asha", last: str = "Rao"
) -> None:
    hc_user.first_name = first
    hc_user.last_name = last
    await db.commit()


# ── GET /api/leads/:id/test-recommendation ──────────────────────────────────


async def test_get_happy_path_returns_lead_summary_and_draft(
    http_client, hc_headers, hc_user, db
):
    lead = await _make_lead(db, hc_user)

    r = await http_client.get(f"/api/leads/{lead.id}/test-recommendation", headers=hc_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["lead_id"] == str(lead.id)
    assert body["full_name"] == "Jane Doe"
    assert body["status"] == "tests_drafted"
    assert body["ready"] is True

    qa_keys = {qa["question_key"] for qa in body["questionnaire_responses"]}
    assert qa_keys == {"current_health_concerns", "sleep_quality"}
    unanswered = next(
        qa for qa in body["questionnaire_responses"] if qa["question_key"] == "sleep_quality"
    )
    assert unanswered["response_text"] is None

    assert body["draft_test_recommendation"] == _DRAFT


async def test_get_cross_tenant_returns_404_not_403(
    http_client, hc_headers, hc2_headers, hc_user, db
):
    lead = await _make_lead(db, hc_user)

    r = await http_client.get(f"/api/leads/{lead.id}/test-recommendation", headers=hc2_headers)
    assert r.status_code == 404


async def test_get_nonexistent_lead_returns_404(http_client, hc_headers):
    r = await http_client.get(f"/api/leads/{uuid.uuid4()}/test-recommendation", headers=hc_headers)
    assert r.status_code == 404


async def test_get_null_draft_returns_structured_not_ready_not_500(
    http_client, hc_headers, hc_user, db
):
    lead = await _make_lead(
        db, hc_user, draft_test_recommendation=None, status_="questionnaire_submitted"
    )

    r = await http_client.get(f"/api/leads/{lead.id}/test-recommendation", headers=hc_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is False
    assert body["draft_test_recommendation"] is None
    # Lead summary + questionnaire responses are still present even when not ready.
    assert body["full_name"] == "Jane Doe"
    assert len(body["questionnaire_responses"]) == 2


async def test_get_requires_auth(http_client, hc_user, db):
    lead = await _make_lead(db, hc_user)
    r = await http_client.get(f"/api/leads/{lead.id}/test-recommendation")
    assert r.status_code == 401


async def test_get_requires_hc_role(http_client, hc_user, db):
    lead = await _make_lead(db, hc_user)
    client_headers = auth_headers(hc_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.get(f"/api/leads/{lead.id}/test-recommendation", headers=client_headers)
    assert r.status_code == 403


# ── POST /api/leads/:id/test-recommendation/send ────────────────────────────


async def test_send_no_edits_passes_draft_additions_through_verbatim(
    http_client, hc_headers, hc_user, db
):
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    payload = {"additions": _DRAFT["additions"]}
    with patch(_PATCH_SEND_EMAIL) as mock_email:
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send", headers=hc_headers, json=payload
        )
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["status"] == "tests_recommended"
    assert body["test_recommendation"]["additions"] == _DRAFT["additions"]
    assert body["test_recommendation"]["standard"] == _DRAFT["standard"]
    assert body["test_recommendation"]["all_tests"] == _DRAFT["all_tests"]
    mock_email.assert_called_once()


async def test_send_with_hc_edits_wins_over_raw_draft(http_client, hc_headers, hc_user, db):
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    edited_additions = [{"test": "Iron Panel", "rationale": "HC's own clinical judgment call."}]
    with patch(_PATCH_SEND_EMAIL):
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": edited_additions},
        )
    assert r.status_code == 201, r.text
    body = r.json()

    # The HC's edited list wins — the raw AI draft's "Vitamin D" addition must
    # NOT survive into the finalized recommendation.
    assert body["test_recommendation"]["additions"] == edited_additions
    assert "Vitamin D" not in body["test_recommendation"]["all_tests"]
    assert body["test_recommendation"]["all_tests"] == ["CBC", "HbA1c", "TSH", "Iron Panel"]
    # standard is still carried over verbatim from the draft, untouched by the edit.
    assert body["test_recommendation"]["standard"] == _DRAFT["standard"]


async def test_send_dedupes_all_tests_first_seen_order(http_client, hc_headers, hc_user, db):
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    # One addition duplicates a standard test (CBC) and another duplicates
    # itself within the additions list — both must collapse to a single
    # first-seen entry in all_tests, while `additions` itself is untouched.
    additions = [
        {"test": "CBC", "rationale": "Already in standard, HC re-added by habit."},
        {"test": "Iron Panel", "rationale": "New addition."},
        {"test": "Iron Panel", "rationale": "Accidentally duplicated by the HC."},
    ]
    with patch(_PATCH_SEND_EMAIL):
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": additions},
        )
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["test_recommendation"]["all_tests"] == ["CBC", "HbA1c", "TSH", "Iron Panel"]
    # Raw additions list is preserved as submitted (not deduped) — matches
    # Task 3's own discipline: only all_tests is deduplicated.
    assert body["test_recommendation"]["additions"] == additions


async def test_send_cross_tenant_returns_404(http_client, hc2_headers, hc_user, db):
    lead = await _make_lead(db, hc_user)
    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send",
        headers=hc2_headers,
        json={"additions": []},
    )
    assert r.status_code == 404


async def test_send_triggers_lead_facing_email_with_correct_args(
    http_client, hc_headers, hc_user, db
):
    await _set_hc_name(db, hc_user, first="Asha", last="Rao")
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_SEND_EMAIL) as mock_email:
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": _DRAFT["additions"]},
        )
    assert r.status_code == 201, r.text

    mock_email.assert_called_once_with(
        to=lead.email,
        lead_name="Jane Doe",
        hc_name="Asha Rao",
        test_list=_DRAFT["all_tests"],
    )


async def test_send_email_failure_does_not_fail_the_request(http_client, hc_headers, hc_user, db):
    """The primary action (persisting `test_recommendation` + status) must
    already be durably committed before the email is attempted, and a raised
    exception from the email call must not turn this into an error response —
    same non-blocking contract as src/api/intake.py's HC-email call."""
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_SEND_EMAIL, side_effect=RuntimeError("resend down")):
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": _DRAFT["additions"]},
        )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "tests_recommended"

    await db.refresh(lead)
    assert lead.status == "tests_recommended"
    assert lead.test_recommendation["all_tests"] == _DRAFT["all_tests"]


async def test_send_requires_auth(http_client, hc_user, db):
    lead = await _make_lead(db, hc_user)
    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send", json={"additions": []}
    )
    assert r.status_code == 401


async def test_send_requires_hc_role(http_client, hc_user, db):
    lead = await _make_lead(db, hc_user)
    client_headers = auth_headers(hc_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send",
        headers=client_headers,
        json={"additions": []},
    )
    assert r.status_code == 403


async def test_send_with_null_draft_returns_409_not_500(http_client, hc_headers, hc_user, db):
    lead = await _make_lead(
        db, hc_user, draft_test_recommendation=None, status_="questionnaire_submitted"
    )
    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send",
        headers=hc_headers,
        json={"additions": []},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "draft_not_ready"


# ── Idempotency: double-Send is allowed, second call wins ───────────────────


async def test_double_send_overwrites_and_resends_email(http_client, hc_headers, hc_user, db):
    """Deliberate idempotency decision (see leads.py docstring): a second Send
    is not blocked. It overwrites `test_recommendation` with whatever the
    second call submits, and re-sends the Lead email."""
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    first_additions = [{"test": "Vitamin D", "rationale": "First send."}]
    second_additions = [
        {"test": "Vitamin B12", "rationale": "HC corrected the panel after the first send."}
    ]

    with patch(_PATCH_SEND_EMAIL) as mock_email:
        r1 = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": first_additions},
        )
        assert r1.status_code == 201, r1.text

        r2 = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": second_additions},
        )
        assert r2.status_code == 201, r2.text

    # Second call is not rejected, and its edits win — the first call's
    # additions do not linger in the final persisted state.
    body2 = r2.json()
    assert body2["test_recommendation"]["additions"] == second_additions
    assert "Vitamin B12" in body2["test_recommendation"]["all_tests"]
    assert "Vitamin D" not in body2["test_recommendation"]["all_tests"]

    # Email fired once per Send — not suppressed on the second call.
    assert mock_email.call_count == 2
