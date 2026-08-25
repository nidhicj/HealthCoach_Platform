"""Public HC intake endpoints (Unit_003 PHASE-02). No auth — resolved by hc_slug.

Security note: responses here are a strict allowlist. Never call `.model_validate()`
(or similar) on the full `HcLeadgenConfig`/`User` objects — build the response model
field-by-field so a future column addition to those tables can't silently leak
through this public endpoint.
"""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.deps import DbDep
from src.config import get_settings
from src.db.models import HcLeadgenConfig, Lead, LeadQuestionnaireResponse, User
from src.lib.email import send_test_recommendation_review_email
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

    # Captured as plain locals for the same reason as `email_value`/
    # `full_name_value` below — `db.commit()`/`db.rollback()` further down
    # expire ORM-managed attributes, and reading `user.email` after that point
    # would trigger an implicit lazy reload that fails outside the async
    # greenlet context.
    hc_name = f"{user.first_name} {user.last_name}".strip()
    hc_email = user.email

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

    # ── Stage 3 (SPEC-0001, PHASE-04) — AI-drafted test recommendation, HC review
    # email. Fires inline, no separate endpoint. A separate transaction from
    # Stage 2's: the Lead + questionnaire responses above are already durably
    # committed — a failure here (AI drafting, or the email send below) must not
    # undo that real, correctly captured submission. `lead_upload_tokens`
    # issuance and the immediate Lead-facing recommendation email that used to
    # fire here (PHASE-02) are gone: PHASE-05 issues the upload token after
    # payment+scheduling instead, and the Lead now only hears from their HC once
    # the HC has reviewed and sent the finalized panel (Stage 3 continued, not
    # built by this endpoint).
    #
    # Local import mirrors this codebase's existing convention for calling into
    # `src.llm_service` from an API module (see `src.api.upload`/`src.api.sessions`
    # call sites for `generate_lead_brief`/`generate_brief`/`generate_mom_draft`).
    from src.llm_service import generate_lead_test_recommendation

    standard_tests: list[str] = list((test_panel or {}).get("standard_tests") or [])

    # `generate_lead_test_recommendation()` is documented and tested to never
    # raise (its whole contract, mirroring PHASE-03's `generate_lead_brief`
    # D-2 contract) — but this call is still wrapped defensively, the same way
    # `src.api.upload`'s call to `generate_lead_brief` is, so that even a
    # contract violation here cannot flip this public, unauthenticated
    # endpoint's response away from "the Lead's submission succeeded", which is
    # already durably true by this point.
    try:
        additions = await generate_lead_test_recommendation(
            db, lead_id=lead_id, hc_user_id=hc_user_id
        )
    except Exception as exc:  # pragma: no cover — defensive only; contract says this never fires
        logger = get_logger(
            request_id=getattr(request.state, "request_id", ""), hc_id=str(hc_user_id)
        )
        logger.error(
            "lead_test_recommendation_generation_unexpected_raise",
            lead_id=str(lead_id),
            error=str(exc),
        )
        additions = None

    # `None` (AI drafting failed, for any reason) falls back to a standard-
    # baseline-only draft — SPEC-0001's documented edge case for this failure
    # mode ("HC review screen falls back to standard-baseline-only"). This is
    # not an error state for the Lead's submission: the HC can still review and
    # send a panel manually.
    if additions is None:
        additions = []
    draft_test_recommendation = {
        "standard": standard_tests,
        "additions": additions,
        "all_tests": standard_tests + [a["test"] for a in additions],
    }
    lead.draft_test_recommendation = draft_test_recommendation
    # Reassign the same local the response is built from below (not a new
    # variable) so IntakeSubmissionOut.status reflects the Lead's actual final
    # state, not the pre-Stage-3 "questionnaire_submitted" snapshot.
    lead_status = "tests_drafted"
    lead.status = lead_status
    await db.commit()

    # Non-blocking, matching this codebase's existing convention for outbound
    # email that must never fail the primary request (see `send_lead_brief_ready_email`
    # / `send_lead_brief_failed_email` call sites in `src.api.upload`, and
    # `send_check_in_reminder_email` in `src.api.check_ins`): the Lead's
    # submission and the AI draft are already durably committed above, so a
    # failure to notify the HC must not turn a successful submission into an
    # error response for the Lead.
    try:
        send_test_recommendation_review_email(
            to=hc_email,
            hc_name=hc_name,
            lead_name=full_name_value,
            review_link=f"{get_settings().frontend_url}/leads/{lead_id}/test-recommendation",
        )
    except Exception as exc:
        logger = get_logger(
            request_id=getattr(request.state, "request_id", ""), hc_id=str(hc_user_id)
        )
        logger.error(
            "test_recommendation_review_email_failed", lead_id=str(lead_id), error=str(exc)
        )

    return IntakeSubmissionOut(lead_id=lead_id, status=lead_status)
