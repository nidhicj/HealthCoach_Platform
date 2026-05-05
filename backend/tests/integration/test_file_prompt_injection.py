"""Integration tests: file content appears (or not) in the LLM user_message. P5 Part B."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from src.db.models import ClientFile
from src.llm_service.client import OpenRouterResult

_MOCK_MOM_JSON = json.dumps({
    "summary": "Good session.",
    "key_discussion_points": ["Hydration"],
    "action_items": [{"description": "Drink 2.5L daily", "due_date": "2026-06-08"}],
    "follow_ups": [],
    "hc_closing_note": "Keep it up.",
})


def _make_openrouter_result(content: str) -> OpenRouterResult:
    return OpenRouterResult(
        content=content,
        model_served="meta-llama/llama-3.3-70b-instruct:free",
        input_tokens=100,
        output_tokens=80,
        latency_ms=200,
        raw_request_id="test-req-id",
    )


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_mock_openrouter(captured: dict):
    """Return an async side_effect that captures kwargs and returns a valid result."""
    async def _fn(**kwargs):
        captured.update(kwargs)
        return _make_openrouter_result(_MOCK_MOM_JSON)
    return _fn


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mom_draft_includes_typed_notes_section(
    http_client, hc_headers, session_id, db, hc_user, client_rec
):
    """POST /mom/draft with session_notes + 1 ClientFile → user_message includes both sections."""
    client_rec.code = "CP0001"
    await db.flush()

    cf = ClientFile(
        session_id=session_id,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
        original_filename="notes.txt",
        storage_path="hc-test/notes.txt",
        mime_type="text/plain",
        size_bytes=11,
        is_zoom_summary=False,
    )
    db.add(cf)
    await db.flush()

    captured: dict = {}
    with patch("src.llm_service.s3_get", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = b"File content here."
        with patch("src.llm_service.call_openrouter", side_effect=_make_mock_openrouter(captured)):
            r = await http_client.post(
                f"/api/sessions/{session_id}/mom/draft",
                headers=hc_headers,
                json={"session_notes": "HC's handwritten notes."},
            )

    assert r.status_code == 200, r.text
    assert "## HC's typed notes:" in captured["user_message"]
    assert "## Uploaded files:" in captured["user_message"]
    assert "HC's handwritten notes." in captured["user_message"]
    assert "File content here." in captured["user_message"]


@pytest.mark.asyncio
async def test_mom_draft_no_files_uses_notes_only(
    http_client, hc_headers, session_id, db, client_rec
):
    """POST /mom/draft with session_notes + no ClientFile → user_message starts with HC's notes, no files section."""
    client_rec.code = "CP0001"
    await db.flush()

    captured: dict = {}
    with patch("src.llm_service.call_openrouter", side_effect=_make_mock_openrouter(captured)):
        r = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft",
            headers=hc_headers,
            json={"session_notes": "Only notes, no files."},
        )

    assert r.status_code == 200, r.text
    assert "## HC's typed notes:" in captured["user_message"]
    assert "## Uploaded files:" not in captured["user_message"]


@pytest.mark.asyncio
async def test_file_content_truncated_at_per_file_limit(
    http_client, hc_headers, session_id, db, hc_user, client_rec
):
    """When file text exceeds per-file token limit, a truncation marker is appended."""
    client_rec.code = "CP0001"
    await db.flush()

    cf = ClientFile(
        session_id=session_id,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
        original_filename="long_notes.txt",
        storage_path="hc-test/long_notes.txt",
        mime_type="text/plain",
        size_bytes=99999,
        is_zoom_summary=False,
    )
    db.add(cf)
    await db.flush()

    # 5000 tokens × 4 chars/token = 20000 chars; we give 30000 chars which exceeds the limit
    long_text = b"word " * 6000  # 30000 chars

    captured: dict = {}
    with patch("src.llm_service.s3_get", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = long_text
        with patch("src.llm_service.call_openrouter", side_effect=_make_mock_openrouter(captured)):
            r = await http_client.post(
                f"/api/sessions/{session_id}/mom/draft",
                headers=hc_headers,
                json={"session_notes": "notes"},
            )

    assert r.status_code == 200, r.text
    assert "[... truncated, file too long ...]" in captured["user_message"]


@pytest.mark.asyncio
async def test_zoom_file_included_in_prompt(
    http_client, hc_headers, session_id, db, hc_user, client_rec
):
    """ClientFile with is_zoom_summary=True still appears in LLM user_message (just excluded from snippets)."""
    client_rec.code = "CP0001"
    await db.flush()

    cf = ClientFile(
        session_id=session_id,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
        original_filename="zoom_ai_summary_session.txt",
        storage_path="hc-test/zoom_summary.txt",
        mime_type="text/plain",
        size_bytes=30,
        is_zoom_summary=True,
    )
    db.add(cf)
    await db.flush()

    captured: dict = {}
    with patch("src.llm_service.s3_get", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = b"Zoom AI summary content here."
        with patch("src.llm_service.call_openrouter", side_effect=_make_mock_openrouter(captured)):
            r = await http_client.post(
                f"/api/sessions/{session_id}/mom/draft",
                headers=hc_headers,
                json={"session_notes": "notes"},
            )

    assert r.status_code == 200, r.text
    assert "## Uploaded files:" in captured["user_message"]
    assert "Zoom AI summary content here." in captured["user_message"]
