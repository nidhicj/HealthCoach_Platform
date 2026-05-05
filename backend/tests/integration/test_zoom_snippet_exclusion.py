"""Integration tests for Zoom summary → snippet exclusion gate. P5 Part B."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
import sqlalchemy as sa

from src.db.models import ClientFile
from src.llm_service.client import OpenRouterResult

_MOCK_MOM_JSON = json.dumps({
    "summary": "Client improved their diet.",
    "key_discussion_points": ["Protein intake", "Sleep schedule"],
    "action_items": [{"description": "Track meals daily", "due_date": "2026-06-08"}],
    "follow_ups": ["Review progress next session"],
    "hc_closing_note": "Solid work this week.",
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


async def _draft_and_patch_mom(http_client, session_id: object, hc_headers: dict, final_suffix: str = " Extra content to ensure substantial diff added here now."):
    """Helper: POST /mom/draft then PATCH /mom with edited final_text."""
    with patch("src.llm_service.s3_get", new_callable=AsyncMock) as mock_s3:
        mock_s3.return_value = b"File content."
        with patch("src.llm_service.call_openrouter") as mock_or:
            mock_or.return_value = _make_openrouter_result(_MOCK_MOM_JSON)
            r_draft = await http_client.post(
                f"/api/sessions/{session_id}/mom/draft",
                headers=hc_headers,
                json={"session_notes": "Session went well, client made great progress."},
            )
    assert r_draft.status_code == 200, r_draft.text
    draft_text = r_draft.json()["draft_text"]

    edited_text = draft_text + final_suffix
    r_patch = await http_client.patch(
        f"/api/sessions/{session_id}/mom",
        headers=hc_headers,
        json={"final_text": edited_text, "status": "reviewed"},
    )
    assert r_patch.status_code == 200, r_patch.text


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zoom_file_suppresses_snippet_capture(
    http_client, hc_headers, session_id, db, hc_user, client_rec
):
    """When a Zoom summary file exists for the session, PATCH mom does NOT capture style snippets."""
    client_rec.code = "CP0001"
    await db.flush()

    cf = ClientFile(
        session_id=session_id,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
        original_filename="zoom_ai_summary_s1.txt",
        storage_path="hc-test/zoom.txt",
        mime_type="text/plain",
        size_bytes=20,
        is_zoom_summary=True,
    )
    db.add(cf)
    await db.flush()

    await _draft_and_patch_mom(http_client, session_id, hc_headers)

    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_non_zoom_file_allows_snippet_capture(
    http_client, hc_headers, session_id, db, hc_user, client_rec
):
    """When only non-Zoom files exist, substantial edits to the MOM DO create style snippets."""
    client_rec.code = "CP0001"
    await db.flush()

    cf = ClientFile(
        session_id=session_id,
        hc_user_id=hc_user.id,
        client_id=client_rec.id,
        original_filename="client_notes.txt",
        storage_path="hc-test/notes.txt",
        mime_type="text/plain",
        size_bytes=20,
        is_zoom_summary=False,  # NOT a Zoom file
    )
    db.add(cf)
    await db.flush()

    await _draft_and_patch_mom(http_client, session_id, hc_headers)

    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    assert result.scalar() >= 1


@pytest.mark.asyncio
async def test_no_files_allows_snippet_capture(
    http_client, hc_headers, session_id, db, hc_user, client_rec
):
    """With no files uploaded, substantial MOM edits still capture style snippets."""
    client_rec.code = "CP0001"
    await db.flush()

    # No ClientFile rows inserted

    with patch("src.llm_service.call_openrouter") as mock_or:
        mock_or.return_value = _make_openrouter_result(_MOCK_MOM_JSON)
        r_draft = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft",
            headers=hc_headers,
            json={"session_notes": "Good session with no files."},
        )
    assert r_draft.status_code == 200, r_draft.text
    draft_text = r_draft.json()["draft_text"]

    edited_text = draft_text + " Extra content added by HC to ensure substantial diff here."
    r_patch = await http_client.patch(
        f"/api/sessions/{session_id}/mom",
        headers=hc_headers,
        json={"final_text": edited_text, "status": "reviewed"},
    )
    assert r_patch.status_code == 200, r_patch.text

    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    assert result.scalar() >= 1
