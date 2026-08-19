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
async def test_hc_reply_emails_client_when_email_on_record(http_client, hc_headers, db):
    import sqlalchemy as sa
    from src.db.models import Client
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
async def test_list_client_messages_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/messages", headers=hc2_headers)
    assert r.status_code == 404
