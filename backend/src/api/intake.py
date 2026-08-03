"""Public HC intake endpoints (Unit_003 PHASE-02). No auth — resolved by hc_slug.

Security note: responses here are a strict allowlist. Never call `.model_validate()`
(or similar) on the full `HcLeadgenConfig`/`User` objects — build the response model
field-by-field so a future column addition to those tables can't silently leak
through this public endpoint.
"""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.deps import DbDep
from src.db.models import HcLeadgenConfig, Lead, LeadQuestionnaireResponse, User

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
async def submit_intake_questionnaire(
    hc_slug: str, body: IntakeSubmissionIn, db: DbDep
) -> IntakeSubmissionOut:
    """Public questionnaire submission. No auth — resolved by hc_slug, same 404
    generic-not-found pattern as GET (see docstring above).

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
    lead_status = "questionnaire_submitted"

    lead = Lead(
        hc_user_id=hc_user_id,
        full_name=_answer_text(_FULL_NAME_KEY) or "",
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
            db.add(LeadQuestionnaireResponse(
                lead_id=lead_id,
                question_key=question["key"],
                question_text=question["text"],
                response_text=_answer_text(question["key"]),
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

    return IntakeSubmissionOut(lead_id=lead_id, status=lead_status)
