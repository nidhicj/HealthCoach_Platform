"""Integration tests for generate_lead_test_recommendation(). PHASE-04 Task 2.

generate_lead_test_recommendation() has no HTTP endpoint yet (that's PHASE-04 Task
3), so these tests call the function directly against a real (savepoint-isolated)
DB session, mocking the OpenRouter HTTP call the same way
test_lead_brief_generation.py does for generate_lead_brief().
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import HcLeadgenConfig, Lead, LeadQuestionnaireResponse, User
from src.llm_service import generate_lead_test_recommendation

pytestmark = pytest.mark.asyncio

_VALID_ADDITIONS_JSON = json.dumps({
    "additions": [
        {
            "test": "Hormonal Panel (LH, FSH, AMH)",
            "rationale": "Lead reports irregular periods and a PCOD diagnosis.",
        },
    ],
})

_VALID_EMPTY_ADDITIONS_JSON = json.dumps({"additions": []})


def _mock_http(content: str, model: str = "meta-llama/llama-3.3-70b-instruct:free") -> AsyncMock:
    """Same helper pattern as test_lead_brief_generation.py."""
    response_data = {
        "id": "gen-lead-test-rec-abc123",
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 110, "completion_tokens": 60},
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
async def leadgen_config(db: AsyncSession, hc_user: User) -> HcLeadgenConfig:
    cfg = HcLeadgenConfig(
        hc_user_id=hc_user.id,
        hc_slug=f"hc-{uuid.uuid4().hex[:8]}",
        questionnaire=[],
        test_panel={
            "standard_tests": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
            "condition_rules": [],
        },
    )
    db.add(cfg)
    await db.flush()
    return cfg


@pytest_asyncio.fixture()
async def lead(db: AsyncSession, hc_user: User, leadgen_config: HcLeadgenConfig) -> Lead:
    rec = Lead(
        hc_user_id=hc_user.id,
        full_name="Jane Doe",
        email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
        status="questionnaire_submitted",
        test_recommendation={
            "standard": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
            "additions": [],
            "all_tests": ["CBC", "HbA1c", "TSH", "Lipid Profile"],
        },
    )
    db.add(rec)
    await db.flush()
    db.add(LeadQuestionnaireResponse(
        lead_id=rec.id,
        question_key="current_health_concerns",
        question_text="What are your current health concerns?",
        response_text="Diagnosed with PCOD last year, irregular periods",
    ))
    db.add(LeadQuestionnaireResponse(
        lead_id=rec.id,
        question_key="sleep_quality",
        question_text="How is your sleep quality?",
        response_text=None,  # unanswered — must render as "(not answered)", not crash
    ))
    await db.flush()
    return rec


async def _llm_calls_row(db: AsyncSession) -> sa.Row | None:
    result = await db.execute(
        sa.text(
            "SELECT use_case, error_message, validation_failed, hc_user_id, client_id, session_id "
            "FROM llm_calls WHERE use_case = 'lead_test_recommendation' ORDER BY id DESC LIMIT 1"
        )
    )
    return result.first()


# ── Success path ─────────────────────────────────────────────────────────────


async def test_success_returns_additions_and_writes_llm_calls_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    mock_http = _mock_http(_VALID_ADDITIONS_JSON)
    with patch("src.llm_service.client.make_http_client", return_value=mock_http):
        result = await generate_lead_test_recommendation(
            db, lead_id=lead.id, hc_user_id=hc_user.id
        )

    assert result == [
        {
            "test": "Hormonal Panel (LH, FSH, AMH)",
            "rationale": "Lead reports irregular periods and a PCOD diagnosis.",
        },
    ]
    # Return shape must be exactly {"test", "rationale"} per dict, nothing else.
    for item in result:
        assert set(item.keys()) == {"test", "rationale"}

    row = await _llm_calls_row(db)
    assert row is not None
    assert row.use_case == "lead_test_recommendation"
    assert row.error_message is None
    assert row.validation_failed is False
    assert str(row.hc_user_id) == str(hc_user.id)
    assert row.client_id is None
    assert row.session_id is None


async def test_success_empty_additions_is_valid(db: AsyncSession, hc_user: User, lead: Lead):
    """An empty additions list is a valid, common success outcome — not a failure."""
    mock_http = _mock_http(_VALID_EMPTY_ADDITIONS_JSON)
    with patch("src.llm_service.client.make_http_client", return_value=mock_http):
        result = await generate_lead_test_recommendation(
            db, lead_id=lead.id, hc_user_id=hc_user.id
        )

    assert result == []

    row = await _llm_calls_row(db)
    assert row is not None
    assert row.error_message is None
    assert row.validation_failed is False


# ── Failure paths — must never raise ────────────────────────────────────────


async def test_llm_exception_returns_none_and_writes_error_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    broken_call = AsyncMock(side_effect=RuntimeError("openrouter down"))
    with patch("src.llm_service.call_openrouter", broken_call):
        result = await generate_lead_test_recommendation(
            db, lead_id=lead.id, hc_user_id=hc_user.id
        )

    assert result is None

    row = await _llm_calls_row(db)
    assert row is not None
    assert row.use_case == "lead_test_recommendation"
    assert row.error_message is not None
    assert "openrouter down" in row.error_message


async def test_validation_failure_returns_none_and_writes_error_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    """LLM returns unparseable content on both the initial call and the retry —
    parse_or_retry reports validation_failed, and the function must not raise."""
    mock_http = _mock_http("not valid json at all")
    with patch("src.llm_service.client.make_http_client", return_value=mock_http):
        result = await generate_lead_test_recommendation(
            db, lead_id=lead.id, hc_user_id=hc_user.id
        )

    assert result is None

    row = await _llm_calls_row(db)
    assert row is not None
    assert row.use_case == "lead_test_recommendation"
    assert row.error_message is not None
    assert row.validation_failed is True


async def test_lead_not_found_returns_none_without_raising(
    db: AsyncSession, hc_user: User, leadgen_config: HcLeadgenConfig
):
    """Caller is expected to have already resolved the Lead — but this function
    must still never raise even if that invariant is somehow violated."""
    missing_lead_id = uuid.uuid4()
    result = await generate_lead_test_recommendation(
        db, lead_id=missing_lead_id, hc_user_id=hc_user.id
    )
    assert result is None

    row = await _llm_calls_row(db)
    assert row is not None
    assert row.use_case == "lead_test_recommendation"
    assert row.error_message is not None
    assert "Lead not found" in row.error_message


async def test_missing_leadgen_config_returns_none_without_raising(
    db: AsyncSession, hc_user: User
):
    """No HcLeadgenConfig row for this hc_user_id (edge case — should not happen in
    practice since Stage 2 requires config to exist, but the function must still
    never raise if it does)."""
    rec = Lead(
        hc_user_id=hc_user.id,
        full_name="Jane Doe",
        email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
        status="questionnaire_submitted",
    )
    db.add(rec)
    await db.flush()

    result = await generate_lead_test_recommendation(
        db, lead_id=rec.id, hc_user_id=hc_user.id
    )
    assert result is None

    row = await _llm_calls_row(db)
    assert row is not None
    assert row.error_message is not None
    assert "HcLeadgenConfig not found" in row.error_message


async def test_missing_prompt_file_returns_none_and_writes_error_row(
    db: AsyncSession, hc_user: User, lead: Lead
):
    """Regression test for the PHASE-03 Task 3 review finding, applied here on the
    second attempt at this exact pattern: get_llm_config()/load_prompt() must run
    INSIDE the try: block, not before it — otherwise a missing/corrupt
    prompts/lead_test_recommendation.md or a bad llm_config.yaml would raise
    straight out of generate_lead_test_recommendation(), violating the "never
    raise" contract (this function's caller is the public, unauthenticated
    POST /api/intake/:slug). This test mocks load_prompt to raise and proves the
    failure is caught and an llm_calls row is still written — i.e. that the
    pre-try-block bug class is actually closed here, not just assumed closed by
    copying the pattern from generate_lead_brief."""
    with patch(
        "src.llm_service.load_prompt",
        side_effect=FileNotFoundError("prompts/lead_test_recommendation.md not found"),
    ):
        result = await generate_lead_test_recommendation(
            db, lead_id=lead.id, hc_user_id=hc_user.id
        )

    assert result is None

    row = await _llm_calls_row(db)
    assert row is not None
    assert row.use_case == "lead_test_recommendation"
    assert row.error_message is not None
    assert "prompts/lead_test_recommendation.md not found" in row.error_message
