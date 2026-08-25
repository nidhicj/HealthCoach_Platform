"""Integration tests: whole-flow payment + scheduling handoff (Unit_003
PHASE-05 Task 8).

Genuine end-to-end proof that Tasks 1-7 compose correctly as ONE flow, not
just that each passes its own isolated tests: a single Lead's journey from
public questionnaire submission (`POST /api/intake/:slug`) through the HC's
Send action (`POST /api/leads/:id/test-recommendation/send` — mints the
`LeadUploadToken`, PHASE-05 Task 4) into the public payment endpoints
(`GET`/`POST /api/leads/:id/payment*`, Task 5), a REAL locally-computed HMAC
webhook signature against a fixture `webhook_secret` (Task 6's
`POST /api/payments/webhook` — mirrors `test_payments_webhook.py`'s
established pattern of computing a genuine HMAC, never a mocked `True`), and
finally the upload-token gate (`GET /api/upload/:token`, Task 3/6) flipping
from `"payment_pending"` to `"valid"` once — and only once — that webhook is
correctly verified and processed.

Scope note (task-8-brief.md): no real Razorpay test-mode credentials exist
in this environment (confirmed: nothing under `RAZORPAY_*` in `.env`).
`razorpay_client.create_order` is mocked here, exactly like
`test_leads_payment_public.py`'s own tests — this file proves the platform's
OWN code composes correctly end to end, not that Razorpay's live API
behaves as documented. The brief's separate "real Razorpay test-mode round
trip" manual-verification requirement (a real Order, real hosted Checkout,
a real webhook delivered from Razorpay's own servers via a tunnel) is
explicitly OUT OF SCOPE for this file and was NOT attempted — see
task-8-report.md.
"""
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import HcPaymentAccount, Lead, LeadUploadToken, User

pytestmark = pytest.mark.asyncio

# Same mocking convention as test_intake_public.py / test_leads_hc.py / the
# rest of this codebase's tests: real API keys are present in local `.env`
# (OPENROUTER_API_KEY, RESEND_API_KEY) — an unmocked call would be a real,
# slow, non-deterministic network request, not a test double.
_PATCH_GENERATE = "src.llm_service.generate_lead_test_recommendation"
_PATCH_REVIEW_EMAIL = "src.api.intake.send_test_recommendation_review_email"
_PATCH_SEND_EMAIL = "src.api.leads.send_finalized_test_recommendation_email"
_PATCH_CREATE_ORDER = "src.api.payments.create_order"

_WEBHOOK_SECRET = "whsec_wholeflow_fixture_secret"
_CREDENTIALS = {
    "key_id": "rzp_test_wholeflow_key123",
    "key_secret": "rzp_test_wholeflow_secret456",
    "webhook_secret": _WEBHOOK_SECRET,
}
_CONSULTATION_FEE_INR = 1500
_EXPECTED_AMOUNT_PAISE = 150000  # 1500 * 100 — the named conversion this task must pin


# ── setup helpers ────────────────────────────────────────────────────────────


async def _init_leadgen_config(http_client: AsyncClient, hc_user: User, hc_headers, db) -> dict:
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _configure_with_test_panel_and_payment(
    http_client: AsyncClient, hc_user: User, hc_headers, db
) -> dict:
    """Base leadgen config (default 6 fixed questions), plus a standard test
    panel and the payment/scheduling fields this flow needs — mirrors
    test_intake_public.py::_configure_with_test_panel, extended with the
    PHASE-05 fields (`consultation_fee_inr`, `scheduling_link`)."""
    await _init_leadgen_config(http_client, hc_user, hc_headers, db)
    resp = await http_client.patch(
        "/api/leadgen/config",
        headers=hc_headers,
        json={
            "test_panel": {"standard_tests": ["CBC", "HbA1c", "TSH"]},
            "consultation_fee_inr": _CONSULTATION_FEE_INR,
            "scheduling_link": "https://cal.example.com/asha-rao",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _connect_payment_account(db: AsyncSession, hc_user: User) -> HcPaymentAccount:
    account = HcPaymentAccount(
        hc_user_id=hc_user.id, credentials=_CREDENTIALS, connected_at=datetime.now(UTC)
    )
    db.add(account)
    await db.flush()
    return account


def _valid_payload(**overrides) -> dict:
    """Matches leadgen.py's default 6 fixed questionnaire keys exactly (no
    custom questions configured for this flow — not needed to exercise the
    payment/webhook composition this file is testing)."""
    payload = {
        "consent_ack": True,
        "full_name": "Priya Sharma",
        "age": "29",
        "email": f"priya-{uuid.uuid4().hex[:8]}@example.com",
        "phone": "9876500000",
        "primary_health_goal": "Weight loss",
        "current_health_concerns": "None",
    }
    payload.update(overrides)
    return payload


def _sign(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def _webhook_payload(*, order_id: str, hc_user_id: str, lead_id: str) -> bytes:
    """Shaped per Razorpay's real payment.captured webhook payload docs, same
    as test_payments_webhook.py's fixture builder."""
    payload = {
        "entity": "event",
        "account_id": "acc_wholeflow_fixture",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_wholeflow_fixture123",
                    "entity": "payment",
                    "amount": _EXPECTED_AMOUNT_PAISE,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": order_id,
                    "notes": {"hc_user_id": hc_user_id, "lead_id": lead_id},
                    "created_at": 1700000000,
                }
            }
        },
        "created_at": 1700000000,
    }
    return json.dumps(payload).encode()


