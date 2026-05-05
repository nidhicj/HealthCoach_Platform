"""LLM service — orchestrates MOM draft and brief generation. Per ADR-0003."""
from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.clients import Client
from src.db.models.coaching import ActionItem, Mom
from src.db.models.sessions import Session
from src.llm_service.chain import build_models_array, fallback_count_for
from src.llm_service.client import call_openrouter
from src.llm_service.config import get_llm_config
from src.llm_service.prompts import load_prompt
from src.llm_service.retry import STRICT_FORMAT_HINT, parse_or_retry
from src.llm_service.schemas.brief import BriefSchema
from src.llm_service.schemas.mom import MomDraftSchema
from src.llm_service.snippets import select as select_snippets
from src.llm_service.snippets import update_usage
from src.llm_service.tracking import write_llm_call


def _format_snippets(snippets: list) -> str:
    if not snippets:
        return ""
    lines = ["\nHC STYLE EXAMPLES (from your previous edits — mirror this voice):"]
    for s in snippets:
        lines.append(f"\nOriginal: {s.original_text}")
        lines.append(f"Your edit: {s.hc_modified_text}")
    return "\n".join(lines)


async def generate_mom_draft(
    db: AsyncSession,
    *,
    session_id: UUID,
    hc_user_id: UUID,
    client_id: UUID,
    session_notes: str,
    request_id: UUID | None = None,
) -> tuple[str, UUID]:
    """
    Generate an AI MOM draft. Returns (draft_text, llm_call_id).
    Raises HTTPException 503 on LLM failure, 422 on persistent validation failure.
    """
    cfg = get_llm_config()
    prompt_file = load_prompt("mom_draft")
    models = build_models_array(cfg)

    # Load client pseudonym
    client = (await db.execute(
        select(Client).where(Client.id == client_id)
    )).scalar_one_or_none()
    client_code = (client.code if client and client.code else f"CLIENT-{str(client_id)[:8]}")

    # Load snippets
    snippets, snippet_tokens = await select_snippets(db, hc_user_id=hc_user_id, config=cfg)
    snippet_section = _format_snippets(snippets)

    system_prompt = (
        prompt_file.body
        .replace("{{CLIENT_CODE}}", client_code)
        .replace("{{SNIPPET_SECTION}}", snippet_section)
    )
    user_message = f"Session notes:\n{session_notes}"

    try:
        result = await call_openrouter(
            models=models,
            system_prompt=system_prompt,
            user_message=user_message,
            no_training=cfg.no_training_header,
            no_retention=cfg.no_retention_header,
        )
    except Exception as exc:
        llm_call_id = await write_llm_call(
            db,
            hc_user_id=hc_user_id,
            client_id=client_id,
            session_id=session_id,
            use_case="mom_generation",
            prompt_version=prompt_file.version,
            model_requested=models[0],
            model_served=None,
            fallback_count=0,
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            validation_failed=False,
            snippet_count=len(snippets),
            snippet_tokens=snippet_tokens,
            inr_cost_estimate=None,
            raw_request_id=None,
            error_message=str(exc),
            prompt_text=system_prompt,
            completion_text="",
            request_id=request_id,
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=repr(exc) or "LLM service unavailable") from exc

    async def retry_fn() -> str:
        retry_result = await call_openrouter(
            models=models,
            system_prompt=system_prompt + STRICT_FORMAT_HINT,
            user_message=user_message,
            no_training=cfg.no_training_header,
            no_retention=cfg.no_retention_header,
        )
        return retry_result.content

    parsed, validation_failed, error_msg = await parse_or_retry(
        result.content, MomDraftSchema, retry_fn
    )

    fb_count = fallback_count_for(result.model_served, cfg)
    llm_call_id = await write_llm_call(
        db,
        hc_user_id=hc_user_id,
        client_id=client_id,
        session_id=session_id,
        use_case="mom_generation",
        prompt_version=prompt_file.version,
        model_requested=models[0],
        model_served=result.model_served,
        fallback_count=fb_count,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        validation_failed=validation_failed,
        snippet_count=len(snippets),
        snippet_tokens=snippet_tokens,
        inr_cost_estimate=None,
        raw_request_id=result.raw_request_id,
        error_message=error_msg,
        prompt_text=system_prompt,
        completion_text=result.content,
        request_id=request_id,
    )

    if validation_failed or parsed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM output failed validation",
        )

    await update_usage(db, [s.id for s in snippets])

    draft_text = parsed.to_draft_text()
    return draft_text, llm_call_id


