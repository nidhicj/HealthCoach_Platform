"""Integration tests for MOM re-draft workflow. P5 Part A."""
import json
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
async def test_redraft_overwrites_draft_text_and_clears_final_text(http_client, hc_headers, session_id):
    """Re-draft overwrites draft_text and clears final_text."""
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        # First draft
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "first notes"},
        )
    # Finalize MOM
    await http_client.patch(
        f"/api/sessions/{session_id}/mom", headers=hc_headers,
        json={"final_text": "Finalized MOM text here."},
    )
    r_get = await http_client.get(f"/api/sessions/{session_id}/mom", headers=hc_headers)
    assert r_get.json()["final_text"] == "Finalized MOM text here."

    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        # Re-draft
        r_redraft = await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "second notes after more thought"},
        )
    assert r_redraft.status_code == 200
    # final_text is cleared on re-draft
    r2 = await http_client.get(f"/api/sessions/{session_id}/mom", headers=hc_headers)
    assert r2.json()["final_text"] is None


@pytest.mark.asyncio
async def test_redraft_produces_second_llm_calls_row(http_client, hc_headers, session_id, db):
    """Two consecutive /mom/draft calls produce two llm_calls rows."""
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "first"},
        )
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "second"},
        )
    result = await db.execute(
        sa.text(
            "SELECT COUNT(*) FROM llm_calls WHERE session_id = :sid AND use_case = 'mom_generation'"
        ),
        {"sid": session_id},
    )
    assert result.scalar() == 2


@pytest.mark.asyncio
async def test_manual_mom_patch_does_not_capture_snippet(
    http_client, hc_headers, hc_user, session_id, db
):
    """Manual MOM (no llm_call_id) → PATCH final_text does not capture snippet."""
    await http_client.post(
        f"/api/sessions/{session_id}/mom", headers=hc_headers,
        json={"draft_text": "I typed this myself."},
    )
    await http_client.patch(
        f"/api/sessions/{session_id}/mom", headers=hc_headers,
        json={"final_text": "I edited this significantly with many new words here."},
    )
    result = await db.execute(
        sa.text("SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = :hc"), {"hc": hc_user.id}
    )
    assert result.scalar() == 0


@pytest.mark.asyncio
async def test_patch_mom_updates_action_items_draft(http_client, hc_headers, session_id):
    """HC can edit the structured action-items list independently of the free-text review."""
    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "notes"},
        )

    edited = [{"description": "Drink 3L daily", "due_date": "2026-07-20"}]
    r = await http_client.patch(
        f"/api/sessions/{session_id}/mom", headers=hc_headers,
        json={"action_items_draft": edited},
    )
    assert r.status_code == 200, r.text
    assert r.json()["action_items_draft"] == edited


@pytest.mark.asyncio
async def test_send_mom_requires_reviewed_status(http_client, hc_headers, db, hc_user, session_id):
    """Sending before Freeze is rejected."""
    from src.db.models import Client
    import sqlalchemy as sa
    client = (await db.execute(
        sa.select(Client).where(Client.hc_user_id == hc_user.id)
    )).scalar_one()
    client.email = "client@example.com"
    await db.flush()

    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "notes"},
        )

    r = await http_client.post(
        f"/api/sessions/{session_id}/mom/send", headers=hc_headers,
        json={"message": "Great work this week!"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_send_mom_emails_action_items_and_marks_sent(http_client, hc_headers, db, hc_user, session_id):
    from src.db.models import Client
    import sqlalchemy as sa
    client = (await db.execute(
        sa.select(Client).where(Client.hc_user_id == hc_user.id)
    )).scalar_one()
    client.email = "client@example.com"
    await db.flush()

    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "notes"},
        )
    await http_client.post(f"/api/sessions/{session_id}/mom/freeze", headers=hc_headers)

    with patch("src.api.sessions.send_action_items_email") as mock_email:
        r = await http_client.post(
            f"/api/sessions/{session_id}/mom/send", headers=hc_headers,
            json={"message": "Great work this week!"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "sent"
    assert body["sent_at"] is not None
    mock_email.assert_called_once()
    call_kwargs = mock_email.call_args.kwargs
    assert call_kwargs["to"] == "client@example.com"
    assert call_kwargs["message"] == "Great work this week!"
    assert call_kwargs["action_items"] == [
        {"description": "Drink 2.5L daily", "due_date": "2026-06-08"}
    ]


@pytest.mark.asyncio
async def test_send_mom_returns_422_when_client_has_no_email(http_client, hc_headers, db, hc_user, session_id):
    from src.db.models import Client
    import sqlalchemy as sa
    client = (await db.execute(
        sa.select(Client).where(Client.hc_user_id == hc_user.id)
    )).scalar_one()
    client.email = None
    await db.flush()

    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "notes"},
        )
    await http_client.post(f"/api/sessions/{session_id}/mom/freeze", headers=hc_headers)

    with patch("src.api.sessions.send_action_items_email"):
        r = await http_client.post(
            f"/api/sessions/{session_id}/mom/send", headers=hc_headers,
            json={"message": "hi"},
        )
    assert r.status_code == 422
    assert "email" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_mom_already_sent_is_idempotent_no_op(http_client, hc_headers, db, hc_user, session_id):
    """Calling send twice does not send a second email — matches D-13, no resend in this phase."""
    from src.db.models import Client
    import sqlalchemy as sa
    client = (await db.execute(
        sa.select(Client).where(Client.hc_user_id == hc_user.id)
    )).scalar_one()
    client.email = "client@example.com"
    await db.flush()

    with patch("src.llm_service.client.make_http_client", return_value=_mock_http(_MOCK_MOM_JSON)):
        await http_client.post(
            f"/api/sessions/{session_id}/mom/draft", headers=hc_headers,
            json={"session_notes": "notes"},
        )
    await http_client.post(f"/api/sessions/{session_id}/mom/freeze", headers=hc_headers)

    with patch("src.api.sessions.send_action_items_email") as mock_email:
        await http_client.post(
            f"/api/sessions/{session_id}/mom/send", headers=hc_headers, json={"message": "hi"},
        )
        await http_client.post(
            f"/api/sessions/{session_id}/mom/send", headers=hc_headers, json={"message": "hi again"},
        )

    assert mock_email.call_count == 1
