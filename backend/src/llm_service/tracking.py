"""Write LLM call records with pgcrypto-encrypted prompt/completion text. Per ADR-0003 §4."""
from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings

# Fallback key ensures pgp_sym_encrypt never receives an empty passphrase.
# In production, LLM_CALL_ENCRYPTION_KEY must be a strong random key.
_FALLBACK_KEY = "dev-only-placeholder-not-for-production"


async def write_llm_call(
    db: AsyncSession,
    *,
    hc_user_id: UUID,
    client_id: UUID | None,
    session_id: UUID | None,
    use_case: str,
    prompt_version: str,
    model_requested: str,
    model_served: str | None,
    fallback_count: int,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    validation_failed: bool,
    snippet_count: int,
    snippet_tokens: int,
    inr_cost_estimate: float | None,
    raw_request_id: str | None,
    error_message: str | None,
    prompt_text: str,
    completion_text: str,
    request_id: UUID | None,
) -> UUID:
    enc_key = get_settings().llm_call_encryption_key or _FALLBACK_KEY

    result = await db.execute(
        sa.text(
            "INSERT INTO llm_calls ("
            "  hc_user_id, client_id, session_id, request_id, use_case, prompt_version,"
            "  model_requested, model_served, fallback_count, input_tokens, output_tokens,"
            "  latency_ms, validation_failed, snippet_count, snippet_tokens,"
            "  inr_cost_estimate, raw_request_id, error_message,"
            "  prompt_text, completion_text"
            ") VALUES ("
            "  :hc_user_id, :client_id, :session_id, :request_id, :use_case, :prompt_version,"
            "  :model_requested, :model_served, :fallback_count, :input_tokens, :output_tokens,"
            "  :latency_ms, :validation_failed, :snippet_count, :snippet_tokens,"
            "  :inr_cost_estimate, :raw_request_id, :error_message,"
            "  pgp_sym_encrypt(:prompt_text, :enc_key),"
            "  pgp_sym_encrypt(:completion_text, :enc_key)"
            ") RETURNING id"
        ),
        {
            "hc_user_id": str(hc_user_id),
            "client_id": str(client_id) if client_id else None,
            "session_id": str(session_id) if session_id else None,
            "request_id": str(request_id) if request_id else None,
            "use_case": use_case,
            "prompt_version": prompt_version,
            "model_requested": model_requested,
            "model_served": model_served,
            "fallback_count": fallback_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "validation_failed": validation_failed,
            "snippet_count": snippet_count,
            "snippet_tokens": snippet_tokens,
            "inr_cost_estimate": inr_cost_estimate,
            "raw_request_id": raw_request_id,
            "error_message": error_message,
            "prompt_text": prompt_text or "",
            "completion_text": completion_text or "",
            "enc_key": enc_key,
        },
    )
    row = result.first()
    await db.flush()
    return UUID(str(row.id))
