"""Unit tests for razorpay_client.py — Razorpay Orders API + webhook signature helpers.

HTTP calls are mocked via httpx.MockTransport (no real network, no respx dependency),
mirroring tests/unit/test_calendar_oauth.py and the make_http_client() factory used by
src/lib/http.py.
"""
import json

import httpx
import pytest

from src.lib.razorpay_client import create_order, verify_credentials, verify_webhook_signature

_KEY_ID = "rzp_test_key123"
_KEY_SECRET = "rzp_test_secret456"


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(
        "src.lib.razorpay_client.make_http_client",
        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


# ── create_order ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_order_sends_exact_body_shape_and_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["auth_header"] = request.headers.get("authorization")
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "order_ABC123", "amount": 50000, "currency": "INR"})

    _patch_client(monkeypatch, handler)

    result = await create_order(
        key_id=_KEY_ID,
        key_secret=_KEY_SECRET,
        amount_paise=50000,
        notes={"lead_id": "lead-1"},
    )

    assert captured["url"] == "https://api.razorpay.com/v1/orders"
    assert captured["method"] == "POST"
    assert captured["auth_header"] is not None and captured["auth_header"].startswith("Basic ")
    assert json.loads(captured["body"]) == {
        "amount": 50000,
        "currency": "INR",
        "notes": {"lead_id": "lead-1"},
    }
    assert result == {"id": "order_ABC123", "amount": 50000, "currency": "INR"}


@pytest.mark.asyncio
async def test_create_order_raises_on_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"description": "amount must be at least 100"}})

    _patch_client(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await create_order(key_id=_KEY_ID, key_secret=_KEY_SECRET, amount_paise=1, notes={})


# ── verify_credentials ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_credentials_true_on_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://api.razorpay.com/v1/orders")
        assert request.url.params.get("count") == "1"
        return httpx.Response(200, json={"entity": "collection", "count": 0, "items": []})

    _patch_client(monkeypatch, handler)

    assert await verify_credentials(key_id=_KEY_ID, key_secret=_KEY_SECRET) is True


@pytest.mark.asyncio
async def test_verify_credentials_false_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"description": "Authentication failed"}})

    _patch_client(monkeypatch, handler)

    assert await verify_credentials(key_id=_KEY_ID, key_secret="wrong-secret") is False


@pytest.mark.asyncio
async def test_verify_credentials_false_on_403(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"description": "Forbidden"}})

    _patch_client(monkeypatch, handler)

    assert await verify_credentials(key_id=_KEY_ID, key_secret=_KEY_SECRET) is False


@pytest.mark.asyncio
async def test_verify_credentials_propagates_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"description": "Internal server error"}})

    _patch_client(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await verify_credentials(key_id=_KEY_ID, key_secret=_KEY_SECRET)


@pytest.mark.asyncio
async def test_verify_credentials_propagates_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_client(monkeypatch, handler)

    with pytest.raises(httpx.ConnectError):
        await verify_credentials(key_id=_KEY_ID, key_secret=_KEY_SECRET)


# ── verify_webhook_signature ─────────────────────────────────────────────────
# Fixture signature hand-computed via:
#   hmac.new(b"whsec_test_123", raw_body, hashlib.sha256).hexdigest()

_WEBHOOK_SECRET = "whsec_test_123"
_RAW_BODY = b'{"event":"payment.captured","payload":{}}'
_VALID_SIGNATURE = "012934fb264b3bb3ebe89487101910afe32ffec2149d859b44675994f4da0c54"


def test_verify_webhook_signature_correct_signature() -> None:
    assert verify_webhook_signature(
        raw_body=_RAW_BODY, signature=_VALID_SIGNATURE, webhook_secret=_WEBHOOK_SECRET
    ) is True


def test_verify_webhook_signature_wrong_signature() -> None:
    tampered = "0" * len(_VALID_SIGNATURE)
    assert verify_webhook_signature(
        raw_body=_RAW_BODY, signature=tampered, webhook_secret=_WEBHOOK_SECRET
    ) is False


def test_verify_webhook_signature_wrong_secret() -> None:
    assert verify_webhook_signature(
        raw_body=_RAW_BODY, signature=_VALID_SIGNATURE, webhook_secret="a-different-secret"
    ) is False


def test_verify_webhook_signature_tampered_body() -> None:
    assert verify_webhook_signature(
        raw_body=b'{"event":"payment.captured","payload":{"tampered":true}}',
        signature=_VALID_SIGNATURE,
        webhook_secret=_WEBHOOK_SECRET,
    ) is False
