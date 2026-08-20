"""Public HC intake endpoints (Unit_003 PHASE-02). No auth — resolved by hc_slug.

Security note: responses here are a strict allowlist. Never call `.model_validate()`
(or similar) on the full `HcLeadgenConfig`/`User` objects — build the response model
field-by-field so a future column addition to those tables can't silently leak
through this public endpoint.
"""
import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.deps import DbDep
from src.config import get_settings
from src.db.models import HcLeadgenConfig, Lead, LeadQuestionnaireResponse, LeadUploadToken, User
from src.lib.email import send_lead_test_recommendation_email
from src.lib.rate_limit import limiter
from src.telemetry.log import get_logger

router = APIRouter(prefix="/api/intake", tags=["intake"])

# Verbatim copy from SPEC-0001 Stage 2 step 3 (consent notice) — DPDP requires the
# purpose statement stored on `leads.consent_purpose` to match what the Lead actually
# saw and acknowledged.
_CONSENT_PURPOSE_TEMPLATE = (
    "Your responses will be shared only with {hc_name} for the purpose of your "
    "initial health consultation. We do not share your information with any third "
    "party."
)

# Verbatim copy from SPEC-0001's edge-cases table, row "Same email submits
# questionnaire twice to same HC".
_DUPLICATE_EMAIL_MESSAGE_TEMPLATE = (
    "Our records show you've already submitted your intake form for this coach. "
    "If you have questions, please contact {hc_name} directly."
)

# The six PHASE-01 D-2 fixed question keys that map onto dedicated `Lead` columns.
# age / primary_health_goal / current_health_concerns are also fixed keys but have
# no dedicated Lead column — they only ever exist as LeadQuestionnaireResponse rows.
_FULL_NAME_KEY = "full_name"
_EMAIL_KEY = "email"
_PHONE_KEY = "phone"

# Stage 3 — SPEC-0001 "Lab recommendation and token" acceptance criteria: 14-day
# expiry, identical TTL convention to `ClientInviteToken` (see clients.py's
# `_INVITE_TTL_DAYS` and `create_invite`'s token-generation pattern, mirrored below).
_UPLOAD_TOKEN_TTL_DAYS = 14


class IntakeConfigOut(BaseModel):
    hc_name: str
    hc_photo_url: str | None
    questionnaire: list[dict]


@router.get("/{hc_slug}")
async def get_intake_config(hc_slug: str, db: DbDep) -> IntakeConfigOut:
    """Resolve a public intake slug to the HC's name, photo, and questionnaire.

    Generic 404 for both "slug never existed" and "slug exists but leadgen isn't
    configured" — a slug only exists once `HcLeadgenConfig` is created (which
    requires a completed profile), so the single lookup below already covers both
    cases without leaking which one occurred.
    """
    config = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_slug == hc_slug)
    )).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    user = await db.get(User, config.hc_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return IntakeConfigOut(
        hc_name=f"{user.first_name} {user.last_name}".strip(),
        hc_photo_url=user.photo_url,
        questionnaire=config.questionnaire,
    )


class IntakeSubmissionIn(BaseModel):
    """Body shape: submitted answers keyed by question key (arbitrary — varies per
    HC's questionnaire config, including custom questions), plus `consent_ack`.

    `consent_ack` is a declared field; every other submitted key lands in
    `model_extra` via `extra="allow"` since the set of valid question keys is only
    known once we've loaded the HC's config (can't be a fixed pydantic schema).
    """
    consent_ack: bool = False

    model_config = {"extra": "allow"}


class IntakeSubmissionOut(BaseModel):
    lead_id: UUID
    status: str


def _is_empty_answer(answer: object) -> bool:
    if answer is None:
        return True
    if isinstance(answer, str) and not answer.strip():
        return True
    return False


def _validate_intake_responses(questionnaire: list[dict], responses: dict[str, object]) -> None:
    """Business-rule validation run before any DB write. Raises 422 with a list of
    human-readable problems if anything fails."""
    errors: list[str] = []
    for question in questionnaire:
        key = question["key"]
        answer = responses.get(key)
        empty = _is_empty_answer(answer)

        if question.get("required") and empty:
            errors.append(f"'{key}' is required")
            continue
        if empty:
            continue  # optional question, nothing submitted — no further checks

        if question["type"] == "multiple_choice":
            options = question.get("options") or []
            if str(answer) not in options:
                errors.append(f"'{key}' must be one of {options}")
        elif question["type"] == "scale":
            try:
                scale_value = int(str(answer))
            except (TypeError, ValueError):
                errors.append(f"'{key}' must be an integer between 1 and 10")
            else:
                if not (1 <= scale_value <= 10):
                    errors.append(f"'{key}' must be an integer between 1 and 10")

    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)


