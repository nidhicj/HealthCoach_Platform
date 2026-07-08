"""Integration tests for POST /mom/freeze — promotes drafted action items to real rows."""
import json
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from src.db.models import ActionItem


_MOCK_JSON = json.dumps({
    "summary": "Good session.",
    "key_discussion_points": [],
    "action_items": [
        {"description": "Walk daily", "due_date": "2026-07-15"},
        {"description": "Cut sugar", "due_date": None},
    ],
    "follow_ups": [],
    "hc_closing_note": "Nice work.",
})


def _mock_http(content: str):
    from unittest.mock import AsyncMock, MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "gen-1", "model": "meta-llama/llama-3.3-70b-instruct:free",
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 40},
    }
    mock_resp.raise_for_status = MagicMock()
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_resp)
    return mock_http


@pytest.mark.asyncio
async def test_freeze_creates_action_item_rows_and_sets_reviewed(http_client, hc_headers, db, session_id):
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "notes"},
        )

    r = await http_client.post(f"/api/sessions/{session_id}/mom/freeze", headers=hc_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "reviewed"

    rows = (await db.execute(
        sa.select(ActionItem).where(ActionItem.session_id == session_id)
    )).scalars().all()
    descriptions = sorted(item.description for item in rows)
    assert descriptions == ["Cut sugar", "Walk daily"]
    walk_item = next(i for i in rows if i.description == "Walk daily")
    assert str(walk_item.due_date) == "2026-07-15"


@pytest.mark.asyncio
async def test_freeze_requires_draft_status(http_client, hc_headers, session_id):
    """Freezing twice (already reviewed/sent) is rejected, not silently repeated."""
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "notes"},
        )
    await http_client.post(f"/api/sessions/{session_id}/mom/freeze", headers=hc_headers)

    r = await http_client.post(f"/api/sessions/{session_id}/mom/freeze", headers=hc_headers)
    assert r.status_code == 409
