"""Public Lead-facing upload endpoints (Unit_003 PHASE-03). No auth — resolved by
the raw upload token mailed to the Lead in Stage 3 (see `intake.py`'s
`submit_intake_questionnaire`, which mints `LeadUploadToken.token_hash`).

Security note: like `intake.py`, responses here are a strict allowlist — build
response models field-by-field, never `.model_validate()` a full ORM object. This
file currently holds only the read-only token-state check (Task 5); a follow-up
task adds `POST /api/upload/:token/files` to this same router.
"""
import hashlib
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import DbDep
from src.db.models import Lead, LeadUploadToken, User

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Verbatim copy from SPEC-0001's edge-cases table, row "Lead opens an already-used
# upload link".
_USED_MESSAGE = (
    "Your reports have already been uploaded successfully. No further action needed."
)

# Verbatim copy from SPEC-0001's edge-cases table, row "Lead opens an expired
# upload link" — `{hc_name}` fills the spec's "[HC Name]" placeholder.
_EXPIRED_MESSAGE_TEMPLATE = "This upload link has expired. Please contact {hc_name} for a new link."

# SPEC-0001 only quotes copy for the expired/used rows — a token that never
# existed (typo'd link, tampered link) has no spec-mandated copy. Generic message,
# tone-matched to the closest existing precedent for an invalid token-gated link:
# frontend/src/app/(public)/invite/page.tsx's "This invite link is invalid or has
# expired. Please ask your coach for a new one."
_NOT_FOUND_MESSAGE = "This upload link is invalid. Please contact your health coach for a new link."


class UploadTokenStateOut(BaseModel):
    """Discriminated response: `state` tells the frontend which of the four Stage-4
    states to render (SPEC-0001 §Stage 4 step 2). `message` carries this endpoint's
    plain-language copy for the three non-"valid" states. `hc_name` is present ONLY
    for state=="valid" — the single piece of information an unconsumed, unexpired
    link is allowed to reveal. No Lead PII, no questionnaire data ever appears here.
    """
    state: Literal["not_found", "expired", "used", "valid"]
    message: str | None = None
    hc_name: str | None = None


@router.get("/{token}")
async def get_upload_token_state(token: str, db: DbDep) -> UploadTokenStateOut:
    """Resolve a public upload token to its current state.

    Always returns HTTP 200, unlike `intake.py`'s generic-404 pattern — this is a
    Lead-facing state machine, not a tenant-isolation boundary, and the page needs
    to render *which* invalid state occurred (never existed vs expired vs used).
    Deliberately NOT rate-limited: a read-only state check with no side effects,
    unlike `POST /api/intake/:slug`'s per-IP submission limit.

    Check order (not found -> used -> expired -> valid) mirrors
    `src.auth.router._verify_invite`'s equivalent invite-token validation sequence.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    upload_token = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.token_hash == token_hash)
    )).scalar_one_or_none()

    if upload_token is None:
        return UploadTokenStateOut(state="not_found", message=_NOT_FOUND_MESSAGE)

    if upload_token.used_at is not None:
        return UploadTokenStateOut(state="used", message=_USED_MESSAGE)

    # Both "expired" and "valid" below need the owning HC's name. Resolved via
    # lead_id -> hc_user_id -> users, same two-hop `db.get()` pattern as
    # intake.py's `get_intake_config` (no ORM relationships are declared anywhere
    # in this codebase's models — ManualJoins are the convention).
    #
    # Both hops are expected non-null by FK constraints (`lead_upload_tokens.lead_id`
    # CASCADEs from `leads`; nothing in this codebase deletes a `users` row still
    # referenced by a `leads.hc_user_id`), but this is a public unauthenticated
    # endpoint — a data anomaly must degrade gracefully, not 500. Fall back to
    # "not_found" rather than raising.
    lead = await db.get(Lead, upload_token.lead_id)
    if lead is None:
        return UploadTokenStateOut(state="not_found", message=_NOT_FOUND_MESSAGE)

    user = await db.get(User, lead.hc_user_id)
    if user is None:
        return UploadTokenStateOut(state="not_found", message=_NOT_FOUND_MESSAGE)

    hc_name = f"{user.first_name} {user.last_name}".strip()

    if upload_token.expires_at < datetime.now(UTC):
        return UploadTokenStateOut(
            state="expired", message=_EXPIRED_MESSAGE_TEMPLATE.format(hc_name=hc_name)
        )

    return UploadTokenStateOut(state="valid", hc_name=hc_name)
