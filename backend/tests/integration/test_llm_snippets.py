"""Integration tests for snippet capture and selection."""
import uuid
from unittest.mock import patch

import pytest

from src.db.models import Client
from src.llm_service.config import LLMConfig
from src.llm_service.snippets import capture, count_tokens, select


def _make_config(**overrides) -> LLMConfig:
    defaults = dict(
        model_chain=["meta-llama/llama-3.3-70b-instruct:free"],
        reasoning_model="deepseek/deepseek-r1",
        no_training_header=True,
        no_retention_header=True,
        snippet_pool_size=25,
        snippet_diff_threshold=5,
        snippet_whitespace_filter=True,
        snippet_token_budget=2000,
        snippet_max_count=10,
        validation_retry_count=1,
    )
    defaults.update(overrides)
    return LLMConfig(**defaults)


# ── capture tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capture_creates_snippet_row(db, hc_user, client_rec):
    original = "You should drink more water daily."
    edited = "Aim for 2.5L water daily and track it in your app."
    await capture(
        db,
        original_text=original,
        hc_modified_text=edited,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
    )
    await db.flush()

    import sqlalchemy as sa
    result = await db.execute(
        sa.text("SELECT snippet_type, original_text, hc_modified_text, client_id FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    rows = result.fetchall()
    assert len(rows) >= 1
    row = rows[0]
    assert row.snippet_type == "edit"
    assert row.client_id == client_rec.id


@pytest.mark.asyncio
async def test_capture_below_threshold_creates_no_row(db, hc_user, client_rec):
    cfg = _make_config(snippet_diff_threshold=10)
    original = "Drink water."
    edited = "Drink water!"  # diff < 10 chars
    await capture(
        db,
        original_text=original,
        hc_modified_text=edited,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
        config=cfg,
    )
    await db.flush()

    import sqlalchemy as sa
    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_capture_whitespace_only_diff_creates_no_row(db, hc_user, client_rec):
    original = "Drink water daily."
    edited = "Drink water  daily."  # whitespace-only diff
    cfg = _make_config(snippet_whitespace_filter=True)
    await capture(
        db,
        original_text=original,
        hc_modified_text=edited,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
        config=cfg,
    )
    await db.flush()

    import sqlalchemy as sa
    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_capture_no_change_creates_no_row(db, hc_user, client_rec):
    text = "Drink 2.5L water daily."
    await capture(
        db,
        original_text=text,
        hc_modified_text=text,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
    )
    await db.flush()

    import sqlalchemy as sa
    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    assert result.scalar() == 0


# ── select tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_select_returns_empty_for_new_hc(db, hc_user):
    cfg = _make_config()
    snippets, token_count = await select(db, hc_user_id=hc_user.id, config=cfg)
    assert snippets == []
    assert token_count == 0


@pytest.mark.asyncio
async def test_select_returns_snippets_for_hc(db, hc_user, client_rec):
    # First capture some snippets
    await capture(
        db,
        original_text="Original text from AI",
        hc_modified_text="HC's improved version with specific numbers: 2.5L daily",
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
    )
    await db.flush()

    cfg = _make_config()
    snippets, token_count = await select(db, hc_user_id=hc_user.id, config=cfg)
    assert len(snippets) >= 1
    assert token_count > 0


@pytest.mark.asyncio
async def test_select_respects_token_budget(db, hc_user, client_rec):
    # Create many long snippets
    for i in range(5):
        await capture(
            db,
            original_text=f"Original text {i} from AI assistant for the health coach.",
            hc_modified_text=f"HC modified version {i}: " + "word " * 100,  # ~500 tokens each
            hc_user_id=hc_user.id,
            client_id=client_rec.id,
        )
    await db.flush()

    cfg = _make_config(snippet_token_budget=200)  # tight budget
    snippets, token_count = await select(db, hc_user_id=hc_user.id, config=cfg)
    assert token_count <= 200


@pytest.mark.asyncio
async def test_select_cross_tenant_isolation(db, hc_user, client_rec):
    """HC2's snippets should not appear when selecting for HC1."""
    import sqlalchemy as sa
    from src.db.models import User, Client

    # Create HC2
    hc2 = User(
        email=f"hc2-snippet-test-{uuid.uuid4().hex[:6]}@example.com",
        google_sub=f"g-hc2-{uuid.uuid4().hex}",
        role="hc",
    )
    db.add(hc2)
    await db.flush()

    # Capture snippet for HC2
    await capture(
        db,
        original_text="HC2 private coaching note for their client.",
        hc_modified_text="HC2 modified: very specific advice for their client only.",
        hc_user_id=hc2.id,
        client_id=None,
    )
    await db.flush()

    cfg = _make_config()
    snippets_for_hc1, _ = await select(db, hc_user_id=hc_user.id, config=cfg)
    # HC1 should see none of HC2's snippets
    hc2_ids = {str(hc2.id)}
    for s in snippets_for_hc1:
        assert str(s.hc_user_id) not in hc2_ids


def test_count_tokens_approximate():
    text = "word " * 100  # ~100 tokens
    tokens = count_tokens(text)
    # Should be within reasonable range (rough 4 char/token approximation)
    assert 50 <= tokens <= 200
