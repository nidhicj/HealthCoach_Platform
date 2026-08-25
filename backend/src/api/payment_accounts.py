"""HC-facing Razorpay payment-account connect endpoints. PHASE-05 (payment +
scheduling handoff), Task 2.

  GET  /api/hc/payment-account          -> {"connected": bool}
  POST /api/hc/payment-account/connect  -> verify + store the HC's own
                                            Razorpay key_id/key_secret/webhook_secret

Mirrors leads.py's HC-authenticated endpoint pattern (require_role('hc') +
current_tenant() via src.api.deps) and payments.py/calendar.py's one-row-per-HC
upsert shape (GoogleCalendarConnection). Unlike calendar.py's OAuth-driven
connect flow, credentials here are pasted by the HC directly, so this router
owns both verification (via razorpay_client.verify_credentials, Task 1) and
storage — there is no separate provider-hosted redirect/callback.

Credentials are write-only from this API's perspective: no route here ever
returns the stored `credentials` dict, in a success or error response, to
anyone — including the owning HC.
"""
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models import HcPaymentAccount
from src.lib.razorpay_client import verify_credentials
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/hc/payment-account", tags=["payment-account"])


# ── schemas ────────────────────────────────────────────────────────────────────


class PaymentAccountStatusOut(BaseModel):
    connected: bool


class ConnectPaymentAccountIn(BaseModel):
    key_id: str = Field(max_length=200)
    key_secret: str = Field(max_length=200)
    webhook_secret: str = Field(max_length=200)

    @field_validator("key_id", "key_secret", "webhook_secret")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


# ── errors ─────────────────────────────────────────────────────────────────────


def _invalid_credentials_error() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": "invalid_credentials",
            "message": (
                "Could not verify these Razorpay credentials — check they're "
                "correct and in test mode."
            ),
        },
    )


def _razorpay_unreachable_error() -> HTTPException:
    # 502 (not 503): this route is acting as a proxy to an external service for
    # the verification call, same framing as calendar.py's 502s for a failed
    # Google Calendar proxy call (calendar_events_fetch_failed /
    # calendar_event_create_failed) — the failure is "the upstream we depend on
    # broke", not "our own endpoint is overloaded/unavailable" (which 503 would
    # imply). Kept as a distinct helper (rather than reusing calendar.py's) so
    # its structured {error, message} body matches this endpoint's own schema.
    return HTTPException(
        status_code=502,
        detail={
            "error": "razorpay_unreachable",
            "message": (
                "Couldn't reach Razorpay to verify these credentials — please try again."
            ),
        },
    )


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("")
async def get_payment_account_status(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> PaymentAccountStatusOut:
    account = (await db.execute(
        select(HcPaymentAccount).where(HcPaymentAccount.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    connected = account is not None and account.connected_at is not None
    return PaymentAccountStatusOut(connected=connected)


@router.post("/connect")
async def connect_payment_account(
    body: ConnectPaymentAccountIn,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    request: Request,
) -> PaymentAccountStatusOut:
    """Verify the pasted Razorpay credentials, then upsert this HC's row.

    Reconnecting (a second call, e.g. after rotating keys in the Razorpay
    dashboard) overwrites the previously stored credentials and bumps
    `updated_at` — deliberately not blocked; there is no separate "disconnect"
    flow at this scope (per the task brief).
    """
    request_id = getattr(request.state, "request_id", "")
    logger = get_logger(request_id=request_id, hc_id=hc_id)

    try:
        verified = await verify_credentials(key_id=body.key_id, key_secret=body.key_secret)
    except httpx.HTTPError as exc:
        # razorpay_client.verify_credentials() deliberately lets network/5xx
        # failures propagate rather than collapsing them into `False` — this
        # is the distinction the brief requires: a transient Razorpay/network
        # failure must never be reported to the HC as "your key is wrong".
        logger.error("razorpay_verify_credentials_failed", outcome="unreachable")
        raise _razorpay_unreachable_error() from exc

    if not verified:
        logger.info("razorpay_verify_credentials_failed", outcome="invalid_credentials")
        raise _invalid_credentials_error()

    now = datetime.now(timezone.utc)
    credentials = {
        "key_id": body.key_id,
        "key_secret": body.key_secret,
        "webhook_secret": body.webhook_secret,
    }

    account = (await db.execute(
        select(HcPaymentAccount).where(HcPaymentAccount.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()

    if account is None:
        account = HcPaymentAccount(
            hc_user_id=UUID(hc_id), credentials=credentials, connected_at=now
        )
        db.add(account)
    else:
        # Reassign (rather than mutate in place) so SQLAlchemy's change
        # tracking sees a new value on this EncryptedJSON column and
        # re-encrypts on flush — same discipline as calendar.py's
        # _get_valid_access_token token refresh.
        account.credentials = credentials
        account.connected_at = now
        account.updated_at = now

    await db.commit()
    logger.info("razorpay_credentials_connected")
    return PaymentAccountStatusOut(connected=True)
