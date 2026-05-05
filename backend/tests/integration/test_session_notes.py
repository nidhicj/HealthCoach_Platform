"""Integration tests for PATCH /sessions/{id} and session_notes persistence. P5 Part A."""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa

_MOCK_MOM_JSON = json.dumps({
    "summary": "Progress on nutrition.",
    "key_discussion_points": ["Hydration"],
    "action_items": [{"description": "Drink 2.5L daily", "due_date": "2026-06-08"}],
    "follow_ups": [],
    "hc_closing_note": "Good session.",
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


@pytest.mark.asyncio
async def test_get_session_returns_session_notes_field(http_client, hc_headers, session_id):
    """GET /sessions/{id} includes session_notes (None by default)."""
    r = await http_client.get(f"/api/sessions/{session_id}", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert "session_notes" in body
    assert body["session_notes"] is None


@pytest.mark.asyncio
async def test_patch_session_notes_saves_and_get_returns_it(http_client, hc_headers, session_id):
    """PATCH saves session_notes; GET returns updated value."""
    r = await http_client.patch(
        f"/api/sessions/{session_id}", headers=hc_headers,
        json={"session_notes": "Client discussed hydration goals."},
    )
    assert r.status_code == 200
    assert r.json()["session_notes"] == "Client discussed hydration goals."

    r2 = await http_client.get(f"/api/sessions/{session_id}", headers=hc_headers)
    assert r2.json()["session_notes"] == "Client discussed hydration goals."


@pytest.mark.asyncio
async def test_patch_empty_body_does_not_overwrite_session_notes(http_client, hc_headers, session_id):
    """PATCH with no session_notes field does not clear existing notes."""
    await http_client.patch(
        f"/api/sessions/{session_id}", headers=hc_headers,
        json={"session_notes": "original notes"},
    )
    await http_client.patch(f"/api/sessions/{session_id}", headers=hc_headers, json={})
    r = await http_client.get(f"/api/sessions/{session_id}", headers=hc_headers)
    assert r.json()["session_notes"] == "original notes"


@pytest.mark.asyncio
async def test_patch_session_notes_cross_tenant_returns_404(http_client, hc2_headers, session_id):
    """PATCH by wrong HC returns 404."""
    r = await http_client.patch(
        f"/api/sessions/{session_id}", headers=hc2_headers,
        json={"session_notes": "steal"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_draft_mom_persists_session_notes_to_db(http_client, hc_headers, session_id):
    """POST /mom/draft persists session_notes to sessions table before LLM call."""
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        r = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "Today client improved sleep schedule."},
        )
    assert r.status_code == 200
    r2 = await http_client.get(f"/api/sessions/{session_id}", headers=hc_headers)
    assert r2.json()["session_notes"] == "Today client improved sleep schedule."


@pytest.mark.asyncio
async def test_redraft_overwrites_session_notes_and_produces_two_llm_calls(
    http_client, hc_headers, session_id, db
):
    """Two consecutive /mom/draft calls overwrite session_notes and produce 2 llm_calls rows."""
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        r1 = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "first notes"},
        )
        r2 = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "second notes — updated after session"},
        )
    assert r1.status_code == 200
    assert r2.status_code == 200

    r3 = await http_client.get(f"/api/sessions/{session_id}", headers=hc_headers)
    assert r3.json()["session_notes"] == "second notes — updated after session"

    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM llm_calls WHERE session_id = :sid AND use_case = 'mom_generation'"),
        {"sid": session_id},
    )
    assert result.scalar() == 2
