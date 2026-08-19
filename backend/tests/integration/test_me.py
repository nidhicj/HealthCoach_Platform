"""Integration tests for /api/me/* client-facing endpoints. P3."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_session(http_client, headers, client_id: str, num: int = 1) -> dict:
    r = await http_client.post(
        "/api/sessions", headers=headers,
        json={"client_id": client_id, "session_number": num, "scheduled_at": "2026-06-01T10:00:00Z"},
    )
    assert r.status_code == 201
    return r.json()


async def _make_mom_sent(http_client, headers, session_id: str, db=None, client_id: str | None = None) -> dict:
    """Create a MOM, freeze it, and send it (mocking the actual email delivery).

    Sending requires status == "reviewed" (post-freeze) and a client with an
    email on record — see Unit_004 PHASE-01 Task 6.
    """
    r = await http_client.post(
        f"/api/sessions/{session_id}/mom", headers=headers,
        json={"draft_text": "Session recap draft"},
    )
    assert r.status_code == 201

    if db is not None and client_id is not None:
        import sqlalchemy as sa
        from src.db.models import Client
        client = (await db.execute(
            sa.select(Client).where(Client.id == uuid.UUID(client_id))
        )).scalar_one()
        client.email = "client@example.com"
        await db.flush()

    await http_client.post(f"/api/sessions/{session_id}/mom/freeze", headers=headers)

    with patch("src.api.sessions.send_action_items_email"):
        r2 = await http_client.post(
            f"/api/sessions/{session_id}/mom/send", headers=headers,
            json={"message": "Here are your action items."},
        )
    assert r2.status_code == 200, r2.text
    return r2.json()


# ── POST /api/me/check-ins ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_submit_check_in_returns_201(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/check-ins", headers=client_headers,
        json={"payload": {"mood": "good", "energy": 8}},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["client_id"] == str(client_rec.id)
    assert body["payload"] == {"mood": "good", "energy": 8}
    assert body["sentiment_flag"] is None


@pytest.mark.asyncio
async def test_hc_token_cannot_submit_check_in(http_client, hc_headers):
    r = await http_client.post(
        "/api/me/check-ins", headers=hc_headers,
        json={"payload": {"mood": "ok"}},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_client_without_linked_record_returns_404(http_client, hc_user, client_user):
    """Client user with no Client record in the DB gets 404."""
    from tests.integration.conftest import auth_headers
    unlinked_headers = auth_headers(client_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.post(
        "/api/me/check-ins", headers=unlinked_headers,
        json={"payload": {"mood": "ok"}},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_client_answer_fills_pending_row_not_a_new_one(http_client, hc_headers, client_headers, client_rec):
    req_r = await http_client.post(f"/api/clients/{client_rec.id}/check-ins/request", headers=hc_headers)
    pending_id = req_r.json()["id"]

    ans_r = await http_client.post(
        "/api/me/check-ins", headers=client_headers,
        json={"payload": {"metrics": {"energy": 7}}},
    )
    assert ans_r.status_code == 201
    assert ans_r.json()["id"] == pending_id  # same row, not a new one
    assert ans_r.json()["payload"] == {"metrics": {"energy": 7}}
    assert ans_r.json()["requested_at"] is not None


@pytest.mark.asyncio
async def test_client_answer_with_no_pending_request_creates_ad_hoc_row(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/check-ins", headers=client_headers,
        json={"payload": {"metrics": {"mood": 8}}},
    )
    assert r.status_code == 201
    assert r.json()["requested_at"] is None


@pytest.mark.asyncio
async def test_client_lists_own_check_ins(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(
        "/api/me/check-ins", headers=client_headers, json={"payload": {"metrics": {"energy": 5}}},
    )
    r = await http_client.get("/api/me/check-ins", headers=client_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


@pytest.mark.asyncio
async def test_client_sees_pending_request_in_own_list(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(f"/api/clients/{client_rec.id}/check-ins/request", headers=hc_headers)
    r = await http_client.get("/api/me/check-ins", headers=client_headers)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["payload"] is None
    assert items[0]["requested_at"] is not None


# ── GET /api/me/moms ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_sees_sent_moms(http_client, hc_headers, client_headers, client_rec, db):
    sess = await _make_session(http_client, hc_headers, str(client_rec.id))
    await _make_mom_sent(http_client, hc_headers, sess["id"], db=db, client_id=str(client_rec.id))

    r = await http_client.get("/api/me/moms", headers=client_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "sent"
    assert items[0]["client_id"] == str(client_rec.id)


@pytest.mark.asyncio
async def test_client_cannot_see_draft_moms(http_client, hc_headers, client_headers, client_rec):
    sess = await _make_session(http_client, hc_headers, str(client_rec.id))
    await http_client.post(
        f"/api/sessions/{sess['id']}/mom", headers=hc_headers,
        json={"draft_text": "Draft only"},
    )

    r = await http_client.get("/api/me/moms", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_client_sees_empty_moms_list(http_client, client_headers, client_rec):
    r = await http_client.get("/api/me/moms", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


# ── GET /api/me/action-items ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_sees_own_action_items(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": str(client_rec.id), "description": "Walk 30 min daily"},
    )

    r = await http_client.get("/api/me/action-items", headers=client_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["description"] == "Walk 30 min daily"


@pytest.mark.asyncio
async def test_client_sees_empty_action_items(http_client, client_headers, client_rec):
    r = await http_client.get("/api/me/action-items", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


# ── GET /api/me/moms/{id} ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_can_read_sent_mom_by_id(http_client, hc_headers, client_headers, client_rec, db):
    sess = await _make_session(http_client, hc_headers, str(client_rec.id))
    sent = await _make_mom_sent(http_client, hc_headers, sess["id"], db=db, client_id=str(client_rec.id))

    r = await http_client.get(f"/api/me/moms/{sent['id']}", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_client_cannot_read_draft_mom_by_id(http_client, hc_headers, client_headers, client_rec):
    sess = await _make_session(http_client, hc_headers, str(client_rec.id))
    draft_r = await http_client.post(
        f"/api/sessions/{sess['id']}/mom", headers=hc_headers,
        json={"draft_text": "Draft only"},
    )
    draft_id = draft_r.json()["id"]

    r = await http_client.get(f"/api/me/moms/{draft_id}", headers=client_headers)
    assert r.status_code == 404


# ── PATCH /api/me/action-items/{id} ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_can_mark_action_item_in_progress(http_client, hc_headers, client_headers, client_rec):
    ai_r = await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": str(client_rec.id), "description": "Walk daily"},
    )
    ai_id = ai_r.json()["id"]

    r = await http_client.patch(
        f"/api/me/action-items/{ai_id}", headers=client_headers,
        json={"status": "in_progress"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_client_can_mark_action_item_completed(http_client, hc_headers, client_headers, client_rec):
    ai_r = await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": str(client_rec.id), "description": "Drink water"},
    )
    ai_id = ai_r.json()["id"]

    r = await http_client.patch(
        f"/api/me/action-items/{ai_id}", headers=client_headers,
        json={"status": "completed"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_client_cannot_patch_other_clients_action_item(http_client, hc_headers, client_headers, db):
    """Client cannot update an action item belonging to a different client."""
    other_client_r = await http_client.post(
        "/api/clients", headers=hc_headers, json={"full_name": "Other Client"},
    )
    other_client_id = other_client_r.json()["id"]
    ai_r = await http_client.post(
        "/api/action-items", headers=hc_headers,
        json={"client_id": other_client_id, "description": "Other's task"},
    )
    ai_id = ai_r.json()["id"]

    r = await http_client.patch(
        f"/api/me/action-items/{ai_id}", headers=client_headers,
        json={"status": "completed"},
    )
    assert r.status_code == 404


# ── POST /api/me/messages ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_can_send_message(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/messages", headers=client_headers,
        data={"body": "Quick question about my meal plan"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["direction"] == "client"
    assert body["body"] == "Quick question about my meal plan"
    assert body["has_attachment"] is False
    assert body["client_id"] == str(client_rec.id)


@pytest.mark.asyncio
async def test_client_message_does_not_trigger_hc_email(http_client, client_headers, client_rec):
    # me.py deliberately never imports send_message_notification_email (D-24), so
    # patching it at its definition site (rather than "src.api.me.<name>", which
    # doesn't exist there) proves no code path in this request sends an email.
    with patch("src.lib.email.send_message_notification_email") as mock_email:
        r = await http_client.post(
            "/api/me/messages", headers=client_headers,
            data={"body": "hi"},
        )
    assert r.status_code == 201
    mock_email.assert_not_called()  # D-24: HC never gets emailed for a client message


@pytest.mark.asyncio
async def test_client_send_message_with_attachment(http_client, client_headers, client_rec):
    with patch("src.api.me.s3_put", new_callable=AsyncMock) as mock_put:
        r = await http_client.post(
            "/api/me/messages", headers=client_headers,
            data={"body": "Here's a photo"},
            files={"attachment": ("meal.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201, r.text
    assert r.json()["has_attachment"] is True
    assert r.json()["attachment_original_filename"] == "meal.jpg"
    mock_put.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_send_message_rejects_non_image_attachment(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/messages", headers=client_headers,
        data={"body": "doc"},
        files={"attachment": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_client_send_message_rejects_empty_body(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/messages", headers=client_headers,
        data={"body": ""},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_client_send_message_rejects_whitespace_only_body(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/messages", headers=client_headers,
        data={"body": "   \n\t  "},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_client_without_linked_record_cannot_send_message(http_client, hc_user, client_user):
    from tests.integration.conftest import auth_headers
    unlinked_headers = auth_headers(client_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.post(
        "/api/me/messages", headers=unlinked_headers,
        data={"body": "hi"},
    )
    assert r.status_code == 404


# ── GET /api/me/messages ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_lists_own_messages(http_client, hc_headers, client_headers, client_rec):
    await http_client.post(
        f"/api/clients/{client_rec.id}/messages", headers=hc_headers, data={"body": "From your coach"},
    )
    await http_client.post("/api/me/messages", headers=client_headers, data={"body": "From me"})

    r = await http_client.get("/api/me/messages", headers=client_headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


@pytest.mark.asyncio
async def test_client_cannot_list_other_clients_messages(http_client, hc_headers, client_headers, client_rec, db):
    other = (await http_client.post("/api/clients", headers=hc_headers, json={"full_name": "Other"})).json()
    await http_client.post(f"/api/clients/{other['id']}/messages", headers=hc_headers, data={"body": "not yours"})

    r = await http_client.get("/api/me/messages", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_client_sees_empty_messages_list(http_client, client_headers, client_rec):
    r = await http_client.get("/api/me/messages", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_client_lists_messages_returns_correct_order(http_client, client_headers, client_rec, db):
    import sqlalchemy as sa
    from datetime import datetime, timedelta, timezone
    from src.db.models import ClientMessage

    bodies = ["first", "second", "third"]
    ids = []
    for b in bodies:
        r = await http_client.post("/api/me/messages", headers=client_headers, data={"body": b})
        assert r.status_code == 201
        ids.append(r.json()["id"])

    # Postgres now() is fixed for the whole test-harness transaction (even across
    # savepoints), so every row above got the same server-default sent_at. Set
    # distinct, increasing timestamps directly so the ordering assertion below
    # actually exercises the ORDER BY, not insertion luck. See test_messages.py.
    base = datetime.now(timezone.utc)
    for i, msg_id in enumerate(ids):
        row = (await db.execute(sa.select(ClientMessage).where(ClientMessage.id == msg_id))).scalar_one()
        row.sent_at = base + timedelta(seconds=i)
    await db.flush()
    await db.commit()

    r = await http_client.get("/api/me/messages", headers=client_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [item["body"] for item in items] == list(reversed(bodies))


# ── GET /api/me/messages/{id}/attachment ──────────────────────────────────────


@pytest.mark.asyncio
async def test_client_get_message_attachment_happy_path(http_client, client_headers, client_rec):
    with patch("src.api.me.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            "/api/me/messages", headers=client_headers,
            data={"body": "Here's a photo"},
            files={"attachment": ("meal.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201
    msg_id = r.json()["id"]

    with patch("src.api.me.s3_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = b"\xff\xd8\xff"
        r2 = await http_client.get(
            f"/api/me/messages/{msg_id}/attachment", headers=client_headers,
        )
    assert r2.status_code == 200
    assert r2.content == b"\xff\xd8\xff"
    assert r2.headers["content-type"] == "image/jpeg"
    mock_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_client_get_message_attachment_returns_404_when_no_attachment(http_client, client_headers, client_rec):
    r = await http_client.post(
        "/api/me/messages", headers=client_headers,
        data={"body": "text only, no attachment"},
    )
    assert r.status_code == 201
    msg_id = r.json()["id"]

    r2 = await http_client.get(
        f"/api/me/messages/{msg_id}/attachment", headers=client_headers,
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_client_cannot_get_attachment_for_other_clients_message(http_client, hc_headers, client_headers, db):
    other = (await http_client.post("/api/clients", headers=hc_headers, json={"full_name": "Other2"})).json()
    with patch("src.api.messages.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/clients/{other['id']}/messages", headers=hc_headers,
            data={"body": "not yours"},
            files={"attachment": ("ref.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201
    msg_id = r.json()["id"]

    r2 = await http_client.get(
        f"/api/me/messages/{msg_id}/attachment", headers=client_headers,
    )
    assert r2.status_code == 404
