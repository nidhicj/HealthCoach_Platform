"""Integration tests for generate_lead_brief(). PHASE-03 Task 3.

generate_lead_brief() has no HTTP endpoint yet (that's a later PHASE-03 task), so
these tests call the function directly against a real (savepoint-isolated) DB
session, mocking the OpenRouter HTTP call the same way test_mom_draft.py and
test_brief_extended.py do for generate_mom_draft()/generate_brief().
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Lead, LeadQuestionnaireResponse, User
from src.llm_service import generate_lead_brief

pytestmark = pytest.mark.asyncio

_VALID_LEAD_BRIEF_JSON = json.dumps({
    "questionnaire_findings": "Lead reports low energy and irregular sleep.",
    "blood_report_highlights": "TSH slightly elevated at 5.2 mIU/L.",
    "suggested_discussion_points": ["Discuss sleep hygiene", "Review thyroid history"],
    "flags": ["elevated_tsh"],
})


def _mock_http(content: str, model: str = "meta-llama/llama-3.3-70b-instruct:free") -> AsyncMock:
    """Same helper pattern as test_mom_draft.py / test_brief_extended.py."""
    response_data = {
        "id": "gen-lead-brief-abc123",
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 90},
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_data
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_resp)
    return mock_http


@pytest_asyncio.fixture()
async def lead(db: AsyncSession, hc_user: User) -> Lead:
    rec = Lead(
        hc_user_id=hc_user.id,
        full_name="Jane Doe",
        email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
        status="questionnaire_submitted",
        test_recommendation={"standard": ["CBC"], "additions": [], "all_tests": ["CBC"]},
    )
    db.add(rec)
    await db.flush()
    db.add(LeadQuestionnaireResponse(
        lead_id=rec.id,
        question_key="energy_level",
        question_text="How is your energy level?",
        response_text="Low most days",
    ))
    db.add(LeadQuestionnaireResponse(
        lead_id=rec.id,
        question_key="sleep_quality",
        question_text="How is your sleep quality?",
        response_text=None,  # unanswered — must render as "(not answered)", not crash
    ))
    await db.flush()
    return rec


async def _llm_calls_row(db: AsyncSession, lead_id: uuid.UUID) -> sa.Row | None:
    result = await db.execute(
        sa.text(
            "SELECT use_case, error_message, validation_failed, hc_user_id, client_id, session_id "
            "FROM llm_calls WHERE use_case = 'lead_brief' ORDER BY id DESC LIMIT 1"
        )
    )
    return result.first()


# ── Success path ─────────────────────────────────────────────────────────────


async def test_success_returns_brief_text_and_writes_llm_calls_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    mock_http = _mock_http(_VALID_LEAD_BRIEF_JSON)
    with patch("src.llm_service.client.make_http_client", return_value=mock_http):
        brief_text, llm_call_id = await generate_lead_brief(
            db, lead_id=lead.id, hc_user_id=hc_user.id, blood_report_text="Hemoglobin: 13.5 g/dL"
        )

    assert brief_text is not None
    assert llm_call_id is not None
    assert "QUESTIONNAIRE FINDINGS:" in brief_text
    assert "Lead reports low energy" in brief_text
    assert "elevated_tsh" in brief_text

    row = await _llm_calls_row(db, lead.id)
    assert row is not None
    assert row.use_case == "lead_brief"
    assert row.error_message is None
    assert row.validation_failed is False
    assert str(row.hc_user_id) == str(hc_user.id)
    assert row.client_id is None
    assert row.session_id is None


async def test_success_handles_empty_blood_report_text(db: AsyncSession, hc_user: User, lead: Lead):
    """Empty blood_report_text (no accepted files extracted usable text) must not
    crash placeholder substitution or the LLM round trip."""
    mock_http = _mock_http(_VALID_LEAD_BRIEF_JSON)
    with patch("src.llm_service.client.make_http_client", return_value=mock_http):
        brief_text, llm_call_id = await generate_lead_brief(
            db, lead_id=lead.id, hc_user_id=hc_user.id, blood_report_text=""
        )

    assert brief_text is not None
    assert llm_call_id is not None


# ── Failure paths — D-2: must never raise ───────────────────────────────────


async def test_llm_exception_returns_none_none_and_writes_error_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    broken_call = AsyncMock(side_effect=RuntimeError("openrouter down"))
    with patch("src.llm_service.call_openrouter", broken_call):
        result = await generate_lead_brief(
            db, lead_id=lead.id, hc_user_id=hc_user.id, blood_report_text="some text"
        )

    assert result == (None, None)

    row = await _llm_calls_row(db, lead.id)
    assert row is not None
    assert row.use_case == "lead_brief"
    assert row.error_message is not None
    assert "openrouter down" in row.error_message


async def test_validation_failure_returns_none_none_and_writes_error_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    """LLM returns unparseable content on both the initial call and the retry —
    parse_or_retry reports validation_failed, and the function must not raise."""
    mock_http = _mock_http("not valid json at all")
    with patch("src.llm_service.client.make_http_client", return_value=mock_http):
        result = await generate_lead_brief(
            db, lead_id=lead.id, hc_user_id=hc_user.id, blood_report_text="some text"
        )

    assert result == (None, None)

    row = await _llm_calls_row(db, lead.id)
    assert row is not None
    assert row.use_case == "lead_brief"
    assert row.error_message is not None
    assert row.validation_failed is True


async def test_lead_not_found_returns_none_none_without_raising(db: AsyncSession, hc_user: User):
    """Caller is expected to have already resolved the Lead — but per D-2 this
    function must still never raise even if that invariant is somehow violated."""
    missing_lead_id = uuid.uuid4()
    result = await generate_lead_brief(
        db, lead_id=missing_lead_id, hc_user_id=hc_user.id, blood_report_text="some text"
    )
    assert result == (None, None)

    row = await _llm_calls_row(db, missing_lead_id)
    assert row is not None
    assert row.use_case == "lead_brief"
    assert row.error_message is not None
    assert "Lead not found" in row.error_message


async def test_missing_prompt_file_returns_none_none_and_writes_error_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    """Regression test for the Critical review finding: get_llm_config()/load_prompt()
    used to run before the try: block, so a missing/corrupt prompts/lead_brief.md or a
    bad llm_config.yaml would raise straight out of generate_lead_brief(), violating D-2
    (must NEVER raise). Both calls now happen inside the try:, and _write_failure_row
    tolerates prompt_file/models never having been assigned."""
    with patch(
        "src.llm_service.load_prompt",
        side_effect=FileNotFoundError("prompts/lead_brief.md not found"),
    ):
        result = await generate_lead_brief(
            db, lead_id=lead.id, hc_user_id=hc_user.id, blood_report_text="some text"
        )

    assert result == (None, None)

    row = await _llm_calls_row(db, lead.id)
    assert row is not None
    assert row.use_case == "lead_brief"
    assert row.error_message is not None
    assert "prompts/lead_brief.md not found" in row.error_message
