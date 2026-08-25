"""LLM service — orchestrates MOM draft and brief generation. Per ADR-0003."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.clients import Client
from src.db.models.coaching import ActionItem, CheckIn, Mom
from src.db.models.content import ContentAssignment, DietChart
from src.db.models.files import ClientFile
from src.db.models.leadgen import HcLeadgenConfig, Lead, LeadQuestionnaireResponse
from src.db.models.sessions import Session
from src.lib.file_extraction import extract_text
from src.lib.s3 import s3_get
from src.llm_service.chain import build_models_array, fallback_count_for
from src.llm_service.client import call_openrouter
from src.llm_service.config import get_llm_config
from src.llm_service.prompts import load_prompt
from src.llm_service.retry import STRICT_FORMAT_HINT, parse_or_retry
from src.llm_service.schemas.brief import BriefSchema
from src.llm_service.schemas.lead_brief import LeadBriefSchema
from src.llm_service.schemas.lead_test_recommendation import LeadTestRecommendationSchema
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


async def _assemble_file_content_section(
    db: AsyncSession,
    session_id: UUID,
    config: object,
) -> tuple[str, bool]:
    """Returns (formatted_file_section, zoom_sources_present)."""
    files = (await db.execute(
        select(ClientFile).where(ClientFile.session_id == session_id)
    )).scalars().all()

    if not files:
        return "", False

    zoom_present = any(f.is_zoom_summary for f in files)
    total_tokens_used = 0
    sections = []

    for f in files:
        try:
            content = await s3_get(f.storage_path)
            text = await extract_text(content, f.mime_type)
        except Exception:
            continue  # skip files that fail to fetch or extract

        if not text.strip():
            continue  # skip empty files — don't emit heading-only noise

        # Per-file token budget (4 chars ≈ 1 token estimate)
        token_estimate = len(text) // 4
        if token_estimate > config.file_content_max_tokens_per_file:  # type: ignore[attr-defined]
            char_limit = config.file_content_max_tokens_per_file * 4  # type: ignore[attr-defined]
            text = text[:char_limit] + "\n[... truncated, file too long ...]"

        # Total budget — guard against negative slice from accumulated overrun
        remaining_budget = max(0, (config.file_content_max_total_tokens - total_tokens_used) * 4)  # type: ignore[attr-defined]
        if remaining_budget == 0:
            break
        if len(text) > remaining_budget:
            text = text[:remaining_budget] + "\n[... total file budget exceeded ...]"

        total_tokens_used += len(text) // 4
        sections.append(f"### {f.original_filename}\n{text}")

    if not sections:
        return "", zoom_present

    file_section = "## Uploaded files:\n" + "\n\n".join(sections)
    return file_section, zoom_present


async def generate_mom_draft(
    db: AsyncSession,
    *,
    session_id: UUID,
    hc_user_id: UUID,
    client_id: UUID,
    session_notes: str,
    request_id: UUID | None = None,
) -> tuple[str, list[dict], UUID]:
    """
    Generate an AI MOM draft. Returns (draft_text, action_items, llm_call_id).
    action_items is [{"description": str, "due_date": str | None}, ...].
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
    file_section, _zoom_present = await _assemble_file_content_section(db, session_id, cfg)
    notes_section = f"## HC's typed notes:\n{session_notes or '(no notes entered)'}"
    user_message = notes_section + ("\n\n" + file_section if file_section else "")

    _active_chart = (await db.execute(
        select(DietChart)
        .join(ContentAssignment, and_(
            ContentAssignment.content_type == "diet_chart",
            ContentAssignment.content_id == DietChart.id,
        ))
        .where(
            ContentAssignment.client_id == client_id,
            ContentAssignment.hc_user_id == hc_user_id,
            DietChart.archived_at.is_(None),
        )
        .limit(1)
    )).scalar_one_or_none()
    if _active_chart is not None:
        user_message += "\n\nNote: A diet chart has been prepared for this client."

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
    action_items = [
        {"description": a.description, "due_date": a.due_date}
        for a in parsed.action_items
    ]
    return draft_text, action_items, llm_call_id


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
            client.metadata_.get("intake_notes", "None provided")
            if client and client.metadata_
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
        .where(CheckIn.client_id == client_id, CheckIn.created_at >= cutoff_14d, CheckIn.payload.isnot(None))
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
    file_section, _zoom_present = await _assemble_file_content_section(db, session_id, cfg)
    user_message = "Generate the pre-session brief." + ("\n\n" + file_section if file_section else "")

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


