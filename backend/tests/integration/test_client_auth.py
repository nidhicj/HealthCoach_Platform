"""Integration tests for client OAuth callback flow. P3."""
import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt_utils import decode_access_token
from src.auth.oauth import GoogleUserInfo
from src.config import get_settings
from src.db.models import Client, ClientInviteToken, User

_FAKE_GOOGLE_USER = GoogleUserInfo(
    sub="google-client-sub-abc",
    email="client@example.com",
    name="Alice Client",
    picture=None,
)


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_client_and_invite(http_client, hc_headers) -> tuple[dict, str]:
    """Create a client and generate an invite token. Returns (client_body, raw_token)."""
    cr = await http_client.post(
        "/api/clients", headers=hc_headers,
        json={"full_name": f"Inv-{uuid.uuid4().hex[:4]}"},
    )
    assert cr.status_code == 201
    client = cr.json()

    ir = await http_client.post(f"/api/clients/{client['id']}/invite", headers=hc_headers)
    assert ir.status_code == 201
    return client, ir.json()["invite_token"]


async def _start_and_get_state(http_client, invite_token: str) -> str:
    """Call /api/auth/client/start and extract the state from the returned auth_url."""
    r = await http_client.get("/api/auth/client/start", params={"invite": invite_token})
    assert r.status_code == 200, r.text
    match = re.search(r"[?&]state=([^&]+)", r.json()["auth_url"])
    assert match, "state not found in auth_url"
    return match.group(1)


# ── GET /api/auth/client/start ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_start_returns_google_auth_url(http_client, hc_headers):
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)
    r = await http_client.get("/api/auth/client/start", params={"invite": invite_token})
    assert r.status_code == 200
    assert "accounts.google.com" in r.json()["auth_url"]


@pytest.mark.asyncio
async def test_client_start_invalid_token_returns_400(http_client):
    r = await http_client.get("/api/auth/client/start", params={"invite": "totally-fake-token"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_client_start_used_invite_returns_400(http_client, hc_headers, db: AsyncSession):
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)
    token_hash = hashlib.sha256(invite_token.encode()).hexdigest()
    invite = (await db.execute(
        select(ClientInviteToken).where(ClientInviteToken.token_hash == token_hash)
    )).scalar_one()
    invite.used_at = datetime.now(timezone.utc)
    await db.flush()

    r = await http_client.get("/api/auth/client/start", params={"invite": invite_token})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_client_start_expired_invite_returns_400(http_client, hc_headers, db: AsyncSession):
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)
    token_hash = hashlib.sha256(invite_token.encode()).hexdigest()
    invite = (await db.execute(
        select(ClientInviteToken).where(ClientInviteToken.token_hash == token_hash)
    )).scalar_one()
    invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.flush()

    r = await http_client.get("/api/auth/client/start", params={"invite": invite_token})
    assert r.status_code == 400


# ── GET /api/auth/client/callback ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_client_callback_issues_client_jwt(http_client, hc_headers, hc_user):
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)
    state = await _start_and_get_state(http_client, invite_token)

    with patch("src.auth.router.exchange_code_for_userinfo", new=AsyncMock(return_value=_FAKE_GOOGLE_USER)):
        r = await http_client.get(
            "/api/auth/client/callback",
            params={"code": "fake-google-code", "state": state},
        )
    assert r.status_code == 200, r.text

    claims = decode_access_token(r.json()["access_token"], public_key=get_settings().jwt_public_key)
    assert claims.role == "client"
    assert claims.hc_id == str(hc_user.id)


@pytest.mark.asyncio
async def test_client_callback_links_client_record(http_client, hc_headers, db: AsyncSession):
    client_body, invite_token = await _make_client_and_invite(http_client, hc_headers)
    state = await _start_and_get_state(http_client, invite_token)

    with patch("src.auth.router.exchange_code_for_userinfo", new=AsyncMock(return_value=_FAKE_GOOGLE_USER)):
        r = await http_client.get(
            "/api/auth/client/callback",
            params={"code": "fake-google-code", "state": state},
        )
    assert r.status_code == 200, r.text

    client = (await db.execute(select(Client).where(Client.id == uuid.UUID(client_body["id"])))).scalar_one()
    assert client.user_id is not None


@pytest.mark.asyncio
async def test_client_callback_marks_invite_used(http_client, hc_headers, db: AsyncSession):
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)
    state = await _start_and_get_state(http_client, invite_token)

    with patch("src.auth.router.exchange_code_for_userinfo", new=AsyncMock(return_value=_FAKE_GOOGLE_USER)):
        await http_client.get(
            "/api/auth/client/callback",
            params={"code": "fake-google-code", "state": state},
        )

    token_hash = hashlib.sha256(invite_token.encode()).hexdigest()
    invite = (await db.execute(
        select(ClientInviteToken).where(ClientInviteToken.token_hash == token_hash)
    )).scalar_one()
    assert invite.used_at is not None


@pytest.mark.asyncio
async def test_client_callback_second_use_returns_400(http_client, hc_headers):
    """Using an already-redeemed invite for a second OAuth dance is rejected."""
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)

    state1 = await _start_and_get_state(http_client, invite_token)
    with patch("src.auth.router.exchange_code_for_userinfo", new=AsyncMock(return_value=_FAKE_GOOGLE_USER)):
        r1 = await http_client.get(
            "/api/auth/client/callback",
            params={"code": "fake-code-1", "state": state1},
        )
    assert r1.status_code == 200

    # Attacker tries to start a second flow with the same (now used) invite
    r2 = await http_client.get("/api/auth/client/start", params={"invite": invite_token})
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_client_callback_invalid_state_returns_400(http_client):
    r = await http_client.get(
        "/api/auth/client/callback",
        params={"code": "x", "state": "not-a-real-state"},
    )
    assert r.status_code == 400


# ── /api/auth/refresh preserves client role ───────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_preserves_client_role(http_client, hc_headers, hc_user):
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)
    state = await _start_and_get_state(http_client, invite_token)

    with patch("src.auth.router.exchange_code_for_userinfo", new=AsyncMock(return_value=_FAKE_GOOGLE_USER)):
        login_r = await http_client.get(
            "/api/auth/client/callback",
            params={"code": "fake-google-code", "state": state},
        )
    assert login_r.status_code == 200

    refresh_r = await http_client.post("/api/auth/refresh")
    assert refresh_r.status_code == 200

    claims = decode_access_token(refresh_r.json()["access_token"], public_key=get_settings().jwt_public_key)
    assert claims.role == "client"
    assert claims.hc_id == str(hc_user.id)
