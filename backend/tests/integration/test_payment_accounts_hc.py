"""Integration tests for HC-facing Razorpay payment-account endpoints.
Unit_003 PHASE-05 Task 2:
  GET  /api/hc/payment-account
  POST /api/hc/payment-account/connect
"""
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select

from src.db.models import HcPaymentAccount
from tests.integration.conftest import auth_headers

pytestmark = pytest.mark.asyncio

# Patch the name as imported into the api module, not the definition in
# src.lib.razorpay_client — payment_accounts.py imports it at module level.
# Same convention as test_leads_hc.py's _PATCH_SEND_EMAIL.
_PATCH_VERIFY = "src.api.payment_accounts.verify_credentials"

_CONNECT_BODY = {
    "key_id": "rzp_test_key123",
    "key_secret": "rzp_test_secret456",
    "webhook_secret": "whsec_test_789",
}


async def _get_account(db, hc_user_id: uuid.UUID) -> HcPaymentAccount | None:
    return (await db.execute(
        select(HcPaymentAccount).where(HcPaymentAccount.hc_user_id == hc_user_id)
    )).scalar_one_or_none()


# ── GET /api/hc/payment-account ─────────────────────────────────────────────


async def test_get_before_connect_returns_false(http_client, hc_headers):
    r = await http_client.get("/api/hc/payment-account", headers=hc_headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"connected": False}


async def test_get_after_connect_returns_true(http_client, hc_headers):
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=True)):
        connect_r = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert connect_r.status_code == 200, connect_r.text

    r = await http_client.get("/api/hc/payment-account", headers=hc_headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"connected": True}


async def test_get_never_returns_credentials_field(http_client, hc_headers):
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=True)):
        await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    r = await http_client.get("/api/hc/payment-account", headers=hc_headers)
    assert set(r.json().keys()) == {"connected"}


async def test_get_cross_tenant_isolation(http_client, hc_headers, hc2_headers):
    """An HC never sees another HC's connected status — trivially true since the
    lookup is always current_tenant()-scoped, but written per the task brief."""
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=True)):
        connect_r = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert connect_r.status_code == 200, connect_r.text

    hc1_status = await http_client.get("/api/hc/payment-account", headers=hc_headers)
    hc2_status = await http_client.get("/api/hc/payment-account", headers=hc2_headers)
    assert hc1_status.json() == {"connected": True}
    assert hc2_status.json() == {"connected": False}


async def test_get_requires_auth(http_client):
    r = await http_client.get("/api/hc/payment-account")
    assert r.status_code == 401


async def test_get_requires_hc_role(http_client, hc_user):
    client_headers = auth_headers(hc_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.get("/api/hc/payment-account", headers=client_headers)
    assert r.status_code == 403


# ── POST /api/hc/payment-account/connect ────────────────────────────────────


async def test_connect_success_creates_row_and_sets_connected_at(
    http_client, hc_headers, hc_user, db
):
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=True)) as mock_verify:
        r = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert r.status_code == 200, r.text
    assert r.json() == {"connected": True}
    mock_verify.assert_awaited_once_with(key_id="rzp_test_key123", key_secret="rzp_test_secret456")

    account = await _get_account(db, hc_user.id)
    assert account is not None
    assert account.connected_at is not None
    assert account.credentials == _CONNECT_BODY


async def test_connect_response_never_includes_credentials(http_client, hc_headers):
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=True)):
        r = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert r.status_code == 200, r.text
    assert set(r.json().keys()) == {"connected"}
    assert "key_secret" not in r.text
    assert "webhook_secret" not in r.text


async def test_connect_bad_credentials_returns_structured_422_no_row_created(
    http_client, hc_headers, hc_user, db
):
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=False)):
        r = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == "invalid_credentials"
    assert "key_secret" not in r.text

    account = await _get_account(db, hc_user.id)
    assert account is None


async def test_connect_razorpay_unreachable_returns_distinct_structured_error_not_500(
    http_client, hc_headers, hc_user, db
):
    with patch(
        _PATCH_VERIFY, new=AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    ):
        r = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert r.status_code == 502, r.text
    assert r.json()["detail"]["error"] == "razorpay_unreachable"
    assert r.json()["detail"]["error"] != "invalid_credentials"

    account = await _get_account(db, hc_user.id)
    assert account is None


async def test_connect_razorpay_5xx_propagated_as_http_status_error_returns_502(
    http_client, hc_headers
):
    """verify_credentials() also propagates httpx.HTTPStatusError (a 5xx from
    Razorpay's own API, via resp.raise_for_status()) — a second concrete shape
    of the same 'unreachable' failure family, distinct from a ConnectError."""
    request = httpx.Request("GET", "https://api.razorpay.com/v1/orders")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("boom", request=request, response=response)
    with patch(_PATCH_VERIFY, new=AsyncMock(side_effect=error)):
        r = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert r.status_code == 502, r.text
    assert r.json()["detail"]["error"] == "razorpay_unreachable"


async def test_reconnect_overwrites_credentials_and_bumps_updated_at(
    http_client, hc_headers, hc_user, db
):
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=True)):
        first = await http_client.post(
            "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=hc_headers
        )
    assert first.status_code == 200, first.text
    account = await _get_account(db, hc_user.id)
    first_updated_at = account.updated_at
    first_row_id = account.id

    new_body = {
        "key_id": "rzp_test_key_NEW",
        "key_secret": "rzp_test_secret_NEW",
        "webhook_secret": "whsec_test_NEW",
    }
    with patch(_PATCH_VERIFY, new=AsyncMock(return_value=True)):
        second = await http_client.post(
            "/api/hc/payment-account/connect", json=new_body, headers=hc_headers
        )
    assert second.status_code == 200, second.text

    account = await _get_account(db, hc_user.id)
    assert account.id == first_row_id  # same row, not a duplicate
    assert account.credentials == new_body
    assert account.updated_at >= first_updated_at


async def test_connect_rejects_blank_field(http_client, hc_headers):
    body = {**_CONNECT_BODY, "key_secret": "   "}
    r = await http_client.post("/api/hc/payment-account/connect", json=body, headers=hc_headers)
    assert r.status_code == 422, r.text


async def test_connect_rejects_missing_field(http_client, hc_headers):
    body = {"key_id": "rzp_test_key123", "key_secret": "rzp_test_secret456"}
    r = await http_client.post("/api/hc/payment-account/connect", json=body, headers=hc_headers)
    assert r.status_code == 422, r.text


async def test_connect_requires_auth(http_client):
    r = await http_client.post("/api/hc/payment-account/connect", json=_CONNECT_BODY)
    assert r.status_code == 401


async def test_connect_requires_hc_role(http_client, hc_user):
    client_headers = auth_headers(hc_user.id, "client", hc_id=str(hc_user.id))
    r = await http_client.post(
        "/api/hc/payment-account/connect", json=_CONNECT_BODY, headers=client_headers
    )
    assert r.status_code == 403
