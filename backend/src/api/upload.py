"""Public Lead-facing upload endpoints (Unit_003 PHASE-03). No auth — resolved by
the raw upload token mailed to the Lead in Stage 3 (see `intake.py`'s
`submit_intake_questionnaire`, which mints `LeadUploadToken.token_hash`).

Security note: like `intake.py`, responses here are a strict allowlist — build
response models field-by-field, never `.model_validate()` a full ORM object.
"""
import hashlib
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import DbDep
from src.config import get_settings
from src.db.models import Lead, LeadFile, LeadUploadToken, User
from src.lib.email import send_lead_brief_failed_email, send_lead_brief_ready_email
from src.lib.file_extraction import extract_text
from src.lib.mime_sniff import sniff_mime
from src.lib.rate_limit import limiter
from src.lib.s3 import _sanitize, s3_put
from src.telemetry.log import get_logger

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

# Task 6 — no SPEC-0001-quoted copy exists for this confirmation (only the
# expired/used edge-case rows are quoted verbatim). Plain-language, tone-matched
# to this file's other Lead-facing copy.
_UPLOAD_SUCCESS_MESSAGE = (
    "Thanks — your reports have been received. Your health coach will review them "
    "before your consultation."
)

# Server-side re-validation of the client-side caps (Task 6 / PHASE-03 Decision D-3).
_MAX_FILES = 5
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_TOTAL_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB


class UploadTokenStateOut(BaseModel):
    """Discriminated response: `state` tells the frontend which of the four Stage-4
    states to render (SPEC-0001 §Stage 4 step 2). `message` carries this endpoint's
    plain-language copy for the three non-"valid" states. `hc_name` is present ONLY
    for state=="valid" — the single piece of information an unconsumed, unexpired
    link is allowed to reveal. No Lead PII, no questionnaire data ever appears here.

    Also reused by `POST /{token}/files` (Task 6) for its three token-invalid
    branches ("not found"/"used"/"expired"), so the frontend can share one
    discriminated-state renderer across both the GET check and the POST result —
    per the Task 6 brief's "matching error responses via the SAME discriminated
    response shape" requirement. POST never returns state=="valid" (a valid token
    always proceeds to either a validation error or `UploadFilesOut`).
    """
    state: Literal["not_found", "expired", "used", "valid"]
    message: str | None = None
    hc_name: str | None = None


class UploadFilesOut(BaseModel):
    """Success response for `POST /{token}/files`. Deliberately does not surface
    whether the pre-consultation brief succeeded or failed (Task 6 / Decision D-2)
    — from the Lead's point of view the upload itself always succeeded once this
    is returned; brief outcome is HC-internal (delivered via email, never to the
    Lead).
    """
    message: str


