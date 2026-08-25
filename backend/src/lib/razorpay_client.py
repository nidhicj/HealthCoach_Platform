"""Razorpay HTTP wrapper. All outbound Razorpay API calls go through here.

PHASE-05 (payment + scheduling handoff), Task 1. No `PaymentProvider` abstraction —
per this phase's plan, Razorpay is the only provider in scope and an interface with
one implementation is premature. Three standalone functions, mirroring the DIY-httpx
style of src/llm_service/client.py and src/lib/s3.py (no SDK dependency).

Each HC connects their own Razorpay account (their own key_id/key_secret/webhook_secret,
stored per-row in hc_payment_accounts.credentials) — this module is deliberately stateless
and takes credentials as arguments rather than reading them from settings/DB itself, so
callers (Task 2's connect endpoint, Task 5's Lead-facing payment endpoint, the webhook
receiver) control exactly whose credentials are used for a given call.
"""
from __future__ import annotations

import hashlib
import hmac

from src.lib.http import (
    make_http_client,  # patched in tests via src.lib.razorpay_client.make_http_client
)

_ORDERS_URL = "https://api.razorpay.com/v1/orders"


async def create_order(
    *,
    key_id: str,
    key_secret: str,
    amount_paise: int,
    notes: dict[str, str],
) -> dict:
    """Create a Razorpay Order. Amount is in paise (smallest currency unit), currency is fixed to INR.

    Raises httpx.HTTPStatusError on a non-2xx response — the caller (Task 5's Lead-facing
    payment endpoint) decides how to translate that into a Lead-facing error.

    Returns the parsed response dict (contains `id`, the order ID, among other fields).
    """
    payload = {"amount": amount_paise, "currency": "INR", "notes": notes}
    async with make_http_client() as client:
        resp = await client.post(_ORDERS_URL, json=payload, auth=(key_id, key_secret))
        resp.raise_for_status()
    return resp.json()


async def verify_credentials(*, key_id: str, key_secret: str) -> bool:
    """Confirm a Razorpay key_id/key_secret pair is valid via one cheap authenticated read.

    Calls `GET /v1/orders?count=1` — the same Orders endpoint create_order() writes to
    (so no separate permission scope to worry about), scoped to the smallest page size
    Razorpay allows, purely to exercise Basic Auth without pulling real data.

    - 401/403 (bad key_id/key_secret, or a valid pair lacking Orders read access) -> False.
    - Any other error status (5xx, network failure, etc.) propagates as an exception —
      callers must be able to distinguish "your key is wrong" from "Razorpay is
      unreachable right now" (see Task 2's connect endpoint).
    - Any 2xx -> True.
    """
    async with make_http_client() as client:
        # Network errors / timeouts (httpx.HTTPError subclasses) propagate unmodified —
        # that's the "Razorpay is unreachable" case callers must distinguish from a bad key.
        resp = await client.get(_ORDERS_URL, params={"count": 1}, auth=(key_id, key_secret))
    if resp.status_code in (401, 403):
        return False
    resp.raise_for_status()
    return True


def verify_webhook_signature(*, raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    """Verify a Razorpay webhook's `X-Razorpay-Signature` header.

    Pure function, no I/O: HMAC-SHA256 hex digest over the raw request body, keyed with
    the account owner's webhook_secret (distinct from key_id/key_secret — configured
    separately in the HC's own Razorpay dashboard), compared via hmac.compare_digest
    to resist timing attacks.

    Callers must pass the exact raw bytes of the request body (pre-JSON-parsing) —
    re-serializing a parsed payload is not guaranteed to reproduce Razorpay's signed bytes.
    """
    expected = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
