"""LLM service — orchestrates MOM draft and brief generation. Per ADR-0003."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.clients import Client
from src.db.models.coaching import ActionItem, CheckIn, Mom
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

CHECKIN_TRIAGE_DAYS = 14
SENTIMENT_LOOKBACK_DAYS = 30


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
) -> tuple[str, list[str], UUID | None]:
    """
    Generate a pre-session brief. Returns (brief_text, triage_flags, llm_call_id).
    M000 sessions (session_number==0) return a static template with llm_call_id=None.
    Raises HTTPException 503 on LLM failure, 422 on persistent validation failure.
    """
    cfg = get_llm_config()
    prompt_file = load_prompt("brief_assemble")
    models = build_models_array(cfg)

    # Load session to check M000
    session = (await db.execute(
        select(Session).where(Session.id == session_id)
    )).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load client
    client = (await db.execute(
        select(Client).where(Client.id == client_id)
    )).scalar_one_or_none()
    client_code = (client.code if client and client.code else f"CLIENT-{str(client_id)[:8]}")

    # ── M000: first-session preparation brief ─────────────────────────────────
    if session.session_number == 0:
        intake_notes = (
            client.metadata.get("intake_notes", "None provided")
            if client and client.metadata
            else "None provided"
        )
        brief_text = (
            f"M000 PREPARATION BRIEF — {client_code}\n\n"
            f"CLIENT CONTEXT:\n"
            f"Goal: {getattr(client, 'course_goal', None) or 'Not yet set'}\n"
            f"Course start: {getattr(client, 'course_start_date', None) or 'TBD'}\n"
            f"Notes: {intake_notes}\n\n"
            "FIRST SESSION CHECKLIST:\n"
            "- Establish rapport and mutual expectations\n"
            "- Clarify health goal and success criteria\n"
            "- Assess current baseline (diet, activity, sleep, stress)\n"
            "- Identify top 3 constraints (time, budget, medical, cultural)\n"
            "- Agree on check-in cadence and preferred channels\n"
            "- Set 1–2 action items for the coming week\n"
            "- Confirm next session date"
        )
        return brief_text, [], None

    # ── M00N: regular pre-session brief ───────────────────────────────────────

    # Previous MOM (most recent for this client, excluding this session)
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

    # Open action items (limit 10)
    open_items = (await db.execute(
        sa.select(ActionItem)
        .where(ActionItem.client_id == client_id, ActionItem.status == "open")
        .limit(10)
    )).scalars().all()

    # Missed action items (limit 10)
    missed_items = (await db.execute(
        sa.select(ActionItem)
        .where(ActionItem.client_id == client_id, ActionItem.status == "missed")
        .limit(10)
    )).scalars().all()

    # Recent check-ins (last 14 days)
    cutoff_14d = datetime.now(timezone.utc) - timedelta(days=CHECKIN_TRIAGE_DAYS)
    recent_checkins = (await db.execute(
        sa.select(CheckIn)
        .where(CheckIn.client_id == client_id, CheckIn.created_at >= cutoff_14d)
        .order_by(CheckIn.created_at.desc())
    )).scalars().all()

    # Build check-in text for prompt ({{RECENT_CHECK_INS}})
    check_in_text = (
        "\n".join(f"- {ci.payload.get('note', '(no note)')}" for ci in recent_checkins)
        if recent_checkins else "No recent check-ins."
    )

    # AST section for prompt ({{AST_SECTION}})
    ast_lines = []
    if open_items:
        ast_lines.append("Open action items:")
        for item in open_items:
            ast_lines.append(f"  - {item.description}")
    else:
        ast_lines.append("Open action items: None")
    if missed_items:
        ast_lines.append("Missed action items:")
        for item in missed_items:
            ast_lines.append(f"  - {item.description}")
    ast_section = "\n".join(ast_lines)

    # Triage flags (computed server-side, not from LLM)
    triage_flags: list[str] = []
    if missed_items:
        triage_flags.append("missed_action_item")
    if not recent_checkins:
        triage_flags.append("no_recent_checkin")

    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=SENTIMENT_LOOKBACK_DAYS)
    sentiment_flagged = (await db.execute(
        sa.select(CheckIn)
        .where(
            CheckIn.client_id == client_id,
            CheckIn.created_at >= cutoff_30d,
            CheckIn.sentiment_flag.isnot(None),
        )
        .limit(1)
    )).scalar_one_or_none()
    if sentiment_flagged is not None:
        triage_flags.append("manual_sentiment_flag")

    triage_section = (
        "\n".join(f"- {f}" for f in triage_flags) if triage_flags else "No triage flags."
    )

    # Load snippets
    snippets, snippet_tokens = await select_snippets(db, hc_user_id=hc_user_id, config=cfg)
    snippet_section = _format_snippets(snippets)

    system_prompt = (
        prompt_file.body
        .replace("{{CLIENT_CODE}}", client_code)
        .replace("{{PREVIOUS_MOM}}", prev_mom_text)
        .replace("{{RECENT_CHECK_INS}}", check_in_text)
        .replace("{{AST_SECTION}}", ast_section)
        .replace("{{TRIAGE_SECTION}}", triage_section)
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

    # Return server-computed triage_flags, not from LLM parsed output
    return parsed.to_brief_text(), triage_flags, llm_call_id