async def generate_brief(
    db: AsyncSession,
    *,
    session_id: UUID,
    hc_user_id: UUID,
    client_id: UUID,
    request_id: UUID | None = None,
) -> tuple[str, list[str], UUID]:
    """
    Generate a pre-session brief. Returns (brief_text, triage_flags, llm_call_id).
    Raises HTTPException 503 on LLM failure, 422 on persistent validation failure.
    """
    cfg = get_llm_config()
    prompt_file = load_prompt("brief_assemble")
    models = build_models_array(cfg)

    # Load client pseudonym
    client = (await db.execute(
        select(Client).where(Client.id == client_id)
    )).scalar_one_or_none()
    client_code = (client.code if client and client.code else f"CLIENT-{str(client_id)[:8]}")

    # Load previous MOM (most recent for this client, excluding this session)
    prev_mom_row = (await db.execute(
        sa.select(Mom)
        .join(Session, Mom.session_id == Session.id)
        .where(
            Mom.client_id == client_id,
            Mom.session_id != session_id,
            Mom.final_text.isnot(None),
        )
        .order_by(Session.scheduled_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    prev_mom_text = prev_mom_row.final_text if prev_mom_row else "No previous session on record."

    # Open action items
    open_items = (await db.execute(
        sa.select(ActionItem)
        .where(ActionItem.client_id == client_id, ActionItem.status == "open")
        .limit(10)
    )).scalars().all()
    check_in_text = (
        "\n".join(f"- {a.description}" for a in open_items)
        if open_items else "No open check-ins."
    )

    # Load snippets
    snippets, snippet_tokens = await select_snippets(db, hc_user_id=hc_user_id, config=cfg)
    snippet_section = _format_snippets(snippets)

    system_prompt = (
        prompt_file.body
        .replace("{{CLIENT_CODE}}", client_code)
        .replace("{{PREVIOUS_MOM}}", prev_mom_text)
        .replace("{{RECENT_CHECK_INS}}", check_in_text)
        .replace("{{SNIPPET_SECTION}}", snippet_section)
    )
    user_message = "Generate the pre-session brief."

    try:
        result = await call_openrouter(
            models=models,
            system_prompt=system_prompt,
            user_message=user_message,
            no_training=cfg.no_training_header,
            no_retention=cfg.no_retention_header,
        )
    except Exception as exc:
        llm_call_id = await write_llm_call(
            db,
            hc_user_id=hc_user_id,
            client_id=client_id,
            session_id=session_id,
            use_case="brief_generation",
            prompt_version=prompt_file.version,
            model_requested=models[0],
            model_served=None,
            fallback_count=0,
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            validation_failed=False,
            snippet_count=len(snippets),
            snippet_tokens=snippet_tokens,
            inr_cost_estimate=None,
            raw_request_id=None,
            error_message=str(exc),
            prompt_text=system_prompt,
            completion_text="",
            request_id=request_id,
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=repr(exc) or "LLM service unavailable") from exc

    async def retry_fn() -> str:
        retry_result = await call_openrouter(
            models=models,
            system_prompt=system_prompt + STRICT_FORMAT_HINT,
            user_message=user_message,
            no_training=cfg.no_training_header,
            no_retention=cfg.no_retention_header,
        )
        return retry_result.content

    parsed, validation_failed, error_msg = await parse_or_retry(
        result.content, BriefSchema, retry_fn
    )

    fb_count = fallback_count_for(result.model_served, cfg)
    llm_call_id = await write_llm_call(
        db,
        hc_user_id=hc_user_id,
        client_id=client_id,
        session_id=session_id,
        use_case="brief_generation",
        prompt_version=prompt_file.version,
        model_requested=models[0],
        model_served=result.model_served,
        fallback_count=fb_count,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        validation_failed=validation_failed,
        snippet_count=len(snippets),
        snippet_tokens=snippet_tokens,
        inr_cost_estimate=None,
        raw_request_id=result.raw_request_id,
        error_message=error_msg,
        prompt_text=system_prompt,
        completion_text=result.content,
        request_id=request_id,
    )

    if validation_failed or parsed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM output failed validation",
        )

    await update_usage(db, [s.id for s in snippets])

    return parsed.to_brief_text(), parsed.triage_flags, llm_call_id
