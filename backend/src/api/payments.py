"""Public Lead-facing payment endpoints. Unit_003 PHASE-05 (payment + scheduling
handoff), Task 5.

  GET  /api/leads/:id/payment        -> payment context for the Lead's book & pay page
  POST /api/leads/:id/payment/order  -> create (or return the already-pending) Razorpay Order

No auth, no tenant scoping — resolved by the Lead's raw `id` (a UUID, itself
high-entropy and unguessable), unlike `src/api/upload.py`'s hashed,
independently-rotatable `LeadUploadToken`. The two links have different
security requirements: the upload token must be single-use and revocable
(consuming/invalidating it is part of that flow's own state machine), while
this payment link's safety against replay comes from a different mechanism —
`payment_status` itself gates what's revealed (GET never mutates and only
returns `scheduling_link` once `payment_status == "paid"`; POST is idempotent
while `unpaid`, see `create_payment_order`'s docstring) — so reusing the
Lead's permanent identifier as the link's bearer credential is a deliberate
simplification for this endpoint, not an oversight of the hashed-token
pattern used elsewhere.

`leads.py`'s router (`src/api/leads.py`) is HC-authenticated throughout
(`HcClaimsDep`/`TenantDep`) — these routes are deliberately public (a Lead
with no platform account must be able to reach them straight from the "book &
pay" button in Stage 3's email), so they live in their own file with their
own un-auth'd router, making that boundary visible in the code rather than
only in a comment on a shared one. `POST /api/payments/webhook` (Task 6)
belongs in this same file, as a second router (`prefix="/api/payments"`) —
not added yet.

Security note: like `intake.py`/`upload.py`, responses here are a strict
allowlist — response models are built field-by-field, never
`.model_validate()`d off a full ORM object. `key_secret` (and the whole
`credentials` dict) never appears in a response body or a log line.
"""
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import DbDep
from src.db.models import HcLeadgenConfig, HcPaymentAccount, Lead, User
from src.lib.razorpay_client import create_order
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/leads", tags=["payments"])


# ── schemas ────────────────────────────────────────────────────────────────────


class LeadPaymentContextOut(BaseModel):
    hc_name: str
    consultation_fee_inr: int | None
    payment_status: str
    # Present ONLY once payment_status == "paid" — withheld until then so an
    # unpaid Lead (or anyone else who has this URL) can't read the HC's
    # scheduling destination before paying (SPEC-0001 Stage 4).
    scheduling_link: str | None = None


class CreatePaymentOrderOut(BaseModel):
    order_id: str
    key_id: str
    amount_paise: int


# ── errors ─────────────────────────────────────────────────────────────────────


def _lead_not_found_error() -> HTTPException:
    # Generic 404, no detail leaked — mirrors intake.py's get_intake_config
    # convention for this codebase's other public, unauthenticated endpoints
    # (a plain string body, not the structured {error, message} shape used
    # below for business-state errors).
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _payment_not_available_error() -> HTTPException:
    # SPEC-0001 edge-cases table, row "HC has not connected a Razorpay account
    # and a Lead reaches Stage 4": POST .../payment/order must return a
    # structured "consultation payment not yet available" response, not a
    # 500. Also used (see create_payment_order below) when the HC's
    # `consultation_fee_inr` isn't configured yet — a related "Stage 1 setup
    # incomplete" condition the spec's table doesn't enumerate as its own
    # row, but which fails for the identical reason from the Lead's point of
    # view: the HC hasn't finished payment setup.
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "payment_not_available",
            "message": (
                "Consultation payment isn't available yet — please contact "
                "your health coach directly."
            ),
        },
    )


def _razorpay_unreachable_error() -> HTTPException:
    # Mirrors payment_accounts.py's _razorpay_unreachable_error: same 502
    # framing (the upstream we depend on failed, not our own endpoint being
    # overloaded/unavailable), kept as a distinct helper so this file's
    # structured body stays scoped to its own schema, same convention as
    # that file.
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "error": "razorpay_unreachable",
            "message": "Couldn't reach Razorpay to start your payment — please try again.",
        },
    )


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/{lead_id}/payment")
async def get_lead_payment_context(lead_id: UUID, db: DbDep) -> LeadPaymentContextOut:
    """Fetch context for the Lead's payment page (SPEC-0001 §API surface,
    `GET /api/leads/:id/payment`).

    No tenant scoping (see module docstring) — a Lead with no platform
    account reaches this straight from their email link. Read-only and safe
    to reopen any number of times: no duplicate-order risk from the GET
    itself, per spec (order creation only ever happens in the POST below).
    """
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise _lead_not_found_error()

    config = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == lead.hc_user_id)
    )).scalar_one_or_none()
    if config is None:
        # Same data-anomaly-degrades-gracefully discipline as upload.py's
        # _resolve_token: a Lead row implies an HcLeadgenConfig row exists
        # (Stage 1 setup precedes the intake flow that creates Leads at
        # all), but this is a public endpoint — don't 500 on an
        # inconsistency, treat it the same as "this Lead doesn't resolve".
        raise _lead_not_found_error()

    hc_user = await db.get(User, lead.hc_user_id)
    if hc_user is None:
        raise _lead_not_found_error()

    hc_name = f"{hc_user.first_name} {hc_user.last_name}".strip()

    return LeadPaymentContextOut(
        hc_name=hc_name,
        consultation_fee_inr=config.consultation_fee_inr,
        payment_status=lead.payment_status,
        scheduling_link=config.scheduling_link if lead.payment_status == "paid" else None,
    )


