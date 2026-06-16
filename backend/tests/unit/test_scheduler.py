"""Unit tests for scheduler pure-logic functions."""
from datetime import datetime, timedelta, timezone

import pytest

from src.api.scheduler import _check_scheduler_token, _should_retire

NOW = datetime.now(timezone.utc)


# ── _should_retire ──────────────────────────────────────────────────────────


def test_last_used_181_days_ago_should_retire():
    assert _should_retire(
        last_used_at=NOW - timedelta(days=181),
        created_at=NOW - timedelta(days=200),
        retired_at=None,
    ) is True


def test_last_used_10_days_ago_should_not_retire():
    assert _should_retire(
        last_used_at=NOW - timedelta(days=10),
        created_at=NOW - timedelta(days=200),
        retired_at=None,
    ) is False


def test_never_used_old_snippet_falls_back_to_created_at():
    """last_used_at is None → use created_at as reference."""
    assert _should_retire(
        last_used_at=None,
        created_at=NOW - timedelta(days=181),
        retired_at=None,
    ) is True


def test_never_used_recent_snippet_not_retired():
    assert _should_retire(
        last_used_at=None,
        created_at=NOW - timedelta(days=10),
        retired_at=None,
    ) is False


def test_already_retired_snippet_is_skipped():
    """Idempotency: a snippet with retired_at set is never re-processed."""
    assert _should_retire(
        last_used_at=NOW - timedelta(days=300),
        created_at=NOW - timedelta(days=300),
        retired_at=NOW - timedelta(days=1),
    ) is False


def test_under_threshold_is_not_retired():
    """Boundary: snippets used less than 180 days ago stay active."""
    assert _should_retire(
        last_used_at=NOW - timedelta(days=179),
        created_at=NOW - timedelta(days=200),
        retired_at=None,
    ) is False


# ── _check_scheduler_token ──────────────────────────────────────────────────


def test_correct_token_does_not_raise():
    _check_scheduler_token(provided="abc123", expected="abc123")  # must not raise


def test_wrong_token_raises():
    with pytest.raises(ValueError, match="invalid"):
        _check_scheduler_token(provided="wrong", expected="abc123")


def test_empty_token_raises():
    with pytest.raises(ValueError, match="invalid"):
        _check_scheduler_token(provided="", expected="abc123")