def _build_test_recommendation(test_panel: dict, responses: dict[str, str]) -> dict:
    """Pure function, no DB/HTTP — SPEC-0001 Stage 3 steps 2-5.

    `test_panel` is `HcLeadgenConfig.test_panel`:
    `{"standard_tests": [...], "condition_rules": [{"keywords": [...], "tests": [...]}]}`.
    `responses` is `{question_key: response_text}` for this submission's non-empty
    answers (mirrors `lead_questionnaire_responses.response_text`).

    Matching is case-insensitive Python substring containment against each
    condition rule's keywords (PHASE-02 Decision D-4: SPEC-0001's "ILIKE" language
    describes matching *semantics*, not a literal SQL query — this runs against data
    already in memory from Stage 2). Deliberately loose: a keyword that is a
    substring of a longer word in the response still counts as a match.

    Only `all_tests` is deduplicated (first-seen order preserved) — a test can
    appear in both `standard` and a matched condition rule's `tests`, but only once
    in `all_tests`. `additions` records one entry per matched rule per response,
    with `triggered_by` set to the first keyword of that rule to match.
    """
    standard_tests: list[str] = list(test_panel.get("standard_tests") or [])
    condition_rules: list[dict] = test_panel.get("condition_rules") or []

    additions: list[dict] = []
    all_tests: list[str] = list(standard_tests)

    for response_text in responses.values():
        if not response_text:
            continue
        response_lower = response_text.lower()
        for rule in condition_rules:
            matched_keyword = next(
                (kw for kw in rule.get("keywords") or [] if kw.lower() in response_lower),
                None,
            )
            if matched_keyword is None:
                continue
            for test in rule.get("tests") or []:
                additions.append({"test": test, "triggered_by": matched_keyword})
                if test not in all_tests:
                    all_tests.append(test)

    return {"standard": standard_tests, "additions": additions, "all_tests": all_tests}


