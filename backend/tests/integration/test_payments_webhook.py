"""Integration tests: POST /api/payments/webhook (Unit_003 PHASE-05 Task 6).

The highest-risk endpoint in this phase — the point where the platform
decides "this Lead really paid" and trusts it. These tests compute a REAL
HMAC-SHA256 signature against a fixture `webhook_secret` (never a mocked
`True`) over the exact raw bytes sent, matching
`razorpay_client.verify_webhook_signature`'s real implementation — this is
the one part of this phase that must not be simplified or short-circuited,
per the task brief, so it isn't simplified here either.
"""
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import HcPaymentAccount, Lead, LeadUploadToken, User

pytestmark = pytest.mark.asyncio

_WEBHOOK_SECRET = "whsec_test_789"
_CREDENTIALS = {
    "key_id": "rzp_test_key123",
    "key_secret": "rzp_test_secret456",
    "webhook_secret": _WEBHOOK_SECRET,
}


_NOTES_UNSET = object()  # sentinel distinct from a deliberate notes=None


def _razorpay_payload(
    *, order_id: str, hc_user_id: str, lead_id: str, event: str = "payment.captured",
    notes: dict[str, str] | None | object = _NOTES_UNSET,
) -> bytes:
    """Builds the raw JSON bytes of a Razorpay webhook body, shaped per
    Razorpay's real `payment.captured` webhook payload docs (confirmed
    during implementation — see task-6-report.md):
    `payload.payment.entity.{notes,order_id,id}`.

    `notes` defaults to the sentinel `_NOTES_UNSET` (not `None`) so callers
    can still deliberately pass `notes=None` to simulate a payload with no
    notes at all, distinct from the default (a real notes dict)."""
    if notes is _NOTES_UNSET:
        notes = {"hc_user_id": hc_user_id, "lead_id": lead_id}
    payload = {
        "entity": "event",
        "account_id": "acc_test_fixture",
        "event": event,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_fixture123",
                    "entity": "payment",
                    "amount": 150000,
                    "currency": "INR",
                    "status": "captured" if event == "payment.captured" else "failed",
                    "order_id": order_id,
                    "notes": notes,
                    "created_at": 1700000000,
                }
            }
        },
        "created_at": 1700000000,
    }
    return json.dumps(payload).encode()