@router.post("/{lead_id}/payment/order")
async def create_payment_order(
    lead_id: UUID, request: Request, db: DbDep
) -> CreatePaymentOrderOut:
    """Create a Razorpay Order for this Lead's consultation fee (SPEC-0001
    Stage 4 step 1), or return the already-pending one on reload.

    Reload-idempotency: a Lead reopening the payment page before completing
    (or ever starting) Razorpay's hosted Checkout must not mint a fresh Order
    every time — that would litter the HC's Razorpay dashboard with
    abandoned duplicates every reload. This is scoped to
    `payment_status == "unpaid"` specifically, not just "a payment_reference
    is present": a failed/cancelled attempt is retry-safe by spec ("nothing
    was held... retrying is a fresh attempt, not a resume" — edge-cases
    table), so a Lead whose most recent attempt ended in `payment_status ==
    "failed"` falls through to mint a NEW order below rather than
    resurrecting the failed one. `payment_status == "paid"` also falls
    through to this same "create new" path rather than the reuse branch —
    not expected to be reachable in practice (the frontend stops offering
    the payment form once `GET .../payment` reports `paid`), but nothing
    here treats an already-paid Lead specially; it is out of this task's
    scope to add a dedicated guard for a state the frontend is not expected
    to reach.

    `create_order()` (src/lib/razorpay_client.py) deliberately propagates a
    non-2xx Razorpay response (or a network failure) rather than swallowing
    it — this is a public, Lead-facing endpoint, so that raise is caught at
    this boundary and translated into a structured error, never left to
    surface as a 500. Same non-raising-at-the-boundary discipline as
    `payment_accounts.py`'s `connect_payment_account` around
    `verify_credentials()`.
    """
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise _lead_not_found_error()

    account = (await db.execute(
        select(HcPaymentAccount).where(HcPaymentAccount.hc_user_id == lead.hc_user_id)
    )).scalar_one_or_none()
    if account is None or account.connected_at is None:
        raise _payment_not_available_error()

    credentials = account.credentials
    if credentials is None:
        # Shouldn't happen alongside a non-null connected_at (the connect
        # endpoint sets both together), but this is a public endpoint —
        # degrade to the same structured error rather than a KeyError/500.
        raise _payment_not_available_error()

    config = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == lead.hc_user_id)
    )).scalar_one_or_none()
    if config is None or config.consultation_fee_inr is None:
        raise _payment_not_available_error()

    key_id: str = credentials["key_id"]
    # THE load-bearing conversion (task brief §3): Razorpay's Orders API
    # takes an amount in paise; `consultation_fee_inr` is stored as whole
    # rupees (src/db/models/leadgen.py). Missing this ×100 either fails
    # Razorpay's minimum-amount check or silently charges 1/100th the
    # intended fee.
    amount_paise = config.consultation_fee_inr * 100

    if lead.payment_reference is not None and lead.payment_status == "unpaid":
        return CreatePaymentOrderOut(
            order_id=lead.payment_reference, key_id=key_id, amount_paise=amount_paise
        )

    key_secret: str = credentials["key_secret"]
    logger = get_logger(
        request_id=getattr(request.state, "request_id", ""), hc_id=str(lead.hc_user_id)
    )
    try:
        order = await create_order(
            key_id=key_id,
            key_secret=key_secret,
            amount_paise=amount_paise,
            notes={"hc_user_id": str(lead.hc_user_id), "lead_id": str(lead.id)},
        )
    except httpx.HTTPError as exc:
        logger.error("razorpay_create_order_failed", lead_id=str(lead.id))
        raise _razorpay_unreachable_error() from exc

    order_id = order.get("id")
    if not order_id:
        # Malformed 2xx response — not a documented possibility of
        # create_order(), but this endpoint is public and must not 500 on
        # it regardless.
        logger.error("razorpay_create_order_missing_id", lead_id=str(lead.id))
        raise _razorpay_unreachable_error()

    lead.payment_reference = order_id
    lead.status = "payment_pending"
    # payment_status stays "unpaid" — only the webhook (Task 6) sets "paid".
    await db.commit()

    return CreatePaymentOrderOut(order_id=order_id, key_id=key_id, amount_paise=amount_paise)