async def generate_lead_brief(
    db: AsyncSession,
    *,
    lead_id: UUID,
    hc_user_id: UUID,
    blood_report_text: str,
    request_id: UUID | None = None,
) -> tuple[str | None, UUID | None]:
    """
    Generate a pre-consultation brief for a Lead. Returns (brief_text, llm_call_id).

    Per D-2: this function must NEVER raise — its caller is a public, unauthenticated
    upload endpoint whose success must not depend on brief generation succeeding. The
    entire body below is wrapped in try/except: any failure (missing Lead, LLM call
    exception, persistent validation failure after parse_or_retry) writes the
    `llm_calls` row with `error_message` set (mirroring the exception path already
    used by generate_mom_draft/generate_brief, per D-1 — no new schema) and returns
    (None, None) instead of raising.

    No snippets (D-4) — this is a standalone function, not a wrapper around
    generate_brief(). Does not touch R2 or `lead_files`; `blood_report_text` is
    assembled by the caller (a future upload endpoint) via extract_text() across all
    accepted files, which keeps this function testable without file I/O.
    """
    # D-2: none of these are assigned yet — get_llm_config()/load_prompt() can each raise
    # (missing/corrupt prompts/lead_brief.md, missing/invalid llm_config.yaml). Keep safe
    # placeholders here so _write_failure_row has something to report even if we fail before
    # the real values are ever assigned inside the try block below.
    prompt_file: object | None = None
    models: list[str] = []
    system_prompt = ""

    async def _write_failure_row(error_message: str) -> None:
        try:
            await write_llm_call(
                db,
                hc_user_id=hc_user_id,
                client_id=None,
                session_id=None,
                use_case="lead_brief",
                prompt_version=prompt_file.version if prompt_file is not None else "unknown",
                model_requested=models[0] if models else "",
                model_served=None,
                fallback_count=0,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                validation_failed=False,
                snippet_count=0,
                snippet_tokens=0,
                inr_cost_estimate=None,
                raw_request_id=None,
                error_message=error_message,
                prompt_text=system_prompt,
                completion_text="",
                request_id=request_id,
            )
        except Exception:
            pass  # logging the failure must not itself raise (D-2)

    try:
        cfg = get_llm_config()
        prompt_file = load_prompt("lead_brief")
        models = build_models_array(cfg)
        system_prompt = prompt_file.body  # overwritten below; used as a fallback if we fail before then

        lead = (await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )).scalar_one_or_none()
        if lead is None:
            raise ValueError(f"Lead not found: {lead_id}")

        # Questionnaire answers: LeadQuestionnaireResponse rows already snapshot each
        # question's label text at submission time (see src/api/intake.py), including
        # a row with response_text=None for unanswered questions — no separate lookup
        # of HcLeadgenConfig.questionnaire is needed to resolve labels.
        q_rows = (await db.execute(
            select(LeadQuestionnaireResponse).where(LeadQuestionnaireResponse.lead_id == lead_id)
        )).scalars().all()
        if q_rows:
            questionnaire_section = "\n\n".join(
                f"Q: {r.question_text}\nA: {r.response_text or '(not answered)'}"
                for r in q_rows
            )
        else:
            questionnaire_section = "No questionnaire responses on record."

        test_rec = lead.test_recommendation or {}
        all_tests = test_rec.get("all_tests") or []
        test_recommendation_section = (
            ", ".join(all_tests) if all_tests else "No specific tests recommended."
        )

        system_prompt = (
            prompt_file.body
            .replace("{{QUESTIONNAIRE_SECTION}}", questionnaire_section)
            .replace("{{TEST_RECOMMENDATION_SECTION}}", test_recommendation_section)
            .replace("{{BLOOD_REPORT_TEXT}}", blood_report_text or "")
        )
        user_message = "Generate the pre-consultation brief."

        try:
            result = await call_openrouter(
                models=models,
                system_prompt=system_prompt,
                user_message=user_message,
                no_training=cfg.no_training_header,
                no_retention=cfg.no_retention_header,
            )
        except Exception as exc:
            await _write_failure_row(str(exc))
            return None, None

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
            result.content, LeadBriefSchema, retry_fn
        )

        fb_count = fallback_count_for(result.model_served, cfg)
        llm_call_id = await write_llm_call(
            db,
            hc_user_id=hc_user_id,
            client_id=None,
            session_id=None,
            use_case="lead_brief",
            prompt_version=prompt_file.version,
            model_requested=models[0],
            model_served=result.model_served,
            fallback_count=fb_count,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            validation_failed=validation_failed,
            snippet_count=0,
            snippet_tokens=0,
            inr_cost_estimate=None,
            raw_request_id=result.raw_request_id,
            error_message=error_msg,
            prompt_text=system_prompt,
            completion_text=result.content,
            request_id=request_id,
        )

        if validation_failed or parsed is None:
            return None, None

        return parsed.to_brief_text(), llm_call_id

    except Exception as exc:
        await _write_failure_row(str(exc))
        return None, None


