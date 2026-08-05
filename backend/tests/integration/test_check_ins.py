"""Integration tests for check-in routes (HC flag + list, client submit). P3."""
import uuid
from unittest.mock import patch

import pytest

from tests.integration.conftest import auth_headers


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_client(http_client, headers, email: str | None = None) -> dict:
    body = {"full_name": f"C-{uuid.uuid4().hex[:4]}"}
    if email is not None:
        body["email"] = email
    r = await http_client.post("/api/clients", headers=headers, json=body)
    assert r.status_code == 201
    return r.json()


async def _submit_check_in(http_client, headers, payload: dict | None = None) -> dict:
    r = await http_client.post(
        "/api/me/check-ins", headers=headers,
        json={"payload": payload or {"mood": "good", "note": "Feeling great"}},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── GET /api/clients/{id}/check-ins ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_client_check_ins_empty(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/check-ins", headers=hc_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_client_check_ins_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(f"/api/clients/{client['id']}/check-ins", headers=hc2_headers)
    assert r.status_code == 404


# ── PATCH /api/check-ins/{id}/flag ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_flag_check_in_sets_sentiment(http_client, hc_headers, hc_user, db):
    """Create a check-in directly in DB (client submit not yet needed), then flag it."""
    from src.db.models import CheckIn

    client_rec = await _make_client(http_client, hc_headers)

    # Create check-in directly — client submit is tested in test_me.py
    ci = CheckIn(
        client_id=uuid.UUID(client_rec["id"]),
        hc_user_id=hc_user.id,
        payload={"mood": "ok"},
    )
    db.add(ci)
    await db.flush()
    await db.commit()

    r = await http_client.patch(
        f"/api/check-ins/{ci.id}/flag", headers=hc_headers,
        json={"sentiment_flag": "concern"},
    )
    assert r.status_code == 200
    assert r.json()["sentiment_flag"] == "concern"


@pytest.mark.asyncio
async def test_flag_check_in_clears_sentiment(http_client, hc_headers, hc_user, db):
    from src.db.models import CheckIn

    client_rec = await _make_client(http_client, hc_headers)
    ci = CheckIn(
        client_id=uuid.UUID(client_rec["id"]),
        hc_user_id=hc_user.id,
        payload={"mood": "ok"},
        sentiment_flag="concern",
    )
    db.add(ci)
    await db.flush()
    await db.commit()

    r = await http_client.patch(
        f"/api/check-ins/{ci.id}/flag", headers=hc_headers,
        json={"sentiment_flag": None},
    )
    assert r.status_code == 200
    assert r.json()["sentiment_flag"] is None


@pytest.mark.asyncio
async def test_flag_check_in_cross_tenant_returns_404(http_client, hc_headers, hc2_headers, hc_user, db):
    from src.db.models import CheckIn

    client_rec = await _make_client(http_client, hc_headers)
    ci = CheckIn(
        client_id=uuid.UUID(client_rec["id"]),
        hc_user_id=hc_user.id,
        payload={"mood": "ok"},
    )
    db.add(ci)
    await db.flush()
    await db.commit()

    r = await http_client.patch(
        f"/api/check-ins/{ci.id}/flag", headers=hc2_headers,
        json={"sentiment_flag": "concern"},
    )
    assert r.status_code == 404


# ── POST /api/clients/{id}/check-ins/request ──

@pytest.mark.asyncio
async def test_hc_can_request_check_in(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)

    r = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["client_id"] == client["id"]
    assert body["payload"] is None
    assert body["requested_at"] is not None


@pytest.mark.asyncio
async def test_hc_cannot_request_second_check_in_while_one_pending(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)

    r1 = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)
    assert r1.status_code == 201

    r2 = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_request_check_in_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)

    r = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc2_headers)
    assert r.status_code == 404


# ── POST /api/clients/{id}/check-ins/request — client notification email ─────


@pytest.mark.asyncio
async def test_request_check_in_sends_reminder_email_when_client_has_email(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers, email="client@example.com")

    with patch("src.api.check_ins.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)

    assert r.status_code == 201, r.text
    mock_email.assert_called_once()
    _, kwargs = mock_email.call_args
    assert kwargs["to"] == "client@example.com"
    assert kwargs["client_name"] == client["full_name"]
    assert kwargs["portal_url"].endswith("/me/checkins")


@pytest.mark.asyncio
async def test_request_check_in_skips_email_when_client_has_no_email(http_client, hc_headers):
    """Client with no email on record: the request still succeeds and creates the
    pending row (mirroring the scheduler's own eligibility filter for the same
    reminder email), it just has no address to notify."""
    client = await _make_client(http_client, hc_headers)
    assert client["email"] is None

    with patch("src.api.check_ins.send_check_in_reminder_email") as mock_email:
        r = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)

    assert r.status_code == 201, r.text
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_request_check_in_succeeds_even_if_email_send_fails(http_client, hc_headers, db):
    """A Resend/API failure while notifying the client must not fail the request —
    the pending check-in row was already committed and the HC's action did succeed."""
    from sqlalchemy import select

    from src.db.models import CheckIn

    client = await _make_client(http_client, hc_headers, email="client@example.com")

    with patch("src.api.check_ins.send_check_in_reminder_email", side_effect=RuntimeError("resend down")):
        r = await http_client.post(f"/api/clients/{client['id']}/check-ins/request", headers=hc_headers)

    assert r.status_code == 201, r.text

    rows = (await db.execute(
        select(CheckIn).where(CheckIn.client_id == uuid.UUID(client["id"]))
    )).scalars().all()
    assert len(rows) == 1