def _sign(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


async def _make_hc_user(db: AsyncSession) -> User:
    user = User(
        email=f"hc-{uuid.uuid4().hex[:8]}@test.com",
        google_sub=f"g-{uuid.uuid4().hex}",
        role="hc",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_account(
    db: AsyncSession, hc_user: User, *, credentials: dict[str, str] | None = _CREDENTIALS
) -> HcPaymentAccount:
    account = HcPaymentAccount(
        hc_user_id=hc_user.id,
        credentials=credentials,
        connected_at=datetime.now(UTC) if credentials is not None else None,
    )
    db.add(account)
    await db.flush()
    return account


async def _make_lead(
    db: AsyncSession, hc_user: User, *,
    payment_status: str = "unpaid",
    payment_reference: str | None = "order_fixture_abc",
    paid_at: datetime | None = None,
) -> Lead:
    lead = Lead(
        hc_user_id=hc_user.id,
        full_name="Jane Doe",
        email=f"jane-{uuid.uuid4().hex[:8]}@example.com",
        status="payment_pending",
        payment_status=payment_status,
        payment_reference=payment_reference,
        paid_at=paid_at,
    )
    db.add(lead)
    await db.flush()
    return lead


async def _make_token(
    db: AsyncSession, lead: Lead, *,
    used_at: datetime | None = None, expires_at: datetime | None = None,
) -> LeadUploadToken:
    token = LeadUploadToken(
        lead_id=lead.id,
        token_hash=f"webhook-test-{uuid.uuid4().hex}",
        used_at=used_at,
        expires_at=expires_at,
    )
    db.add(token)
    await db.flush()
    return token


# ── success ──────────────────────────────────────────────────────────────────


async def test_webhook_success_flips_payment_status_and_activates_upload_token(
    http_client, db: AsyncSession
):
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    lead = await _make_lead(db, hc_user, payment_reference="order_success_1")
    token = await _make_token(db, lead)  # expires_at=None, used_at=None — Task 4's Send-time shape
    await db.commit()

    raw_body = _razorpay_payload(
        order_id="order_success_1", hc_user_id=str(hc_user.id), lead_id=str(lead.id)
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    before = datetime.now(UTC)
    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    after = datetime.now(UTC)

    assert resp.status_code == 200, resp.text

    await db.refresh(lead)
    assert lead.payment_status == "paid"
    assert lead.payment_reference == "order_success_1"
    assert lead.paid_at is not None
    assert before <= lead.paid_at <= after

    await db.refresh(token)
    assert token.expires_at is not None
    # ~14 days out — allow generous tolerance for wall-clock skew, not a
    # precise timing assertion.
    expected = before + timedelta(days=14)
    assert abs((token.expires_at - expected).total_seconds()) < 60
    assert token.used_at is None  # activation only sets expires_at, not used_at


# ── signature verification — the load-bearing part of this task ────────────


async def test_webhook_wrong_signature_rejected_no_state_change(
    http_client, db: AsyncSession
):
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    lead = await _make_lead(db, hc_user, payment_reference="order_badsig_1")
    token = await _make_token(db, lead)
    await db.commit()

    raw_body = _razorpay_payload(
        order_id="order_badsig_1", hc_user_id=str(hc_user.id), lead_id=str(lead.id)
    )
    # Signed with the WRONG secret — must not verify against the right one.
    bad_signature = _sign(raw_body, "totally-wrong-secret")

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": bad_signature, "Content-Type": "application/json"},
    )

    assert resp.status_code == 400, resp.text

    await db.refresh(lead)
    assert lead.payment_status == "unpaid"
    assert lead.paid_at is None

    await db.refresh(token)
    assert token.expires_at is None


async def test_webhook_missing_signature_header_rejected(http_client, db: AsyncSession):
    """No `X-Razorpay-Signature` header at all — must reject, not treat a
    missing header as an automatic mismatch that somehow still processes."""
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    lead = await _make_lead(db, hc_user, payment_reference="order_nosig_1")
    await db.commit()

    raw_body = _razorpay_payload(
        order_id="order_nosig_1", hc_user_id=str(hc_user.id), lead_id=str(lead.id)
    )
    resp = await http_client.post(
        "/api/payments/webhook", content=raw_body, headers={"Content-Type": "application/json"}
    )

    assert resp.status_code == 400, resp.text
    await db.refresh(lead)
    assert lead.payment_status == "unpaid"


async def test_webhook_unknown_hc_user_id_rejected_before_verification(
    http_client, db: AsyncSession
):
    """No HcPaymentAccount row at all for the claimed hc_user_id — reject
    400 immediately without attempting verification against any other
    account's secret (there's no "right" secret to even try here)."""
    unknown_hc_user_id = str(uuid.uuid4())
    raw_body = _razorpay_payload(
        order_id="order_doesnt_matter", hc_user_id=unknown_hc_user_id, lead_id=str(uuid.uuid4())
    )
    # Sign with SOME secret — irrelevant, since the account lookup fails first.
    signature = _sign(raw_body, "some-secret-nobody-owns")

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400, resp.text


async def test_webhook_account_row_exists_but_not_connected_rejected(
    http_client, db: AsyncSession
):
    """A row exists (e.g. created but never verified, connected_at IS NULL)
    — must be treated the same as no row at all."""
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user, credentials=None)  # connected_at stays None
    raw_body = _razorpay_payload(
        order_id="order_unconnected", hc_user_id=str(hc_user.id), lead_id=str(uuid.uuid4())
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400, resp.text


async def test_webhook_malformed_json_rejected(http_client, db: AsyncSession):
    resp = await http_client.post(
        "/api/payments/webhook",
        content=b"not json at all {{{",
        headers={"X-Razorpay-Signature": "irrelevant", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400, resp.text


async def test_webhook_missing_notes_rejected(http_client, db: AsyncSession):
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    raw_body = _razorpay_payload(
        order_id="order_no_notes", hc_user_id=str(hc_user.id), lead_id="irrelevant", notes=None
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)
    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400, resp.text


# ── idempotency ──────────────────────────────────────────────────────────────


async def test_webhook_duplicate_delivery_of_already_paid_is_noop(
    http_client, db: AsyncSession
):
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    original_paid_at = datetime.now(UTC) - timedelta(hours=1)
    lead = await _make_lead(
        db, hc_user, payment_status="paid", payment_reference="order_dup_1",
        paid_at=original_paid_at,
    )
    already_active_expiry = datetime.now(UTC) + timedelta(days=10)
    token = await _make_token(db, lead, expires_at=already_active_expiry)
    await db.commit()

    raw_body = _razorpay_payload(
        order_id="order_dup_1", hc_user_id=str(hc_user.id), lead_id=str(lead.id)
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )

    assert resp.status_code == 200, resp.text

    await db.refresh(lead)
    # Untouched — proves this really was a no-op, not a re-write with the
    # same values.
    assert lead.paid_at == original_paid_at

    await db.refresh(token)
    assert token.expires_at == already_active_expiry


async def test_webhook_no_matching_lead_returns_200_not_400(http_client, db: AsyncSession):
    """A verified (correctly-signed) webhook whose order_id matches no Lead
    — must not be retried forever by Razorpay (400 would cause retries);
    this platform can't resolve it by retrying, so it's a logged 200 no-op."""
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    raw_body = _razorpay_payload(
        order_id="order_never_created", hc_user_id=str(hc_user.id), lead_id=str(uuid.uuid4())
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text


async def test_webhook_cross_tenant_order_id_collision_not_matched(
    http_client, db: AsyncSession
):
    """A verified webhook for HC A's account, whose order_id happens to
    match a payment_reference belonging to a Lead owned by HC B — the
    hc_user_id cross-check must prevent HC A's webhook from marking HC B's
    Lead as paid."""
    hc_a = await _make_hc_user(db)
    hc_b = await _make_hc_user(db)
    await _make_account(db, hc_a)
    lead_b = await _make_lead(db, hc_b, payment_reference="order_shared_ref")
    await db.commit()

    raw_body = _razorpay_payload(
        order_id="order_shared_ref", hc_user_id=str(hc_a.id), lead_id=str(uuid.uuid4())
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text  # verified, but no matching Lead for HC A -> no-op

    await db.refresh(lead_b)
    assert lead_b.payment_status == "unpaid"  # HC B's Lead must be untouched


# ── event-type scoping ───────────────────────────────────────────────────────


async def test_webhook_ignores_non_captured_event_after_verification(
    http_client, db: AsyncSession
):
    """A genuinely-signed webhook for an event type other than
    payment.captured (e.g. the HC's Razorpay dashboard has more than one
    event enabled for this URL) must be a 200 no-op — not treated as
    suspicious, and must not mark the Lead as paid."""
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    lead = await _make_lead(db, hc_user, payment_reference="order_failed_evt")
    await db.commit()

    raw_body = _razorpay_payload(
        order_id="order_failed_evt", hc_user_id=str(hc_user.id), lead_id=str(lead.id),
        event="payment.failed",
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(lead)
    assert lead.payment_status == "unpaid"
    assert lead.paid_at is None


# ── anomaly: zero/multiple unused tokens must not crash the response ────────


async def test_webhook_success_with_no_unused_token_logs_but_still_returns_200(
    http_client, db: AsyncSession
):
    """Data anomaly Task 4's invalidation should prevent (zero unused
    tokens for the Lead at payment time) — the payment itself must still
    succeed; this handler must not crash or fail the webhook response."""
    hc_user = await _make_hc_user(db)
    await _make_account(db, hc_user)
    lead = await _make_lead(db, hc_user, payment_reference="order_no_token")
    # No LeadUploadToken row at all for this Lead.
    await db.commit()

    raw_body = _razorpay_payload(
        order_id="order_no_token", hc_user_id=str(hc_user.id), lead_id=str(lead.id)
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text

    await db.refresh(lead)
    assert lead.payment_status == "paid"  # the payment itself still succeeded