@router.post("/{hc_slug}", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def submit_intake_questionnaire(
    request: Request, hc_slug: str, body: IntakeSubmissionIn, db: DbDep
) -> IntakeSubmissionOut:
    """Public questionnaire submission. No auth — resolved by hc_slug, same 404
    generic-not-found pattern as GET (see docstring above).

    Rate-limited 5 req/hour per direct-connection IP (SPEC-0001 API surface table;
    `src.lib.rate_limit.limiter`, keyed by `get_remote_address` only — no
    X-Forwarded-For trust per PHASE-02 Decision D-1). `request: Request` is required
    by name for slowapi's key function to read the client IP.

    Consent (`consent_given_at` / `consent_purpose`) is written on the same `Lead`
    row that is flushed/committed together with its `LeadQuestionnaireResponse`
    rows in one transaction — required by SPEC-0001's DPDP acceptance criteria.
    """
    config = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_slug == hc_slug)
    )).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # Captured now as a plain local — `db.rollback()` in the except block below
    # expires every ORM-managed object in the session (not just `lead`), so reading
    # `config.hc_user_id` after a rollback would trigger an implicit lazy reload
    # that fails outside the async greenlet context.
    hc_user_id = config.hc_user_id
    test_panel: dict = config.test_panel

    user = await db.get(User, hc_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if body.consent_ack is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Consent acknowledgement is required.",
        )

    questionnaire: list[dict] = config.questionnaire
    responses: dict[str, object] = body.model_extra or {}
    _validate_intake_responses(questionnaire, responses)

    hc_name = f"{user.first_name} {user.last_name}".strip()

    def _answer_text(key: str) -> str | None:
        answer = responses.get(key)
        if _is_empty_answer(answer):
            return None
        return str(answer)

    # Captured as plain locals (not read off `lead` after the fact) because
    # `db.rollback()` in the except block below expires ORM-managed attributes —
    # reading `lead.email`/`lead.id` post-rollback would trigger an implicit lazy
    # reload that fails outside the async greenlet context.
    email_value = _answer_text(_EMAIL_KEY) or ""
    full_name_value = _answer_text(_FULL_NAME_KEY) or ""
    lead_status = "questionnaire_submitted"

    lead = Lead(
        hc_user_id=hc_user_id,
        full_name=full_name_value,
        email=email_value,
        phone=_answer_text(_PHONE_KEY),
        status=lead_status,
        consent_given_at=datetime.now(UTC),
        consent_purpose=_CONSENT_PURPOSE_TEMPLATE.format(hc_name=hc_name),
    )
    db.add(lead)

    # Stage 3 (test recommendation matching) needs each question's response text
    # alongside `lead_id` — built here, inside the same loop that creates the
    # LeadQuestionnaireResponse rows, so it's available after the try/except below
    # without re-reading anything off the (possibly-expired-on-rollback) ORM objects.
    response_texts: dict[str, str] = {}

    try:
        await db.flush()  # assigns lead.id and surfaces a UNIQUE(hc_user_id, email)
        # violation now, before any LeadQuestionnaireResponse rows are added.
        lead_id = lead.id
        for question in questionnaire:
            answer_text = _answer_text(question["key"])
            db.add(LeadQuestionnaireResponse(
                lead_id=lead_id,
                question_key=question["key"],
                question_text=question["text"],
                response_text=answer_text,
            ))
            if answer_text is not None:
                response_texts[question["key"]] = answer_text
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Don't trust the bare IntegrityError to mean "duplicate email" — re-query to
        # confirm the collision is genuinely on uq_leads_hc_user_id_email before
        # returning 409. Mirrors leadgen.py's init_leadgen_config disambiguation.
        existing = (await db.execute(
            select(Lead).where(Lead.hc_user_id == hc_user_id, Lead.email == email_value)
        )).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_DUPLICATE_EMAIL_MESSAGE_TEMPLATE.format(hc_name=hc_name),
            ) from None
        raise

    # ── Stage 3 (SPEC-0001) — lab test recommendation, upload token, email ──────
    # Fires inline, no separate endpoint. A separate transaction from Stage 2's:
    # the Lead + questionnaire responses above are already durably committed: a
    # failure here (or in the email send below) must not undo that real, correctly
    # captured submission.
    recommendation = _build_test_recommendation(test_panel, response_texts)
    lead.test_recommendation = recommendation
    # Reassign the same local the response is built from below (not a new
    # variable) so IntakeSubmissionOut.status reflects the Lead's actual final
    # state, not the pre-Stage-3 "questionnaire_submitted" snapshot.
    lead_status = "tests_recommended"
    lead.status = lead_status

    raw_token = os.urandom(32).hex()
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=_UPLOAD_TOKEN_TTL_DAYS)
    db.add(LeadUploadToken(lead_id=lead_id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    # D-2: email delivery failure must not fail this request — the Lead's
    # submission, recommendation, and upload token are already committed above.
    # Caught broadly and logged, never re-raised.
    try:
        send_lead_test_recommendation_email(
            to=email_value,
            lead_name=full_name_value,
            hc_name=hc_name,
            recommended_tests=recommendation["all_tests"],
            upload_link=f"{get_settings().frontend_url}/upload/{raw_token}",
            expiry_days=_UPLOAD_TOKEN_TTL_DAYS,
        )
    except Exception as exc:
        logger = get_logger(
            request_id=getattr(request.state, "request_id", ""), hc_id=str(hc_user_id)
        )
        logger.error(
            "lead_test_recommendation_email_failed", lead_id=str(lead_id), error=str(exc)
        )

    return IntakeSubmissionOut(lead_id=lead_id, status=lead_status)