async def _drive_flow_to_order_created(
    http_client: AsyncClient, hc_user: User, hc_headers: dict, db: AsyncSession
) -> dict:
    """Runs the flow from questionnaire submission through order creation —
    the shared prefix for both whole-flow tests below (success path and
    forged-signature path both need an identical, real order in place before
    they diverge at the webhook step).

    Returns {lead_id, raw_upload_token, order_id, hc_name}.
    """
    await _configure_with_test_panel_and_payment(http_client, hc_user, hc_headers, db)
    await _connect_payment_account(db, hc_user)

    # ── Stage 2: public questionnaire submission (AI drafting mocked). ──────
    ai_additions = [
        {"test": "Vitamin D", "rationale": "Common deficiency, worth a baseline check."},
    ]
    hc_slug = await _slug_for(db, hc_user)
    with patch(_PATCH_GENERATE, new_callable=AsyncMock, return_value=ai_additions), \
         patch(_PATCH_REVIEW_EMAIL):
        submit_resp = await http_client.post(
            f"/api/intake/{hc_slug}", json=_valid_payload()
        )
    assert submit_resp.status_code == 201, submit_resp.text
    lead_id = uuid.UUID(submit_resp.json()["lead_id"])

    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.status == "tests_drafted"

    # ── Stage 3: HC finalizes and Sends — mints the upload token (Task 4). ──
    with patch(_PATCH_SEND_EMAIL) as mock_send_email:
        send_resp = await http_client.post(
            f"/api/leads/{lead_id}/test-recommendation/send",
            headers=hc_headers,
            json={"additions": []},
        )
    assert send_resp.status_code == 201, send_resp.text
    assert send_resp.json()["status"] == "tests_recommended"

    mock_send_email.assert_called_once_with(
        to=ANY, lead_name=ANY, hc_name="Asha Rao", test_list=ANY,
        pay_link=ANY, upload_link=ANY,
    )
    call_kwargs = mock_send_email.call_args.kwargs
    settings = get_settings()

    # Links must be exactly what SPEC-0001/D-8 promises — not just "truthy".
    assert call_kwargs["pay_link"] == f"{settings.frontend_url}/pay/{lead_id}"
    upload_link = call_kwargs["upload_link"]
    assert upload_link.startswith(f"{settings.frontend_url}/upload/")
    raw_upload_token = upload_link.rsplit("/", 1)[-1]

    upload_token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead_id)
    )).scalar_one()
    # The raw token embedded in the email must hash to the exact row Send
    # minted for this Lead — and that row must still be in Task 4's
    # documented pre-payment shape (mintable, not yet usable).
    assert upload_token_row.token_hash == hashlib.sha256(raw_upload_token.encode()).hexdigest()
    assert upload_token_row.expires_at is None
    assert upload_token_row.used_at is None

    # ── Stage 4 step 0: Lead opens the payment page (GET context). ──────────
    context_resp = await http_client.get(f"/api/leads/{lead_id}/payment")
    assert context_resp.status_code == 200, context_resp.text
    context_body = context_resp.json()
    assert context_body["payment_status"] == "unpaid"
    assert context_body["consultation_fee_inr"] == _CONSULTATION_FEE_INR
    assert context_body["scheduling_link"] is None  # withheld pre-payment

    # ── Before paying: the upload link must gate, not 500 or silently work. ─
    pending_resp = await http_client.get(f"/api/upload/{raw_upload_token}")
    assert pending_resp.status_code == 200, pending_resp.text
    assert pending_resp.json()["state"] == "payment_pending"

    # ── Stage 4 step 1: order creation (Razorpay call mocked). ──────────────
    order_id = f"order_wholeflow_{uuid.uuid4().hex[:10]}"
    with patch(
        _PATCH_CREATE_ORDER, new=AsyncMock(return_value={"id": order_id})
    ) as mock_create_order:
        order_resp = await http_client.post(f"/api/leads/{lead_id}/payment/order")
    assert order_resp.status_code == 200, order_resp.text
    order_body = order_resp.json()
    assert order_body["order_id"] == order_id

    # THE named assertion task-8-brief.md §5 requires as its own dedicated
    # check, not folded into a generic "order creation works" assertion.
    assert order_body["amount_paise"] == _EXPECTED_AMOUNT_PAISE
    mock_create_order.assert_awaited_once_with(
        key_id=_CREDENTIALS["key_id"],
        key_secret=_CREDENTIALS["key_secret"],
        amount_paise=_EXPECTED_AMOUNT_PAISE,
        notes={"hc_user_id": str(hc_user.id), "lead_id": str(lead_id)},
    )

    await db.refresh(lead)
    assert lead.payment_reference == order_id
    assert lead.payment_status == "unpaid"  # only the webhook sets "paid"

    return {
        "lead_id": lead_id,
        "raw_upload_token": raw_upload_token,
        "order_id": order_id,
    }


