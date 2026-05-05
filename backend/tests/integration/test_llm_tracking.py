"""Integration tests for LLM call tracking (llm_calls table with pgcrypto)."""
import uuid

import pytest
import sqlalchemy as sa

from src.llm_service.tracking import write_llm_call


@pytest.mark.asyncio
async def test_write_llm_call_creates_row(db, hc_user):
    call_id = await write_llm_call(
        db,
        hc_user_id=hc_user.id,
        client_id=None,
        session_id=None,
        use_case="mom_generation",
        prompt_version="1.0.0",
        model_requested="meta-llama/llama-3.3-70b-instruct:free",
        model_served="meta-llama/llama-3.3-70b-instruct:free",
        fallback_count=0,
        input_tokens=120,
        output_tokens=200,
        latency_ms=1500,
        validation_failed=False,
        snippet_count=2,
        snippet_tokens=350,
        inr_cost_estimate=None,
        raw_request_id="or-abc123",
        error_message=None,
        prompt_text="You are a health coach. Draft MOM for CP0001.",
        completion_text='{"summary": "Good session"}',
        request_id=uuid.uuid4(),
    )
    assert call_id is not None

    # Verify the row exists and metadata is readable
    result = await db.execute(
        sa.text("SELECT model_requested, fallback_count, validation_failed FROM llm_calls WHERE id = :id"),
        {"id": call_id},
    )
    row = result.first()
    assert row is not None
    assert row.model_requested == "meta-llama/llama-3.3-70b-instruct:free"
    assert row.fallback_count == 0
    assert row.validation_failed is False


@pytest.mark.asyncio
async def test_write_llm_call_encrypts_prompt_text(db, hc_user):
    prompt = "Test prompt for encryption check"
    call_id = await write_llm_call(
        db,
        hc_user_id=hc_user.id,
        client_id=None,
        session_id=None,
        use_case="mom_generation",
        prompt_version="1.0.0",
        model_requested="meta-llama/llama-3.3-70b-instruct:free",
        model_served="meta-llama/llama-3.3-70b-instruct:free",
        fallback_count=0,
        input_tokens=10,
        output_tokens=10,
        latency_ms=100,
        validation_failed=False,
        snippet_count=0,
        snippet_tokens=0,
        inr_cost_estimate=None,
        raw_request_id=None,
        error_message=None,
        prompt_text=prompt,
        completion_text="{}",
        request_id=None,
    )
    # The raw stored bytes should NOT be the plain text
    result = await db.execute(
        sa.text("SELECT prompt_text FROM llm_calls WHERE id = :id"),
        {"id": call_id},
    )
    row = result.first()
    stored_bytes = row.prompt_text
    # Encrypted bytes should not decode to the original prompt
    assert stored_bytes is not None
    try:
        decoded = stored_bytes.decode("utf-8")
        assert decoded != prompt
    except UnicodeDecodeError:
        pass  # Encrypted bytes can't even be decoded — good


@pytest.mark.asyncio
async def test_write_llm_call_failure_row(db, hc_user):
    call_id = await write_llm_call(
        db,
        hc_user_id=hc_user.id,
        client_id=None,
        session_id=None,
        use_case="mom_generation",
        prompt_version="1.0.0",
        model_requested="meta-llama/llama-3.3-70b-instruct:free",
        model_served=None,
        fallback_count=0,
        input_tokens=0,
        output_tokens=0,
        latency_ms=300,
        validation_failed=False,
        snippet_count=0,
        snippet_tokens=0,
        inr_cost_estimate=None,
        raw_request_id=None,
        error_message="OpenRouter 401 Unauthorized",
        prompt_text="",
        completion_text="",
        request_id=None,
    )
    result = await db.execute(
        sa.text("SELECT error_message, model_served FROM llm_calls WHERE id = :id"),
        {"id": call_id},
    )
    row = result.first()
    assert row.error_message == "OpenRouter 401 Unauthorized"
    assert row.model_served is None


@pytest.mark.asyncio
async def test_write_llm_call_validation_failed(db, hc_user):
    call_id = await write_llm_call(
        db,
        hc_user_id=hc_user.id,
        client_id=None,
        session_id=None,
        use_case="mom_generation",
        prompt_version="1.0.0",
        model_requested="meta-llama/llama-3.3-70b-instruct:free",
        model_served="meta-llama/llama-3.3-70b-instruct:free",
        fallback_count=0,
        input_tokens=100,
        output_tokens=50,
        latency_ms=800,
        validation_failed=True,
        snippet_count=0,
        snippet_tokens=0,
        inr_cost_estimate=None,
        raw_request_id=None,
        error_message="Schema validation failed: missing field 'summary'",
        prompt_text="prompt",
        completion_text="not valid json",
        request_id=None,
    )
    result = await db.execute(
        sa.text("SELECT validation_failed FROM llm_calls WHERE id = :id"),
        {"id": call_id},
    )
    row = result.first()
    assert row.validation_failed is True
