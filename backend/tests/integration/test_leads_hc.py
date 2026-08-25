"""Integration tests for HC-facing Lead test-recommendation endpoints.
Unit_003 PHASE-04 Task 5:
  GET  /api/leads/:id/test-recommendation
  POST /api/leads/:id/test-recommendation/send

PHASE-05 Task 4 (SPEC-0001 D-8) extended `POST .../send` to also mint (and,
on re-Send, invalidate-then-remint) this Lead's `LeadUploadToken`, and
extended the outbound email's signature with `pay_link`/`upload_link` — see
the "upload token minting" section below.
"""
import hashlib
import uuid
from unittest.mock import ANY, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Lead, LeadQuestionnaireResponse, LeadUploadToken, User
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


async def test_get_returns_null_test_recommendation_before_any_send(
    http_client, hc_headers, hc_user, db
):
    """Fix #1 (final-review-fix round): `test_recommendation` must be present
    on the response shape (null when nothing has been sent yet), not omitted
    — this is the field the frontend now branches on to decide what to seed
    its editor from."""
    lead = await _make_lead(db, hc_user)
    r = await http_client.get(f"/api/leads/{lead.id}/test-recommendation", headers=hc_headers)
    assert r.status_code == 200, r.text
    assert r.json()["test_recommendation"] is None


async def test_get_after_send_returns_finalized_panel_as_test_recommendation(
    http_client, hc_headers, hc_user, db
):
    """Fix #1 (final-review-fix round): once the HC has already Sent a panel,
    reopening the review screen must surface it via `test_recommendation` —
    the correct starting point for further edits — distinct from the
    original, unmodified `draft_test_recommendation`."""
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    edited_additions = [{"test": "Iron Panel", "rationale": "HC's own clinical judgment call."}]
    with patch(_PATCH_SEND_EMAIL):
        send_r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": edited_additions},
        )
    assert send_r.status_code == 201, send_r.text

    r = await http_client.get(f"/api/leads/{lead.id}/test-recommendation", headers=hc_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["test_recommendation"]["additions"] == edited_additions
    assert body["test_recommendation"]["all_tests"] == ["CBC", "HbA1c", "TSH", "Iron Panel"]
    # The raw AI draft is untouched by Send — still what Task 3 originally wrote.
    assert body["draft_test_recommendation"] == _DRAFT


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

    # PHASE-05 Task 4: signature grew `pay_link`/`upload_link` — asserted
    # precisely in test_send_email_receives_pay_and_upload_links_matching_
    # minted_token below (upload_link embeds a freshly random raw token that
    # can't be predicted here, so ANY stands in for both new kwargs in this
    # test, which is only about the pre-existing four).
    mock_email.assert_called_once_with(
        to=lead.email,
        lead_name="Jane Doe",
        hc_name="Asha Rao",
        test_list=_DRAFT["all_tests"],
        pay_link=ANY,
        upload_link=ANY,
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


async def test_send_with_status_past_review_stage_returns_409(http_client, hc_headers, hc_user, db):
    """Fix #2 (final-review-fix round): a Lead whose status has already
    advanced past the reviewable window (`tests_drafted` / `tests_recommended`)
    must be rejected — not silently walked backward to `tests_recommended` by
    a stale review-screen link still sitting in the HC's inbox. Only later
    SPEC-0001 statuses (unreachable in shipped code today) exercise this;
    `report_uploaded` stands in for "any later stage"."""
    lead = await _make_lead(db, hc_user, status_="report_uploaded")

    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send",
        headers=hc_headers,
        json={"additions": []},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "status_not_reviewable"

    # Status must not have been walked backward.
    await db.refresh(lead)
    assert lead.status == "report_uploaded"


async def test_send_strips_padded_test_name_before_storing_and_deduping(
    http_client, hc_headers, hc_user, db
):
    """Fix #3 (final-review-fix round): `TestAdditionIn._test_not_blank`
    validated the stripped value but returned the unstripped one — a padded
    name like " CBC " would defeat the exact-string dedup against the "CBC"
    standard-baseline entry and ship both variants to the Lead's email."""
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    additions = [{"test": " CBC ", "rationale": "Padded, duplicates the standard baseline."}]
    with patch(_PATCH_SEND_EMAIL):
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": additions},
        )
    assert r.status_code == 201, r.text
    body = r.json()

    # Stored stripped, not with its original padding.
    assert body["test_recommendation"]["additions"] == [
        {"test": "CBC", "rationale": "Padded, duplicates the standard baseline."}
    ]
    # Dedup against the standard baseline's "CBC" now actually takes effect —
    # "CBC" appears once, not as two variants ("CBC" and " CBC ").
    assert body["test_recommendation"]["all_tests"] == ["CBC", "HbA1c", "TSH"]


async def test_send_rejects_over_length_test_name(http_client, hc_headers, hc_user, db):
    """Fix #4 (final-review-fix round): `TestAdditionIn.test` has a 200-char
    bound (Pydantic `Field(max_length=200)`)."""
    lead = await _make_lead(db, hc_user)
    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send",
        headers=hc_headers,
        json={"additions": [{"test": "x" * 201, "rationale": "ok"}]},
    )
    assert r.status_code == 422


async def test_send_rejects_over_length_rationale(http_client, hc_headers, hc_user, db):
    """Fix #4 (final-review-fix round): `TestAdditionIn.rationale` has a
    2000-char bound (Pydantic `Field(max_length=2000)`)."""
    lead = await _make_lead(db, hc_user)
    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send",
        headers=hc_headers,
        json={"additions": [{"test": "CBC", "rationale": "x" * 2001}]},
    )
    assert r.status_code == 422


