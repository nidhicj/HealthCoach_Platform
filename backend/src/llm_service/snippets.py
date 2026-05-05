"""Snippet capture and selection for HC style learning. Per ADR-0003 §6."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.coaching import HcStyleSnippet
from src.llm_service.config import LLMConfig, get_llm_config


def count_tokens(text: str) -> int:
    """Approximate token count (~4 chars per token)."""
    return max(1, len(text) // 4)


async def capture(
    db: AsyncSession,
    *,
    original_text: str,
    hc_modified_text: str,
    hc_user_id: UUID,
    client_id: UUID | None,
    config: LLMConfig | None = None,
) -> None:
    """Create an hc_style_snippets row if the edit meets capture thresholds."""
    cfg = config or get_llm_config()

    if original_text == hc_modified_text:
        return

    diff_size = abs(len(hc_modified_text) - len(original_text))
    if diff_size < cfg.snippet_diff_threshold:
        return

    if cfg.snippet_whitespace_filter:
        orig_norm = " ".join(original_text.split())
        edit_norm = " ".join(hc_modified_text.split())
        if orig_norm == edit_norm:
            return

    snippet = HcStyleSnippet(
        hc_user_id=hc_user_id,
        client_id=client_id,
        snippet_type="edit",
        original_text=original_text,
        hc_modified_text=hc_modified_text,
    )
    db.add(snippet)


async def select(  # noqa: A001
    db: AsyncSession,
    *,
    hc_user_id: UUID,
    config: LLMConfig | None = None,
) -> tuple[list[HcStyleSnippet], int]:
    """
    Option C hybrid: pool of N most-recent by created_at, re-sorted by
    last_used_at ASC NULLS FIRST within the pool, stopped at token budget.
    """
    cfg = config or get_llm_config()

    pool_q = (
        sa.select(HcStyleSnippet)
        .where(
            HcStyleSnippet.hc_user_id == hc_user_id,
            HcStyleSnippet.retired_at.is_(None),
        )
        .order_by(HcStyleSnippet.created_at.desc())
        .limit(cfg.snippet_pool_size)
    )
    pool = list((await db.execute(pool_q)).scalars().all())

    # NULLS FIRST (never-injected gets priority), then oldest last_used_at first
    pool.sort(key=lambda s: (
        s.last_used_at is not None,
        s.last_used_at or datetime.min.replace(tzinfo=timezone.utc),
    ))

    result: list[HcStyleSnippet] = []
    total_tokens = 0
    for snippet in pool:
        text = snippet.hc_modified_text or snippet.original_text
        tokens = count_tokens(text)
        if total_tokens + tokens > cfg.snippet_token_budget:
            break
        result.append(snippet)
        total_tokens += tokens
        if len(result) >= cfg.snippet_max_count:
            break

    return result, total_tokens


async def update_usage(db: AsyncSession, snippet_ids: list[UUID]) -> None:
    """Atomically bump use_count and last_used_at for injected snippets."""
    if not snippet_ids:
        return
    now = datetime.now(timezone.utc)
    await db.execute(
        sa.update(HcStyleSnippet)
        .where(HcStyleSnippet.id.in_(snippet_ids))
        .values(last_used_at=now, use_count=HcStyleSnippet.use_count + 1)
    )