async def _slug_for(db: AsyncSession, hc_user: User) -> str:
    from src.db.models import HcLeadgenConfig
    cfg = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == hc_user.id)
    )).scalar_one()
    return cfg.hc_slug


# ── whole-flow tests ─────────────────────────────────────────────────────────


async def test_whole_flow_questionnaire_to_paid_and_upload_unlocked(
    http_client: AsyncClient, hc_user: User, hc_headers: dict, db: AsyncSession
):
    """The success path, start to finish: submit -> Send -> payment context
    -> order -> a REAL locally-computed HMAC webhook -> payment_status flips
    to 'paid' -> the SAME upload link (previously gated) now resolves
    'valid'."""
    state = await _drive_flow_to_order_created(http_client, hc_user, hc_headers, db)
    lead_id = state["lead_id"]

    # ── Stage 4 step 2 (Razorpay's side): a real, correctly-signed webhook. ─
    raw_body = _webhook_payload(
        order_id=state["order_id"], hc_user_id=str(hc_user.id), lead_id=str(lead_id)
    )
    signature = _sign(raw_body, _WEBHOOK_SECRET)

    before = datetime.now(UTC)
    webhook_resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    after = datetime.now(UTC)
    assert webhook_resp.status_code == 200, webhook_resp.text

    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.payment_status == "paid"
    assert lead.paid_at is not None
    assert before <= lead.paid_at <= after

    upload_token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead_id)
    )).scalar_one()
    assert upload_token_row.expires_at is not None
    expected_expiry = before + timedelta(days=14)
    assert abs((upload_token_row.expires_at - expected_expiry).total_seconds()) < 60
    assert upload_token_row.used_at is None  # activation only sets expires_at

    # ── The whole point: the SAME link that was gated before now works. ─────
    valid_resp = await http_client.get(f"/api/upload/{state['raw_upload_token']}")
    assert valid_resp.status_code == 200, valid_resp.text
    valid_body = valid_resp.json()
    assert valid_body["state"] == "valid"
    assert valid_body["hc_name"] == "Asha Rao"

    # Bonus full-loop confirmation of Task 5's GET context (not explicitly
    # named by the brief's checklist, but proves the scheduling handoff too):
    # the scheduling link is now revealed post-payment.
    context_resp = await http_client.get(f"/api/leads/{lead_id}/payment")
    assert context_resp.status_code == 200, context_resp.text
    context_body = context_resp.json()
    assert context_body["payment_status"] == "paid"
    assert context_body["scheduling_link"] == "https://cal.example.com/asha-rao"


async def test_whole_flow_forged_webhook_signature_cannot_advance_real_lead(
    http_client: AsyncClient, hc_user: User, hc_headers: dict, db: AsyncSession
):
    """Dedicated wrong-signature-rejected test in this SAME whole-flow
    context (task-8-brief.md §5) — not just Task 6's isolated unit test.
    Confirms a forged webhook cannot advance a real Lead's state end to end:
    the Lead stays unpaid and the upload link stays gated at
    'payment_pending', never flipping to 'valid'."""
    state = await _drive_flow_to_order_created(http_client, hc_user, hc_headers, db)
    lead_id = state["lead_id"]

    raw_body = _webhook_payload(
        order_id=state["order_id"], hc_user_id=str(hc_user.id), lead_id=str(lead_id)
    )
    # Signed with the WRONG secret — a forged/tampered delivery, not
    # Razorpay's genuine one.
    forged_signature = _sign(raw_body, "an-attacker-does-not-know-the-real-secret")

    webhook_resp = await http_client.post(
        "/api/payments/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": forged_signature, "Content-Type": "application/json"},
    )
    assert webhook_resp.status_code == 400, webhook_resp.text

    lead = await db.get(Lead, lead_id)
    assert lead is not None
    assert lead.payment_status == "unpaid"
    assert lead.paid_at is None

    upload_token_row = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.lead_id == lead_id)
    )).scalar_one()
    assert upload_token_row.expires_at is None
    assert upload_token_row.used_at is None

    # The real end-to-end proof: the SAME link a genuine webhook would have
    # unlocked is still gated, not "valid", after the forged delivery.
    still_pending_resp = await http_client.get(f"/api/upload/{state['raw_upload_token']}")
    assert still_pending_resp.status_code == 200, still_pending_resp.text
    assert still_pending_resp.json()["state"] == "payment_pending"

    # And the payment page still withholds the scheduling link.
    context_resp = await http_client.get(f"/api/leads/{lead_id}/payment")
    assert context_resp.status_code == 200, context_resp.text
    assert context_resp.json()["scheduling_link"] is None