async def _resolve_token(
    db: AsyncSession, token: str
) -> tuple[
    Literal["not_found", "expired", "used", "valid"],
    LeadUploadToken | None,
    Lead | None,
    User | None,
]:
    """Shared token-state resolution, used by both the GET state-check (Task 5)
    and the POST upload endpoint (Task 6) — single source of truth for the
    not-found -> used -> expired -> valid check order (mirrors
    `src.auth.router._verify_invite`'s equivalent invite-token validation
    sequence).

    Returns `(state, upload_token, lead, hc_user)`. Only the fields resolvable
    before `state` was determined are populated — e.g. for state=="not_found"
    (token row missing entirely), all three are `None`; for state=="used",
    `upload_token` is populated but `lead`/`hc_user` are not (not needed to
    render the "used" response, and Task 5 never looked them up in that branch
    either). Callers must check `state` before trusting `lead`/`hc_user`.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    upload_token = (await db.execute(
        select(LeadUploadToken).where(LeadUploadToken.token_hash == token_hash)
    )).scalar_one_or_none()

    if upload_token is None:
        return "not_found", None, None, None

    if upload_token.used_at is not None:
        return "used", upload_token, None, None

    # Both "expired" and "valid" below need the owning HC's name. Resolved via
    # lead_id -> hc_user_id -> users, same two-hop `db.get()` pattern as
    # intake.py's `get_intake_config` (no ORM relationships are declared anywhere
    # in this codebase's models — manual joins are the convention).
    #
    # Both hops are expected non-null by FK constraints (`lead_upload_tokens.lead_id`
    # CASCADEs from `leads`; nothing in this codebase deletes a `users` row still
    # referenced by a `leads.hc_user_id`), but this is a public unauthenticated
    # endpoint — a data anomaly must degrade gracefully, not 500. Fall back to
    # "not_found" rather than raising.
    lead = await db.get(Lead, upload_token.lead_id)
    if lead is None:
        return "not_found", upload_token, None, None

    user = await db.get(User, lead.hc_user_id)
    if user is None:
        return "not_found", upload_token, lead, None

    if upload_token.expires_at < datetime.now(UTC):
        return "expired", upload_token, lead, user

    return "valid", upload_token, lead, user


@router.get("/{token}")
async def get_upload_token_state(token: str, db: DbDep) -> UploadTokenStateOut:
    """Resolve a public upload token to its current state.

    Always returns HTTP 200, unlike `intake.py`'s generic-404 pattern — this is a
    Lead-facing state machine, not a tenant-isolation boundary, and the page needs
    to render *which* invalid state occurred (never existed vs expired vs used).
    Deliberately NOT rate-limited: a read-only state check with no side effects,
    unlike `POST /api/intake/:slug`'s per-IP submission limit or this file's own
    `POST /{token}/files` below.
    """
    state, _upload_token, lead, user = await _resolve_token(db, token)

    if state == "not_found":
        return UploadTokenStateOut(state="not_found", message=_NOT_FOUND_MESSAGE)

    if state == "used":
        return UploadTokenStateOut(state="used", message=_USED_MESSAGE)

    assert lead is not None and user is not None  # guaranteed by _resolve_token for expired/valid
    hc_name = f"{user.first_name} {user.last_name}".strip()

    if state == "expired":
        return UploadTokenStateOut(
            state="expired", message=_EXPIRED_MESSAGE_TEMPLATE.format(hc_name=hc_name)
        )

    return UploadTokenStateOut(state="valid", hc_name=hc_name)


@router.post("/{token}/files")
@limiter.limit("10/hour")
async def upload_lead_files(
    request: Request,
    token: str,
    files: list[UploadFile],
    db: DbDep,
    response: Response,
) -> UploadTokenStateOut | UploadFilesOut:
    """Lead-facing blood report upload (SPEC-0001 Stage 4 steps 3-13; PHASE-03
    Task 6). No auth — resolved by the same raw upload token as the GET above.

    Rate-limited 10 req/hour per direct-connection IP (PHASE-03 Decision D-3;
    `src.lib.rate_limit.limiter`, keyed by `get_remote_address` only — no
    X-Forwarded-For trust, same convention as `intake.py`'s POST). `request:
    Request` is required by name for slowapi's key function to read the client IP.

    Token re-validated fresh on every call via `_resolve_token` (shared with the
    GET endpoint above) — a token that is not_found/used/expired returns the SAME
    `UploadTokenStateOut` shape the GET endpoint uses, at HTTP 200, with no upload
    processed. Only state=="valid" proceeds past this point.

    Validation (batch caps, then per-file MIME sniffing) happens for ALL files
    before ANY R2 write — a late per-file rejection must never leave earlier files
    already sitting in R2 while the token remains unused. Caps/MIME violations
    raise HTTPException(422); nothing is written anywhere.

    R2 upload + `LeadFile` row creation is sequential (PHASE-03 Decision D-5,
    not concurrent). If `s3_put()` raises partway through the batch, objects
    already written to R2 for earlier files in this batch are left as orphans
    (accepted tradeoff, not cleaned up — see task brief) but no `LeadFile` row is
    ever added to the session for ANY file in the batch (the `LeadFile` objects
    are only constructed, never `db.add()`-ed, until every file's `s3_put()` has
    succeeded), and neither `lead_upload_tokens.used_at` nor `leads.status` is
    touched before that point — so a mid-batch R2 failure leaves the DB exactly as
    it was before this request, and the token remains valid for a retry.

    Once all files are durably uploaded and committed (token used, lead status
    advanced to "report_uploaded"), brief generation (`generate_lead_brief`, Task
    3) is attempted. Per Decision D-2 — the whole point of this phase — nothing
    from here on can change this endpoint's success response: `generate_lead_brief`
    is documented to never raise, and the HC-notification emails are individually
    wrapped in try/except, log-only on failure (mirrors PHASE-02 Decision D-2's
    non-blocking email convention in `intake.py`).
    """
    logger = get_logger(request_id=getattr(request.state, "request_id", ""))

    state, upload_token, lead, hc_user = await _resolve_token(db, token)

    if state == "not_found":
        return UploadTokenStateOut(state="not_found", message=_NOT_FOUND_MESSAGE)
    if state == "used":
        return UploadTokenStateOut(state="used", message=_USED_MESSAGE)
    if state == "expired":
        assert lead is not None and hc_user is not None
        hc_name = f"{hc_user.first_name} {hc_user.last_name}".strip()
        return UploadTokenStateOut(
            state="expired", message=_EXPIRED_MESSAGE_TEMPLATE.format(hc_name=hc_name)
        )

    # state == "valid"
    assert upload_token is not None and lead is not None and hc_user is not None

    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required.",
        )
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Too many files — a maximum of {_MAX_FILES} is allowed per upload.",
        )

    # ── Read + size-validate every file before any MIME check or R2 write ───────
    contents: list[bytes] = []
    total_size = 0
    for f in files:
        content = await f.read()
        if len(content) > _MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"File '{f.filename}' exceeds the "
                    f"{_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per-file limit."
                ),
            )
        total_size += len(content)
        contents.append(content)

    if total_size > _MAX_TOTAL_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Total upload size exceeds the "
                f"{_MAX_TOTAL_SIZE_BYTES // (1024 * 1024)} MB limit."
            ),
        )

    # ── MIME-sniff every file (Task 1) — reject the WHOLE batch before any R2
    # write if ANY file is unrecognized. Deliberately validate-all-first, not
    # interleaved with the upload loop below.
    sniffed: list[tuple[UploadFile, bytes, str]] = []
    for f, content in zip(files, contents, strict=True):
        mime = sniff_mime(content)
        if mime is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File '{f.filename}' is not a recognized PDF, JPEG, or PNG file.",
            )
        sniffed.append((f, content, mime))

    # ── Sequential R2 upload + (uncommitted) LeadFile row construction (D-5) ────
    # `LeadFile` instances are only `db.add()`-ed after every file in the batch
    # has been successfully `s3_put()`'d — see the loop below. If any `s3_put()`
    # raises, no `LeadFile` has been added to the session yet, so there is nothing
    # to roll back: `db.commit()` (and the used_at/status writes that precede it)
    # is never reached, and the token stays unused / lead status untouched.
    new_lead_files: list[LeadFile] = []
    try:
        for f, content, mime in sniffed:
            filename = f.filename or "unnamed"
            epoch_ms = int(datetime.now(UTC).timestamp() * 1000)
            key = f"leads/{lead.id}/reports/{epoch_ms}_{_sanitize(filename, max_len=200)}"
            await s3_put(key, content, mime)
            new_lead_files.append(LeadFile(
                lead_id=lead.id,
                hc_user_id=lead.hc_user_id,
                filename=filename,
                s3_key=key,
                mime_type=mime,
                file_size_bytes=len(content),
                purpose="blood_report",
            ))
    except Exception as exc:
        # R2 failure: objects already s3_put()'d for earlier files in this batch
        # are left as orphans in R2 (accepted tradeoff — not deleted). No DB
        # write has happened yet (see docstring), so the token/lead state is
        # untouched and the Lead can safely retry with the same link.
        logger.error("lead_upload_r2_put_failed", lead_id=str(lead.id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We couldn't process your upload. Please try again — your link is still valid.",
        ) from exc

    # ── All files uploaded — commit LeadFile rows, mark token used, advance
    # lead status. One transaction (SPEC-0001 Stage 4 steps 9-11).
    for lf in new_lead_files:
        db.add(lf)
    upload_token.used_at = datetime.now(UTC)
    lead.status = "report_uploaded"
    await db.commit()

    # Captured as plain locals — not strictly required (this session has
    # expire_on_commit=False, per src/db/session.py), but matches intake.py's
    # defensive convention of not reading ORM attributes off objects after a
    # commit/rollback boundary.
    lead_id: UUID = lead.id
    hc_user_id: UUID = lead.hc_user_id
    lead_full_name = lead.full_name
    hc_name = f"{hc_user.first_name} {hc_user.last_name}".strip()
    hc_email = hc_user.email

    # ── Text extraction + brief generation (SPEC-0001 Stage 4 steps 12-13) ──────
    # extract_text() returns "" for a non-PDF mime type by its own fallback branch
    # — so calling it uniformly across every accepted file (not just PDFs)
    # naturally makes accepted JPEG/PNG files contribute an empty string rather
    # than an error, with no special-casing needed here. It does NOT, however,
    # guard its own `application/pdf` branch against `pypdf.PdfReader` raising on
    # a corrupt/unparseable-but-magic-byte-valid PDF (confirmed by reading
    # file_extraction.py — no try/except around that branch) — so THIS call site
    # wraps every extraction in try/except, treating an extraction failure the
    # same as "no text found": empty string, upload/brief flow continues
    # regardless ("gap-note" path — the brief itself notes what couldn't be read).
    extracted_texts: list[str] = []
    for _f, content, mime in sniffed:
        try:
            text = await extract_text(content, mime)
        except Exception as exc:
            logger.warn("lead_upload_extract_text_failed", lead_id=str(lead_id), error=str(exc))
            text = ""
        extracted_texts.append(text)
    blood_report_text = "\n\n".join(t for t in extracted_texts if t)

    # Local import mirrors `src.api.sessions`'s existing convention for calling
    # into `src.llm_service` (see `generate_brief`/`generate_mom_draft` call
    # sites) rather than importing at module level.
    from src.llm_service import generate_lead_brief

    # Decision D-2 (the whole point of this phase): generate_lead_brief() is
    # documented and tested to never raise — but this call is still wrapped
    # defensively so that even a contract violation there cannot flip this
    # endpoint's response away from "upload succeeded", which is already true by
    # this point (LeadFile rows + used_at + status are already committed above).
    try:
        brief_text, llm_call_id = await generate_lead_brief(
            db,
            lead_id=lead_id,
            hc_user_id=hc_user_id,
            blood_report_text=blood_report_text,
        )
    except Exception as exc:  # pragma: no cover — defensive only; contract says this never fires
        logger.error("lead_brief_generation_unexpected_raise", lead_id=str(lead_id), error=str(exc))
        brief_text, llm_call_id = None, None

    lead_detail_link = f"{get_settings().frontend_url}/leads/{lead_id}"

    if brief_text is not None:
        lead.brief_text = brief_text
        lead.brief_llm_call_id = llm_call_id
        await db.commit()
        try:
            send_lead_brief_ready_email(
                to=hc_email, hc_name=hc_name, lead_name=lead_full_name,
                lead_detail_link=lead_detail_link,
            )
        except Exception as exc:
            logger.error("lead_brief_ready_email_failed", lead_id=str(lead_id), error=str(exc))
    else:
        # leads.status stays "report_uploaded" (already committed above) —
        # brief generation failing does not roll anything back.
        try:
            send_lead_brief_failed_email(
                to=hc_email, hc_name=hc_name, lead_name=lead_full_name,
                lead_detail_link=lead_detail_link,
            )
        except Exception as exc:
            logger.error("lead_brief_failed_email_failed", lead_id=str(lead_id), error=str(exc))

    response.status_code = status.HTTP_201_CREATED
    return UploadFilesOut(message=_UPLOAD_SUCCESS_MESSAGE)
