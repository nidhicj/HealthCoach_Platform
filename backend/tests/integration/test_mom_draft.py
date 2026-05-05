"""Integration tests for POST /api/sessions/{id}/mom/draft, brief, snippet capture."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa

from src.auth.jwt_utils import create_access_token
from src.config import get_settings

_MOCK_MOM_JSON = json.dumps({
    "summary": "Client made progress on nutrition goals.",
    "key_discussion_points": ["Hydration targets", "Sleep schedule"],
    "action_items": [{"description": "Drink 2.5L water daily", "due_date": "2026-06-08"}],
    "follow_ups": ["Check weight next session"],
    "hc_closing_note": "Great session.",
})

_MOCK_BRIEF_JSON = json.dumps({
    "context_summary": "Client has been active. One open action item.",
    "open_action_items": ["Drink 2.5L water daily"],
    "triage_flags": [],
    "suggested_topics": ["Review hydration progress"],
})


def _mock_http(content: str, model: str = "meta-llama/llama-3.3-70b-instruct:free") -> AsyncMock:
    """Return a mock make_http_client() context manager whose .post() returns a valid OR response."""
    response_data = {
        "id": "gen-abc123",
        "model": model,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 80},
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_data
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_resp)
    return mock_http


# ── MOM draft ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mom_draft_creates_mom_with_llm_content(http_client, hc_headers, session_id):
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        r = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft",
            headers=hc_headers,
            json={"session_notes": "Client discussed hydration goals."},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "draft"
    assert data["draft_text"]
    assert data["llm_call_id"] is not None


@pytest.mark.asyncio
async def test_mom_draft_writes_llm_calls_row(http_client, hc_headers, session_id, db):
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        r = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft",
            headers=hc_headers,
            json={"session_notes": "Good hydration discussion."},
        )

    assert r.status_code == 200
    llm_call_id = r.json()["llm_call_id"]

    result = await db.execute(
        sa.text("SELECT model_requested, validation_failed, use_case FROM llm_calls WHERE id = :id"),
        {"id": llm_call_id},
    )
    row = result.first()
    assert row is not None
    assert row.validation_failed is False
    assert row.use_case == "mom_generation"


@pytest.mark.asyncio
async def test_mom_draft_wrong_hc_returns_404(http_client, session_id):
    other_hc_id = str(uuid.uuid4())
    token = create_access_token(
        sub=other_hc_id, role="hc", hc_id=other_hc_id,
        private_key=get_settings().jwt_private_key,
    )
    r = await http_client.post(
        f"/api/sessions/{session_id}/mom/draft",
        headers={"Authorization": f"Bearer {token}"},
        json={"session_notes": "..."},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mom_draft_missing_token_returns_401(http_client, session_id):
    r = await http_client.post(f"/api/sessions/{session_id}/mom/draft", json={"session_notes": "x"})
    assert r.status_code == 401


# ── Snippet capture on PATCH ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_mom_with_ai_draft_captures_snippet(
    http_client, hc_headers, session_id, db, hc_user
):
    """After AI drafting, PATCHing final_text captures a snippet."""
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        r = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft",
            headers=hc_headers,
            json={"session_notes": "Good session today."},
        )
    assert r.status_code == 200

    edited_text = (
        "Client CP0001 made excellent progress on hydration. "
        "Aim for 2.5L water daily measured with a tracking bottle. "
        "Sleep schedule improved from 10pm to 9:30pm — maintain this."
    )
    r2 = await http_client.patch(
        f"/api/sessions/{session_id}/mom",
        headers=hc_headers,
        json={"final_text": edited_text},
    )
    assert r2.status_code == 200

    result = await db.execute(
        sa.text("SELECT snippet_type FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    rows = result.fetchall()
    assert len(rows) >= 1
    assert rows[0].snippet_type == "edit"


@pytest.mark.asyncio
async def test_patch_manual_mom_does_not_capture_snippet(
    http_client, hc_headers, session_id, db, hc_user
):
    """Manually entered MOM (no llm_call_id) must NOT capture snippets on PATCH."""
    await http_client.post(
        f"/api/sessions/{session_id}/mom",
        headers=hc_headers,
        json={"draft_text": "I typed this myself without AI."},
    )
    await http_client.patch(
        f"/api/sessions/{session_id}/mom",
        headers=hc_headers,
        json={"final_text": "I edited this significantly with many new words added here for content."},
    )

    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"),
        {"hc": hc_user.id},
    )
    assert result.scalar() == 0


# ── Brief ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_brief_generates_and_caches(http_client, hc_headers, session_id, db):
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_BRIEF_JSON)):
        r1 = await http_client.get(f"/api/sessions/{session_id}/brief", headers=hc_headers)
        r2 = await http_client.get(f"/api/sessions/{session_id}/brief", headers=hc_headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["brief_text"] == r2.json()["brief_text"]

    # Only one llm_calls row (second GET hit cache)
    result = await db.execute(
        sa.text(
            "SELECT COUNT(*) FROM llm_calls WHERE use_case = 'brief_generation' AND session_id = :sid"
        ),
        {"sid": session_id},
    )
    assert result.scalar() == 1
