"""LLM-based diet chart personalisation. Per ADR-0003."""
from __future__ import annotations

import logging
from uuid import UUID

import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm_service.chain import build_models_array, fallback_count_for
from src.llm_service.client import call_openrouter
from src.llm_service.config import get_llm_config
from src.llm_service.prompts import load_prompt
from src.llm_service.retry import STRICT_FORMAT_HINT, parse_or_retry
from src.llm_service.schemas.diet_chart import DietChartGridSchema
from src.llm_service.tracking import write_llm_call

logger = logging.getLogger(__name__)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _template_grid_section(template_params: dict) -> str:
    if template_params.get("template_type") == "raw_table":
        rows: list[list[str]] = template_params.get("rows", [])
        if not rows:
            return "Template: (empty)"
        lines = ["Template diet chart (full table — rows are meal types, columns are notes/options/ingredients):"]
        for row in rows:
            lines.append("  " + "  |  ".join(row))
        return "\n".join(lines)

    lines = ["Template grid:"]
    slots: list[str] = template_params.get("meal_slots", [])
    grid: dict = template_params.get("grid", {})
    for day in _DAYS:
        if day not in grid:
            continue
        lines.append(f"  {day}:")
        for slot in slots:
            cell = grid[day].get(slot, {})
            food = cell.get("food", "")
            timing = cell.get("timing", "")
            if timing:
                lines.append(f"    {slot}: {food} · {timing}")
            else:
                lines.append(f"    {slot}: {food}")
    return "\n".join(lines)


async def generate_diet_chart(
    db: AsyncSession,
    *,
    hc_user_id: UUID,
    client_id: UUID,
    template_params: dict,
    modifications: str | None,
    request_id: UUID | None = None,
) -> tuple[dict, str]:
    """
    Personalise a diet chart from a template via LLM.
    Returns (parameters_dict, generation_status) where generation_status is
    "generated" or "fallback".
    """
    cfg = get_llm_config()
    prompt_file = load_prompt("diet_chart_generate_v2")
    models = build_models_array(cfg)

    template_section = _template_grid_section(template_params)
    modifications_text = modifications or "No specific modifications — personalise for balanced nutrition."

    system_prompt = (
        prompt_file.body
        .replace("{{TEMPLATE_GRID}}", template_section)
        .replace("{{MODIFICATIONS}}", modifications_text)
        .replace("{{FORMAT_HINT}}", "")
    )
    user_message = "Personalise the template diet chart for this client."

    try:
        result = await call_openrouter(
            models=models,
            system_prompt=system_prompt,
            user_message=user_message,
            no_training=cfg.no_training_header,
            no_retention=cfg.no_retention_header,
        )
    except Exception as exc:
        await write_llm_call(
            db,
            hc_user_id=hc_user_id,
            client_id=client_id,
            session_id=None,
            use_case="diet_chart_generation",
            prompt_version=prompt_file.version,
            model_requested=models[0],
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
            error_message=str(exc),
            prompt_text=system_prompt,
            completion_text="",
            request_id=request_id,
        )
        logger.warning(
            "diet_chart_generation.llm_error.fallback",
            extra={"hc_user_id": str(hc_user_id), "client_id": str(client_id), "error": str(exc)},
        )
        sentry_sdk.capture_message(
            f"diet_chart_generation: LLM call failed — {exc}",
            level="warning",
        )
        return {**template_params, "is_template": False}, "fallback"

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
        result.content, DietChartGridSchema, retry_fn
    )

    fc = fallback_count_for(result.model_served, cfg)
    await write_llm_call(
        db,
        hc_user_id=hc_user_id,
        client_id=client_id,
        session_id=None,
        use_case="diet_chart_generation",
        prompt_version=prompt_file.version,
        model_requested=models[0],
        model_served=result.model_served,
        fallback_count=fc,
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

    if parsed is None:
        logger.warning(
            "diet_chart_generation.parse_failed.fallback",
            extra={
                "hc_user_id": str(hc_user_id),
                "client_id": str(client_id),
                "raw_snippet": result.content[:200],
            },
        )
        sentry_sdk.capture_message(
            "diet_chart_generation: JSON parse failed, returning template fallback",
            level="warning",
        )
        return {**template_params, "is_template": False}, "fallback"

    return parsed.to_parameters(template_params), "generated"
