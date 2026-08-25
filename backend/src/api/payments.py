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
returns `scheduling_link` once `payment_status == "paid"`; POST never mints a
second real order for the same Lead once one is pending OR once payment has
already succeeded, see `create_payment_order`'s docstring) — so reusing the
Lead's permanent identifier as the link's bearer credential is a deliberate
simplification for this endpoint, not an oversight of the hashed-token
pattern used elsewhere. This matters because the endpoint is reachable at any
time from a bookmarked/emailed link, a stale browser tab, or a replayed
request — "the frontend won't offer the form once paid" is UX, not a security
boundary this backend can rely on.

`leads.py`'s router (`src/api/leads.py`) is HC-authenticated throughout
(`HcClaimsDep`/`TenantDep`) — these routes are deliberately public (a Lead
with no platform account must be able to reach them straight from the "book &
pay" button in Stage 3's email), so they live in their own file with their
own un-auth'd router, making that boundary visible in the code rather than
only in a comment on a shared one. `POST /api/payments/webhook` (Task 6) is a
second router in this same file (`webhook_router`, `prefix="/api/payments"`)
— its "auth" is the HMAC signature check itself, not a bearer token, so it
gets its own `APIRouter` rather than sharing `router` above.

Security note: like `intake.py`/`upload.py`, responses here are a strict
allowlist — response models are built field-by-field, never
`.model_validate()`d off a full ORM object. `key_secret` (and the whole
`credentials` dict) never appears in a response body or a log line.
"""
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import DbDep
from src.db.models import HcLeadgenConfig, HcPaymentAccount, Lead, LeadUploadToken, User
from src.lib.razorpay_client import create_order, verify_webhook_signature
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/leads", tags=["payments"])
webhook_router = APIRouter(prefix="/api/payments", tags=["payments"])


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


class WebhookAckOut(BaseModel):
    """Body Razorpay receives back on every 200 — Razorpay itself only checks
    the status code, this is purely for humans reading logs/traces."""
    status: str = "ok"


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


def _already_paid_error() -> HTTPException:
    # Guards create_payment_order's "already paid" path (review round 1,
    # Critical finding): a Lead can reach this public endpoint at any time
    # via a bookmarked/emailed link, a stale tab, or a replayed request —
    # long after payment_status flipped to "paid" and lead.status has moved
    # on to consultation_scheduled/report_uploaded/converted/etc. Falling
    # through to the "create new order" branch in that state would silently
    # reset lead.status back to "payment_pending" and overwrite
    # payment_reference with a fresh, unrelated Order, discarding the
    # reference to what was actually paid and (if a stale checkout flow ever
    # completed against the new order) risking a second real charge. This is
    # a read-only short-circuit: no DB write, no create_order() call. A
    # frontend that still calls this after GET already reported
    # payment_status == "paid" should treat this the same way it already
    # treats that GET response — nothing new to signal beyond what GET gave
    # it up front.
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "already_paid",
            "message": "This consultation has already been paid for.",
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


# Uniform 400 body for every pre-trust webhook rejection (malformed payload,
# unresolvable hc_user_id, unknown/unconnected account, missing
# webhook_secret, signature mismatch). `POST /api/payments/webhook` is
# unauthenticated by design — the HMAC check itself IS the auth — so
# distinguishing rejection reasons in the HTTP response would hand an
# unauthenticated caller an oracle (e.g. "which hc_user_id values are
# onboarded on this platform" by comparing which 400 body comes back). The
# real reason for each rejection is only ever recorded server-side, in the
# log line immediately before the raise.
_WEBHOOK_REJECT_MESSAGE = "Invalid webhook request."

_RAZORPAY_PAYMENT_CAPTURED_EVENT = "payment.captured"


def _webhook_reject() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_WEBHOOK_REJECT_MESSAGE)


def _nested_dict(obj: Any, *keys: str) -> dict[str, Any]:
    """Defensively walk a chain of dict keys in an untrusted (pre-signature-
    verification) payload, returning `{}` the moment anything along the way
    isn't a dict — never raises on a malformed/malicious webhook body."""
    for key in keys:
        if not isinstance(obj, dict):
            return {}
        obj = obj.get(key)
    return obj if isinstance(obj, dict) else {}


def _hc_user_id_from_notes(entity: dict[str, Any]) -> str | None:
    """Pull a usable `hc_user_id` out of one entity's `notes` dict, or
    `None` if `notes` is absent/not a dict/has no non-empty string
    `hc_user_id`. Shared by both extraction paths `razorpay_webhook` tries
    below (PHASE-05 final-review fix round, Fix #3)."""
    notes = entity.get("notes")
    hc_user_id_raw = notes.get("hc_user_id") if isinstance(notes, dict) else None
    return hc_user_id_raw if isinstance(hc_user_id_raw, str) and hc_user_id_raw else None


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

    # Fallback guards against a blank/"None None" render if both names are
    # unset (`first_name`/`last_name` are nullable on User) — review round 1,
    # Important finding #1: this function already degrades gracefully for
    # `credentials is None`/`consultation_fee_inr is None` a few lines away
    # in the POST handler below; this GET handler's own untested, previously
    # undefended assumption that names are always populated by the time a
    # Lead reaches this Lead-facing page deserved the same treatment. Same
    # fallback string as `leads.py::send_test_recommendation`'s identical
    # guard for the same underlying gap.
    hc_first = hc_user.first_name or ""
    hc_last = hc_user.last_name or ""
    hc_name = f"{hc_first} {hc_last}".strip() or "Your Coach"

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

    Three distinct outcomes for a Lead who already has SOME payment history,
    keyed off `payment_status` — this endpoint is public and reachable at
    any time via a bookmarked/emailed link, a stale browser tab, or a
    replayed request, so each of these is a real, not merely theoretical,
    call pattern (review round 1, Critical finding):

    - `payment_status == "paid"`: short-circuits to `_already_paid_error()`
      (409) immediately, before even looking up the payment account/fee
      config. Read-only — no DB write, no `create_order()` call. Falling
      through to "create new order" here (the original, pre-review-round
      behavior) would silently reset `lead.status` back to
      `"payment_pending"` even if it had already advanced to
      `consultation_scheduled`/`report_uploaded`/`converted`/etc., overwrite
      `payment_reference` with a fresh, unrelated Order (discarding the
      reference to what was actually paid), and hand back a real, valid
      `key_id` + Order that — if a stale checkout flow ever completed
      against it — could charge the Lead a second time.
    - `payment_status == "unpaid"` AND `payment_reference` already set:
      reload-idempotency — return the existing pending Order rather than
      minting a fresh one, so repeatedly reopening the payment page before
      completing (or ever starting) Razorpay's hosted Checkout doesn't
      litter the HC's Razorpay dashboard with abandoned duplicates.
    - `payment_status == "failed"` (or `"refunded"`, or `"unpaid"` with no
      `payment_reference` yet): falls through to mint a NEW order. A
      failed/cancelled attempt is retry-safe by spec ("nothing was held...
      retrying is a fresh attempt, not a resume" — edge-cases table), so a
      Lead whose most recent attempt ended in `"failed"` must NOT have that
      failed order resurrected — this is why the reuse branch above is
      scoped to `"unpaid"` specifically, not "any non-null
      `payment_reference`".

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

    if lead.payment_status == "paid":
        raise _already_paid_error()

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

    key_id: str | None = credentials.get("key_id")
    if not key_id:
        # Same "shouldn't happen, but this is public — degrade, don't
        # KeyError/500" discipline as the `credentials is None` guard above
        # (review round 1, Important finding #2: this previously used bare
        # `credentials["key_id"]` subscription).
        raise _payment_not_available_error()

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

    key_secret: str | None = credentials.get("key_secret")
    if not key_secret:
        # Same rationale as the key_id guard above.
        raise _payment_not_available_error()

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


@webhook_router.post("/webhook")
async def razorpay_webhook(request: Request, db: DbDep) -> WebhookAckOut:
    """Razorpay webhook receiver (PHASE-05 Task 6) — the point where the
    platform decides "this Lead really paid" and trusts it. Get this exactly
    right; nothing here is simplified for convenience.

    Verification algorithm (this phase's plan doc §3, followed exactly):

      1. Read the RAW request body bytes (`await request.body()`) before any
         JSON parsing — needed verbatim for HMAC. A re-serialized/re-parsed
         body is not guaranteed to reproduce the exact bytes Razorpay signed.
      2. Parse the JSON (still untrusted). Extract `hc_user_id` from
         `payload.payment.entity.notes` — Task 5's `create_payment_order`
         sets `notes={"hc_user_id": ..., "lead_id": ...}` on the Order at
         creation time, and Razorpay's `payment.captured` webhook payload
         docs describe an Order's `notes` as carried onto its resulting
         `payment.entity` verbatim (see task-6-report.md for the payload
         shape this was checked against during implementation). This has
         NOT been confirmed against a real Razorpay sandbox (no test-mode
         credentials exist in this environment) — the single biggest
         unverified assumption in this whole handler (flagged explicitly in
         PHASE-05's final-review fix round, Fix #3). Defense in depth: if
         `payload.payment.entity.notes` is absent, not a dict, or has no
         usable `hc_user_id`, this step falls back to
         `payload.order.entity.notes` (same `notes` Task 5 set on the Order
         itself) before giving up. If BOTH paths come up empty, that's
         logged with which path(s) were tried, so a real failure here is
         diagnosable from logs rather than a silent black box.
      3. Look up that `hc_user_id`'s `HcPaymentAccount` row. No row / not
         connected / no `webhook_secret` on file -> reject 400 immediately —
         logged as a suspicious event (this could be a forged webhook
         attempt targeting an `hc_user_id` that was never onboarded, not
         merely a data anomaly). Never attempt verification against any
         other account's secret.
      4. Recompute HMAC-SHA256 over the raw body with that HC's
         `webhook_secret` (`razorpay_client.verify_webhook_signature` — the
         already-shipped, already-tested implementation, not reimplemented
         here) and compare to the `X-Razorpay-Signature` header via
         `hmac.compare_digest` (inside that function, for a constant-time
         comparison). Mismatch -> reject 400; the payload is never processed
         past this point.
      5. Only past step 4 is anything in the payload trusted — including the
         `event` field itself, which is why the `event` check below happens
         AFTER signature verification, not before.

    Every rejection before step 4 completes returns the SAME generic 400
    body (`_WEBHOOK_REJECT_MESSAGE`) for the oracle-avoidance reason
    documented at that constant. The real reason is only ever in the
    server-side log line immediately before each `raise`.

    Once verified, only `event == "payment.captured"` is processed (this
    task's documented scope). Any other event type this same webhook URL
    happens to receive (an HC's Razorpay dashboard could have more than one
    event enabled for it) is a genuine, correctly-signed webhook this
    handler simply doesn't act on — 200 no-op, not a 400, and not logged as
    suspicious.

    Idempotency: the verified payload's `order_id`
    (`payload.payment.entity.order_id`) is looked up against
    `leads.payment_reference`, cross-checked against the verified
    `hc_user_id` for tenant safety (Task 5's `create_payment_order` always
    writes both together, so a genuine match implies both belong to the same
    Lead). If no Lead matches, or the matched Lead is already
    `payment_status == "paid"`, this is a no-op 200 — Razorpay retries
    non-2xx responses, so a duplicate `payment.captured` delivery for an
    already-processed payment, or one this platform can't resolve to a
    Lead, must never be treated as an error worth retrying forever.

    On genuine first-time success: `payment_status="paid"`,
    `payment_reference` (re-)confirmed, `paid_at=now()`, AND this Lead's
    currently-unused `LeadUploadToken` (`used_at IS NULL` — Task 4
    guarantees at most one such row per Lead at any moment) gets
    `expires_at = now() + 14 days` — the D-8 mechanism that actually unlocks
    Stage 4's upload link. Both writes happen in the same commit; it's easy
    to do the first and forget the second. If zero or more than one unused
    token row exists (a data anomaly Task 4's invalidation should prevent,
    but this handler must not crash on it), that's logged as unexpected and
    skipped — the payment itself still succeeded and must not fail the
    webhook response over it.

    Returns 200 on every branch reached past signature verification,
    including every edge-case bookkeeping path above — never makes Razorpay
    retry a webhook that was already correctly handled.
    """
    logger = get_logger(request_id=getattr(request.state, "request_id", ""))

    # Step 1 — raw bytes, before any JSON parsing.
    raw_body = await request.body()

    # Step 2 — parse (still untrusted).
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warn("razorpay_webhook_malformed_json")
        raise _webhook_reject()

    if not isinstance(payload, dict):
        logger.warn("razorpay_webhook_malformed_payload_shape")
        raise _webhook_reject()

    payment_entity = _nested_dict(payload, "payload", "payment", "entity")
    hc_user_id_raw = _hc_user_id_from_notes(payment_entity)
    if hc_user_id_raw is None:
        # Fallback path (Fix #3): `payload.payment.entity.notes` is the
        # primary, documented-but-unconfirmed path (see this function's
        # docstring). Try the Order's own notes next — Task 5 sets the same
        # notes on Order creation — before giving up.
        order_entity = _nested_dict(payload, "payload", "order", "entity")
        hc_user_id_raw = _hc_user_id_from_notes(order_entity)
        if hc_user_id_raw is None:
            logger.warn(
                "razorpay_webhook_missing_hc_user_id",
                tried=["payment.entity.notes", "order.entity.notes"],
            )
            raise _webhook_reject()

    try:
        hc_user_id = UUID(hc_user_id_raw)
    except ValueError:
        logger.warn("razorpay_webhook_invalid_hc_user_id")
        raise _webhook_reject()

    # Step 3 — resolve the claimed HC's webhook_secret. No match / not
    # connected / no secret on file -> reject immediately, do not attempt
    # verification against any other account's secret.
    account = (await db.execute(
        select(HcPaymentAccount).where(HcPaymentAccount.hc_user_id == hc_user_id)
    )).scalar_one_or_none()

    if account is None or account.connected_at is None or account.credentials is None:
        logger.warn(
            "razorpay_webhook_unknown_hc_account",
            hc_user_id=str(hc_user_id),
            note="possible forged webhook attempt",
        )
        raise _webhook_reject()

    webhook_secret = account.credentials.get("webhook_secret")
    if not webhook_secret:
        logger.warn(
            "razorpay_webhook_no_webhook_secret_on_file",
            hc_user_id=str(hc_user_id),
            note="possible forged webhook attempt",
        )
        raise _webhook_reject()

    # Step 4 — constant-time HMAC verification (razorpay_client.py, Task 1).
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_webhook_signature(
        raw_body=raw_body, signature=signature, webhook_secret=webhook_secret
    ):
        logger.warn("razorpay_webhook_signature_mismatch", hc_user_id=str(hc_user_id))
        raise _webhook_reject()

    # ── Step 5 — past this point, the payload (including `event`) is trusted. ──

    razorpay_event = payload.get("event")
    if razorpay_event != _RAZORPAY_PAYMENT_CAPTURED_EVENT:
        logger.info(
            "razorpay_webhook_ignored_event",
            hc_user_id=str(hc_user_id),
            razorpay_event=str(razorpay_event),
        )
        return WebhookAckOut()

    order_id = payment_entity.get("order_id")
    if not order_id or not isinstance(order_id, str):
        logger.error("razorpay_webhook_captured_missing_order_id", hc_user_id=str(hc_user_id))
        return WebhookAckOut()

    lead = (await db.execute(
        select(Lead).where(Lead.payment_reference == order_id, Lead.hc_user_id == hc_user_id)
    )).scalar_one_or_none()

    if lead is None:
        logger.error(
            "razorpay_webhook_no_matching_lead", hc_user_id=str(hc_user_id), order_id=order_id
        )
        return WebhookAckOut()

    if lead.payment_status == "paid":
        # Idempotent no-op — duplicate delivery of an already-processed payment.
        logger.info("razorpay_webhook_duplicate_delivery_noop", lead_id=str(lead.id))
        return WebhookAckOut()

    now = datetime.now(UTC)
    lead.payment_status = "paid"
    lead.payment_reference = order_id
    lead.paid_at = now

    unused_tokens = (await db.execute(
        select(LeadUploadToken).where(
            LeadUploadToken.lead_id == lead.id, LeadUploadToken.used_at.is_(None)
        )
    )).scalars().all()

    if len(unused_tokens) == 1:
        unused_tokens[0].expires_at = now + timedelta(days=14)
    else:
        # Task 4 invalidates any prior unused token on every Send, so this
        # should be unreachable — but this handler must not crash on a data
        # anomaly. The payment itself still succeeded; log and move on.
        logger.error(
            "razorpay_webhook_unexpected_unused_token_count",
            lead_id=str(lead.id),
            count=len(unused_tokens),
        )

    await db.commit()
    logger.info(
        "razorpay_webhook_payment_captured", lead_id=str(lead.id), hc_user_id=str(hc_user_id)
    )
    return WebhookAckOut()
