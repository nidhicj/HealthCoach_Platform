# backend/tests/integration/test_messages.py
from unittest.mock import AsyncMock, patch

import pytest


async def _make_client(http_client, headers) -> dict:
    import uuid
    r = await http_client.post("/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_hc_can_send_text_only_message(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        data={"body": "How's the new routine going?"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["direction"] == "coach"
    assert body["body"] == "How's the new routine going?"
    assert body["has_attachment"] is False


@pytest.mark.asyncio
async def test_hc_send_message_with_attachment(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    with patch("src.api.messages.s3_put", new_callable=AsyncMock) as mock_put:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Here's a reference photo"},
            files={"attachment": ("ref.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201, r.text
    assert r.json()["has_attachment"] is True
    assert r.json()["attachment_original_filename"] == "ref.jpg"
    mock_put.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_rejects_non_image_attachment(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        data={"body": "doc"},
        files={"attachment": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_hc_reply_emails_client_when_email_on_record(http_client, hc_headers, hc_user, db):
    import sqlalchemy as sa
    from src.db.models import Client
    hc_user.display_name = "Coach Priya"
    await db.flush()
    client = await _make_client(http_client, hc_headers)
    row = (await db.execute(sa.select(Client).where(Client.id == client["id"]))).scalar_one()
    row.email = "client@example.com"
    await db.flush()
    await db.commit()

    with patch("src.api.messages.send_message_notification_email") as mock_email:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Great progress this week!"},
        )
    assert r.status_code == 201
    mock_email.assert_called_once()
    assert mock_email.call_args.kwargs["coach_name"] == "Coach Priya"


@pytest.mark.asyncio
async def test_hc_reply_email_uses_generic_fallback_when_hc_has_no_display_name(http_client, hc_headers, db):
    import sqlalchemy as sa
    from src.db.models import Client
    client = await _make_client(http_client, hc_headers)
    row = (await db.execute(sa.select(Client).where(Client.id == client["id"]))).scalar_one()
    row.email = "client2@example.com"
    await db.flush()
    await db.commit()

    with patch("src.api.messages.send_message_notification_email") as mock_email:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Hello"},
        )
    assert r.status_code == 201
    # hc_user fixture has no display_name set — must not leak a raw UUID into the email.
    coach_name = mock_email.call_args.kwargs["coach_name"]
    assert coach_name == "Your coach"


@pytest.mark.asyncio
async def test_hc_reply_skips_email_when_client_has_no_email(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    with patch("src.api.messages.send_message_notification_email") as mock_email:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Hi there"},
        )
    assert r.status_code == 201
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_send_message_rejects_empty_body(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        data={"body": ""},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_send_message_rejects_whitespace_only_body(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        data={"body": "   \n\t  "},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_client_messages_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/messages", headers=hc2_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_client_messages_returns_correct_order(http_client, hc_headers, db):
    import sqlalchemy as sa
    from datetime import datetime, timedelta, timezone
    from src.db.models import ClientMessage

    client = await _make_client(http_client, hc_headers)
    bodies = ["first", "second", "third"]
    ids = []
    for b in bodies:
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers, data={"body": b},
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])

    # The test harness runs each test inside one DB transaction, and Postgres's
    # now() is fixed for the whole transaction — so every row above got the same
    # server-default sent_at. Set distinct, increasing timestamps directly so the
    # ordering assertion below actually exercises the ORDER BY, not insertion luck.
    base = datetime.now(timezone.utc)
    for i, msg_id in enumerate(ids):
        row = (await db.execute(sa.select(ClientMessage).where(ClientMessage.id == msg_id))).scalar_one()
        row.sent_at = base + timedelta(seconds=i)
    await db.flush()
    await db.commit()

    r = await http_client.get(f"/api/clients/{client['id']}/messages", headers=hc_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [item["body"] for item in items] == list(reversed(bodies))


@pytest.mark.asyncio
async def test_list_client_messages_paginates_with_cursor(http_client, hc_headers, db):
    import sqlalchemy as sa
    from datetime import datetime, timedelta, timezone
    from src.db.models import ClientMessage

    client = await _make_client(http_client, hc_headers)
    ids = []
    for i in range(5):
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers, data={"body": f"msg-{i}"},
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])

    base = datetime.now(timezone.utc)
    for i, msg_id in enumerate(ids):
        row = (await db.execute(sa.select(ClientMessage).where(ClientMessage.id == msg_id))).scalar_one()
        row.sent_at = base + timedelta(seconds=i)
    await db.flush()
    await db.commit()

    r1 = await http_client.get(
        f"/api/clients/{client['id']}/messages", headers=hc_headers, params={"limit": 2},
    )
    assert r1.status_code == 200
    page1 = r1.json()
    assert [item["body"] for item in page1["items"]] == ["msg-4", "msg-3"]
    assert page1["next_cursor"] is not None

    r2 = await http_client.get(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        params={"limit": 2, "cursor": page1["next_cursor"]},
    )
    assert r2.status_code == 200
    page2 = r2.json()
    assert [item["body"] for item in page2["items"]] == ["msg-2", "msg-1"]
    assert page2["next_cursor"] is not None

    r3 = await http_client.get(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        params={"limit": 2, "cursor": page2["next_cursor"]},
    )
    assert r3.status_code == 200
    page3 = r3.json()
    assert [item["body"] for item in page3["items"]] == ["msg-0"]
    assert page3["next_cursor"] is None


@pytest.mark.asyncio
async def test_get_message_attachment_happy_path(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    with patch("src.api.messages.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Here's a reference photo"},
            files={"attachment": ("ref.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201
    msg_id = r.json()["id"]

    with patch("src.api.messages.s3_get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = b"\xff\xd8\xff"
        r2 = await http_client.get(
            f"/api/clients/{client['id']}/messages/{msg_id}/attachment", headers=hc_headers,
        )
    assert r2.status_code == 200
    assert r2.content == b"\xff\xd8\xff"
    assert r2.headers["content-type"] == "image/jpeg"
    mock_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_message_attachment_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    with patch("src.api.messages.s3_put", new_callable=AsyncMock):
        r = await http_client.post(
            f"/api/clients/{client['id']}/messages", headers=hc_headers,
            data={"body": "Here's a reference photo"},
            files={"attachment": ("ref.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
    assert r.status_code == 201
    msg_id = r.json()["id"]

    r2 = await http_client.get(
        f"/api/clients/{client['id']}/messages/{msg_id}/attachment", headers=hc2_headers,
    )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_get_message_attachment_returns_404_when_message_has_no_attachment(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/messages", headers=hc_headers,
        data={"body": "text only, no attachment"},
    )
    assert r.status_code == 201
    msg_id = r.json()["id"]

    r2 = await http_client.get(
        f"/api/clients/{client['id']}/messages/{msg_id}/attachment", headers=hc_headers,
    )
    assert r2.status_code == 404