async def test_send_rejects_over_length_additions_list(http_client, hc_headers, hc_user, db):
    """Fix #4 (final-review-fix round): `SendTestRecommendationIn.additions`
    has a 50-item sanity cap (Pydantic `Field(max_length=50)`) — a Lead's test
    panel realistically never approaches this."""
    lead = await _make_lead(db, hc_user)
    additions = [{"test": f"Test {i}", "rationale": "r"} for i in range(51)]
    r = await http_client.post(
        f"/api/leads/{lead.id}/test-recommendation/send",
        headers=hc_headers,
        json={"additions": additions},
    )
    assert r.status_code == 422


async def test_send_falls_back_to_generic_hc_name_when_names_unset(
    http_client, hc_headers, hc_user, db
):
    """Fix #7 (final-review-fix round): if the HC's first/last name are both
    unset, `hc_name` must not render as an empty string in the Lead-facing
    email — falls back to a generic label. Unreachable via the product flow
    today (Stage 1 leadgen setup gates on both names being present), but the
    endpoint must not depend on that to stay correct. `hc_user` here is used
    without `_set_hc_name`, so both names are null by construction."""
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_SEND_EMAIL) as mock_email:
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": _DRAFT["additions"]},
        )
    assert r.status_code == 201, r.text

    # PHASE-05 Task 4: see the ANY note in
    # test_send_triggers_lead_facing_email_with_correct_args above.
    mock_email.assert_called_once_with(
        to=lead.email,
        lead_name="Jane Doe",
        hc_name="Your Coach",
        test_list=_DRAFT["all_tests"],
        pay_link=ANY,
        upload_link=ANY,
    )


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


# ── PHASE-05 Task 4 (SPEC-0001 D-8): upload token minting on Send ───────────


async def test_send_mints_upload_token_with_null_expiry_and_used_at(
    http_client, hc_headers, hc_user, db
):
    """Send now mints the Lead's `LeadUploadToken` up front (no longer at
    intake time — that path was removed in PHASE-04). `expires_at` stays
    NULL until PHASE-05 Task 6's payment webhook activates it; `used_at`
    stays NULL until the Lead actually uploads (PHASE-03 Task 6)."""
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_SEND_EMAIL):
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": _DRAFT["additions"]},
        )
    assert r.status_code == 201, r.text

    tokens = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead.id)
    )).scalars().all()
    assert len(tokens) == 1
    assert tokens[0].expires_at is None
    assert tokens[0].used_at is None


async def test_send_email_receives_pay_and_upload_links_matching_minted_token(
    http_client, hc_headers, hc_user, db
):
    """`pay_link`/`upload_link` are constructed from the lead id / raw
    token, and the raw token embedded in `upload_link` hashes to exactly the
    `LeadUploadToken` row Send just minted — proves the Lead's email carries
    a link that actually resolves to the live DB row, not some other value."""
    await _set_hc_name(db, hc_user, first="Asha", last="Rao")
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_SEND_EMAIL) as mock_email:
        r = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": _DRAFT["additions"]},
        )
    assert r.status_code == 201, r.text

    mock_email.assert_called_once()
    kwargs = mock_email.call_args.kwargs
    assert kwargs["to"] == lead.email
    assert kwargs["lead_name"] == "Jane Doe"
    assert kwargs["hc_name"] == "Asha Rao"
    assert kwargs["test_list"] == _DRAFT["all_tests"]

    frontend_url = get_settings().frontend_url
    assert kwargs["pay_link"] == f"{frontend_url}/pay/{lead.id}"

    upload_prefix = f"{frontend_url}/upload/"
    assert kwargs["upload_link"].startswith(upload_prefix)
    raw_token = kwargs["upload_link"][len(upload_prefix):]
    assert len(raw_token) == 64  # os.urandom(32).hex()

    token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead.id)
    )).scalar_one()
    assert token_row.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()


async def test_second_send_invalidates_first_token_and_mints_fresh_one(
    http_client, hc_headers, hc_user, db
):
    """Re-send idempotency (PHASE-05 Task 4 brief, "Re-send idempotency"
    section): a second Send invalidates any prior unused `LeadUploadToken`
    row for this Lead (`used_at` set) before minting a fresh one — keeps
    "the Lead's live token" unambiguous for Task 6's payment webhook, and
    stops a stale link from an earlier email from being usable to upload a
    second time."""
    await _set_hc_name(db, hc_user)
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_SEND_EMAIL) as mock_email:
        r1 = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": _DRAFT["additions"]},
        )
        assert r1.status_code == 201, r1.text
        first_upload_link = mock_email.call_args.kwargs["upload_link"]

        r2 = await http_client.post(
            f"/api/leads/{lead.id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": _DRAFT["additions"]},
        )
        assert r2.status_code == 201, r2.text
        second_upload_link = mock_email.call_args.kwargs["upload_link"]

    # The email reflects the new link on the second Send, not the first.
    assert first_upload_link != second_upload_link

    tokens = (await db.execute(
        select(LeadUploadToken)
        .where(LeadUploadToken.lead_id == lead.id)
        .order_by(LeadUploadToken.created_at)
    )).scalars().all()
    assert len(tokens) == 2
    assert tokens[0].used_at is not None  # first token invalidated
    assert tokens[1].used_at is None  # only the fresh token is still unused
    assert tokens[1].expires_at is None