async def generate_lead_test_recommendation(
    db: AsyncSession,
    *,
    lead_id: UUID,
    hc_user_id: UUID,
    request_id: UUID | None = None,
) -> list[dict[str, str]] | None:
    """
    Generate AI-drafted test recommendation *additions* for a Lead, on top of the
    HC's standard baseline panel. Returns a list of `{"test": str, "rationale": str}`
    dicts (an empty list is a valid, common result — see prompt rules), or None on
    any failure.

    Per PHASE-04 plan (mirroring PHASE-03 D-2 for generate_lead_brief): this
    function must NEVER raise — its caller is `POST /api/intake/:slug`, a public,
    unauthenticated, Lead-facing endpoint whose success must not depend on this LLM
    call succeeding. The entire body below is wrapped in try/except: any failure
    (missing Lead/HcLeadgenConfig, config/prompt load failure, LLM call exception,
    persistent validation failure after parse_or_retry) writes the `llm_calls` row
    with `error_message` set (mirroring the exception path already used by
    generate_lead_brief/generate_mom_draft/generate_brief — no new schema) and
    returns None instead of raising.

    No snippets — this is a standalone function, not a wrapper around
    generate_brief(), per the prompt design (Task 1).
    """
    # None of these are assigned yet — get_llm_config()/load_prompt() can each raise
    # (missing/corrupt prompts/lead_test_recommendation.md, missing/invalid
    # llm_config.yaml). Keep safe placeholders here so _write_failure_row has
    # something to report even if we fail before the real values are ever assigned
    # inside the try block below.
    prompt_file: object | None = None
    models: list[str] = []
    system_prompt = ""

    async def _write_failure_row(error_message: str) -> None:
        try:
            await write_llm_call(
                db,
                hc_user_id=hc_user_id,
                client_id=None,
                session_id=None,
                use_case="lead_test_recommendation",
                prompt_version=prompt_file.version if prompt_file is not None else "unknown",
                model_requested=models[0] if models else "",
                model_served=None,
                fallback_count=0,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                validation_failed=False,
                snippet_count=0,
                snippet_tokens=0,
                inr_cost_estimate=None,
                raw_request_id=None,
                error_message=error_message,
                prompt_text=system_prompt,
                completion_text="",
                request_id=request_id,
            )
        except Exception:
            pass  # logging the failure must not itself raise (mirrors generate_lead_brief)

    try:
        cfg = get_llm_config()
        prompt_file = load_prompt("lead_test_recommendation")
        models = build_models_array(cfg)
        system_prompt = prompt_file.body  # overwritten below; fallback if we fail before then

        lead = (await db.execute(
            select(Lead).where(Lead.id == lead_id)
        )).scalar_one_or_none()
        if lead is None:
            raise ValueError(f"Lead not found: {lead_id}")

        config = (await db.execute(
            select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == hc_user_id)
        )).scalar_one_or_none()
        if config is None:
            raise ValueError(f"HcLeadgenConfig not found for hc_user_id: {hc_user_id}")

        standard_tests: list[str] = list((config.test_panel or {}).get("standard_tests") or [])
        baseline_tests_section = (
            ", ".join(standard_tests) if standard_tests else "No standard tests configured."
        )

        # Questionnaire answers: same shape/section-building as generate_lead_brief —
        # LeadQuestionnaireResponse rows already snapshot each question's label text
        # at submission time (see src/api/intake.py), including a row with
        # response_text=None for unanswered questions.
        q_rows = (await db.execute(
            select(LeadQuestionnaireResponse).where(LeadQuestionnaireResponse.lead_id == lead_id)
        )).scalars().all()
        if q_rows:
            questionnaire_section = "\n\n".join(
                f"Q: {r.question_text}\nA: {r.response_text or '(not answered)'}"
                for r in q_rows
            )
        else:
            questionnaire_section = "No questionnaire responses on record."

        system_prompt = (
            prompt_file.body
            .replace("{{BASELINE_TESTS_SECTION}}", baseline_tests_section)
            .replace("{{QUESTIONNAIRE_SECTION}}", questionnaire_section)
        )
        user_message = "Generate the test recommendation additions."

        try:
            result = await call_openrouter(
                models=models,
                system_prompt=system_prompt,
                user_message=user_message,
                no_training=cfg.no_training_header,
                no_retention=cfg.no_retention_header,
            )
        except Exception as exc:
            await _write_failure_row(str(exc))
            return None

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
            result.content, LeadTestRecommendationSchema, retry_fn
        )

        fb_count = fallback_count_for(result.model_served, cfg)
        await write_llm_call(
            db,
            hc_user_id=hc_user_id,
            client_id=None,
            session_id=None,
            use_case="lead_test_recommendation",
            prompt_version=prompt_file.version,
            model_requested=models[0],
            model_served=result.model_served,
            fallback_count=fb_count,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            validation_failed=validation_failed,
            snippet_count=0,
            snippet_tokens=0,
            inr_cost_estimate=None,
            raw_request_id=result.raw_request_id,
            error_message=error_msg,
            prompt_text=system_prompt,
            completion_text=result.content,
            request_id=request_id,
        )

        if validation_failed or parsed is None:
            return None

        return [{"test": a.test, "rationale": a.rationale} for a in parsed.additions]

    except Exception as exc:
        await _write_failure_row(str(exc))
        return None
