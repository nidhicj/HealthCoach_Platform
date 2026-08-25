"""Integration tests: public Lead-facing payment endpoints (Unit_003 PHASE-05
Task 5).

  GET  /api/leads/:id/payment
  POST /api/leads/:id/payment/order
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import HcLeadgenConfig, HcPaymentAccount, Lead, User

pytestmark = pytest.mark.asyncio

# Patch the name as imported into the api module, not the definition in
# src.lib.razorpay_client — payments.py imports it at module level. Same
# convention as test_payment_accounts_hc.py's _PATCH_VERIFY.
_PATCH_CREATE_ORDER = "src.api.payments.create_order"

_CREDENTIALS = {
    "key_id": "rzp_test_key123",
    "key_secret": "rzp_test_secret456",
    "webhook_secret": "whsec_test_789",
}


async def _make_config(
    db: AsyncSession, hc_user: User, *, consultation_fee_inr: int | None = 1500,
    scheduling_link: str | None = "https://cal.example.com/asha",
) -> HcLeadgenConfig:
    cfg = HcLeadgenConfig(
        hc_user_id=hc_user.id,
        hc_slug=f"hc-{uuid.uuid4().hex[:8]}",
        questionnaire=[],
        test_panel={"standard_tests": ["CBC"], "condition_rules": []},
        consultation_fee_inr=consultation_fee_inr,
        scheduling_link=scheduling_link,
    )
    db.add(cfg)
    await db.flush()
    return cfg


async def _make_lead(
    db: AsyncSession, hc_user: User, *,
    status: str = "tests_recommended",
    payment_status: str = "unpaid",
    payment_reference: str | None = None,
) -> Lead:
    lead = Lead(
        hc_user_id=hc_user.id,
        full_name="Jane Doe",
        email=f"jane-{uuid.uuid4().hex[:8]}@example.com",
        status=status,
        payment_status=payment_status,
        payment_reference=payment_reference,
    )
    db.add(lead)
    await db.flush()
    return lead


async def _make_connected_account(
    db: AsyncSession, hc_user: User, *, connected: bool = True
) -> HcPaymentAccount:
    account = HcPaymentAccount(
        hc_user_id=hc_user.id,
        credentials=_CREDENTIALS if connected else None,
        connected_at=datetime.now(UTC) if connected else None,
    )
    db.add(account)
    await db.flush()
    return account


# ── GET /api/leads/:id/payment ──────────────────────────────────────────────


async def test_get_context_before_payment_hides_scheduling_link(
    http_client, hc_user: User, db: AsyncSession
):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.flush()
    await _make_config(db, hc_user, consultation_fee_inr=1500, scheduling_link="https://cal.example.com/asha")
    lead = await _make_lead(db, hc_user, payment_status="unpaid")

    resp = await http_client.get(f"/api/leads/{lead.id}/payment")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "hc_name": "Asha Rao",
        "consultation_fee_inr": 1500,
        "payment_status": "unpaid",
        "scheduling_link": None,
    }


async def test_get_context_after_payment_reveals_scheduling_link(
    http_client, hc_user: User, db: AsyncSession
):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.flush()
    await _make_config(db, hc_user, consultation_fee_inr=1500, scheduling_link="https://cal.example.com/asha")
    lead = await _make_lead(
        db, hc_user, status="consultation_scheduled", payment_status="paid",
        payment_reference="order_abc",
    )

    resp = await http_client.get(f"/api/leads/{lead.id}/payment")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["payment_status"] == "paid"
    assert body["scheduling_link"] == "https://cal.example.com/asha"


async def test_get_unknown_lead_returns_generic_404(http_client):
    resp = await http_client.get(f"/api/leads/{uuid.uuid4()}/payment")
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Not found"


async def test_get_requires_no_auth(http_client, hc_user: User, db: AsyncSession):
    """Sanity check this really is a public route — no Authorization header."""
    await _make_config(db, hc_user)
    lead = await _make_lead(db, hc_user)
    resp = await http_client.get(f"/api/leads/{lead.id}/payment")
    assert resp.status_code == 200, resp.text


# ── POST /api/leads/:id/payment/order ───────────────────────────────────────


async def test_order_creation_success_sends_exact_paise_conversion(
    http_client, hc_user: User, db: AsyncSession
):
    """The named test §5 requires: for a known rupee fee, assert the exact
    amount_paise sent to create_order() — not folded into a generic
    'order creation works' assertion."""
    await _make_config(db, hc_user, consultation_fee_inr=1500)
    await _make_connected_account(db, hc_user)
    lead = await _make_lead(db, hc_user)

    with patch(
        _PATCH_CREATE_ORDER, new=AsyncMock(return_value={"id": "order_xyz789"})
    ) as mock_create_order:
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 200, resp.text
    mock_create_order.assert_awaited_once_with(
        key_id="rzp_test_key123",
        key_secret="rzp_test_secret456",
        amount_paise=150000,  # 1500 INR * 100 — the load-bearing conversion
        notes={"hc_user_id": str(hc_user.id), "lead_id": str(lead.id)},
    )


async def test_order_creation_success_response_shape_and_db_writes(
    http_client, hc_user: User, db: AsyncSession
):
    await _make_config(db, hc_user, consultation_fee_inr=2000)
    await _make_connected_account(db, hc_user)
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_CREATE_ORDER, new=AsyncMock(return_value={"id": "order_new_1"})):
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"order_id": "order_new_1", "key_id": "rzp_test_key123", "amount_paise": 200000}
    # key_secret must never leave the backend.
    assert "key_secret" not in resp.text
    assert "webhook_secret" not in resp.text

    await db.refresh(lead)
    assert lead.payment_reference == "order_new_1"
    assert lead.status == "payment_pending"
    assert lead.payment_status == "unpaid"  # only the webhook (Task 6) sets "paid"


async def test_order_creation_failure_returns_structured_error_not_500(
    http_client, hc_user: User, db: AsyncSession
):
    await _make_config(db, hc_user, consultation_fee_inr=1500)
    await _make_connected_account(db, hc_user)
    lead = await _make_lead(db, hc_user)

    with patch(
        _PATCH_CREATE_ORDER, new=AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    ):
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 502, resp.text
    assert resp.json()["detail"]["error"] == "razorpay_unreachable"

    await db.refresh(lead)
    assert lead.payment_reference is None
    assert lead.status != "payment_pending"


async def test_order_creation_failure_http_status_error_returns_502(
    http_client, hc_user: User, db: AsyncSession
):
    """create_order() also propagates httpx.HTTPStatusError (a non-2xx from
    Razorpay's own API, via resp.raise_for_status()) — a second concrete
    shape of the same 'unreachable' failure family."""
    await _make_config(db, hc_user, consultation_fee_inr=1500)
    await _make_connected_account(db, hc_user)
    lead = await _make_lead(db, hc_user)

    request = httpx.Request("POST", "https://api.razorpay.com/v1/orders")
    response = httpx.Response(400, request=request)
    error = httpx.HTTPStatusError("boom", request=request, response=response)
    with patch(_PATCH_CREATE_ORDER, new=AsyncMock(side_effect=error)):
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 502, resp.text
    assert resp.json()["detail"]["error"] == "razorpay_unreachable"


async def test_order_no_connected_account_returns_structured_error(
    http_client, hc_user: User, db: AsyncSession
):
    await _make_config(db, hc_user, consultation_fee_inr=1500)
    # No HcPaymentAccount row at all.
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_CREATE_ORDER, new=AsyncMock()) as mock_create_order:
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "payment_not_available"
    mock_create_order.assert_not_awaited()


async def test_order_account_row_exists_but_not_connected_returns_structured_error(
    http_client, hc_user: User, db: AsyncSession
):
    """A row exists (e.g. created but never verified) with connected_at IS NULL —
    same structured error as no row at all, per the brief."""
    await _make_config(db, hc_user, consultation_fee_inr=1500)
    await _make_connected_account(db, hc_user, connected=False)
    lead = await _make_lead(db, hc_user)

    resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "payment_not_available"


async def test_order_fee_not_configured_returns_structured_error(
    http_client, hc_user: User, db: AsyncSession
):
    """consultation_fee_inr is nullable (leadgen.py) — an HC who connected
    Razorpay but hasn't set a fee yet must not 500 (None * 100)."""
    await _make_config(db, hc_user, consultation_fee_inr=None)
    await _make_connected_account(db, hc_user)
    lead = await _make_lead(db, hc_user)

    with patch(_PATCH_CREATE_ORDER, new=AsyncMock()) as mock_create_order:
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"] == "payment_not_available"
    mock_create_order.assert_not_awaited()


async def test_order_unknown_lead_returns_generic_404(http_client):
    resp = await http_client.post(f"/api/leads/{uuid.uuid4()}/payment/order")
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Not found"


async def test_order_reload_returns_existing_order_not_a_new_one(
    http_client, hc_user: User, db: AsyncSession
):
    """If leads.payment_reference is already set and payment_status is still
    'unpaid', return the existing order instead of creating a new Razorpay
    Order — avoids littering the HC's Razorpay dashboard with duplicate
    abandoned orders every time the Lead reloads the page."""
    await _make_config(db, hc_user, consultation_fee_inr=1500)
    await _make_connected_account(db, hc_user)
    lead = await _make_lead(
        db, hc_user, status="payment_pending", payment_status="unpaid",
        payment_reference="order_already_pending",
    )

    with patch(_PATCH_CREATE_ORDER, new=AsyncMock()) as mock_create_order:
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "order_id": "order_already_pending",
        "key_id": "rzp_test_key123",
        "amount_paise": 150000,
    }
    mock_create_order.assert_not_awaited()


async def test_order_failed_payment_retries_with_a_fresh_order(
    http_client, hc_user: User, db: AsyncSession
):
    """Unlike 'unpaid' + an existing payment_reference (idempotent reuse), a
    Lead whose last attempt ended in 'failed' gets a brand-new order on
    retry — per SPEC-0001's edge-cases table ('retrying is a fresh attempt,
    not a resume')."""
    await _make_config(db, hc_user, consultation_fee_inr=1500)
    await _make_connected_account(db, hc_user)
    lead = await _make_lead(
        db, hc_user, status="payment_failed", payment_status="failed",
        payment_reference="order_that_failed",
    )

    with patch(
        _PATCH_CREATE_ORDER, new=AsyncMock(return_value={"id": "order_retry_fresh"})
    ) as mock_create_order:
        resp = await http_client.post(f"/api/leads/{lead.id}/payment/order")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_id"] == "order_retry_fresh"
    mock_create_order.assert_awaited_once()

    await db.refresh(lead)
    assert lead.payment_reference == "order_retry_fresh"
