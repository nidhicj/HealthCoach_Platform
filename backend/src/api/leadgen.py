"""HC leadgen setup endpoints (Unit_003 Stage 1). All routes scoped to JWT hc_id (tenant)."""
import random
import re
import string
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models import HcLeadgenConfig, User

router = APIRouter(prefix="/api/leadgen", tags=["leadgen"])

_FIXED_QUESTIONS = [
    {"key": "full_name", "text": "Full name", "type": "free_text", "required": True, "removable": False},
    {"key": "age", "text": "Age", "type": "free_text", "required": True, "removable": False},
    {"key": "email", "text": "Email", "type": "free_text", "required": True, "removable": False},
    {"key": "phone", "text": "Phone", "type": "free_text", "required": True, "removable": False},
    {"key": "primary_health_goal", "text": "What is your primary health goal?", "type": "free_text", "required": True, "removable": False},
    {"key": "current_health_concerns", "text": "Any current health concerns?", "type": "free_text", "required": True, "removable": False},
]
_SLUG_SUFFIX_CHARS = string.ascii_lowercase + string.digits
_MAX_SLUG_ATTEMPTS = 5


def _slugify_name_part(name: str) -> str:
    cleaned = re.sub(r"[^a-z]", "", name.lower())
    return cleaned or "hc"  # fallback for names with no ASCII letters — edge case, documented in D-2 of the plan


def _generate_slug(first_name: str, last_name: str) -> str:
    suffix = "".join(random.choices(_SLUG_SUFFIX_CHARS, k=5))
    return f"{_slugify_name_part(first_name)}-{_slugify_name_part(last_name)}-{suffix}"


def _already_configured_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "already_configured", "message": "Leadgen is already set up for this account."},
    )


class LeadgenConfigOut(BaseModel):
    hc_slug: str
    questionnaire: list[dict]
    test_panel: dict
    consultation_fee_inr: int | None
    consultation_duration_min: int
    scheduling_link: str | None
    notification_delivery: str
    lead_expiry_days: int

    model_config = {"from_attributes": True}


class LeadgenConfigStatusOut(BaseModel):
    configured: bool
    hc_slug: str | None = None
    questionnaire: list[dict] | None = None
    test_panel: dict | None = None
    consultation_fee_inr: int | None = None
    consultation_duration_min: int | None = None
    scheduling_link: str | None = None
    notification_delivery: str | None = None
    lead_expiry_days: int | None = None


@router.post("/config/init", status_code=status.HTTP_201_CREATED)
async def init_leadgen_config(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> LeadgenConfigOut:
    user = await db.get(User, UUID(hc_id))
    if user is None or not user.first_name or not user.last_name:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "profile_incomplete",
                "message": "Complete your profile (first and last name) before setting up lead generation.",
                "redirect": "/settings/profile",
            },
        )

    existing = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if existing is not None:
        raise _already_configured_error()

    for attempt in range(_MAX_SLUG_ATTEMPTS):
        config = HcLeadgenConfig(
            hc_user_id=UUID(hc_id),
            hc_slug=_generate_slug(user.first_name, user.last_name),
            questionnaire=list(_FIXED_QUESTIONS),
        )
        db.add(config)
        try:
            await db.flush()
            await db.commit()
            return LeadgenConfigOut.model_validate(config)
        except IntegrityError:
            await db.rollback()
            # IntegrityError here means either the hc_slug was already taken (retry with
            # a new slug) or a concurrent request won the race on hc_user_id's unique
            # constraint (the pre-check above ran before that request committed). We
            # can't reliably tell which from the exception itself without parsing the
            # DB-specific constraint name, which is fragile. Re-query by hc_user_id —
            # the same check already used above — to disambiguate.
            raced = (await db.execute(
                select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == UUID(hc_id))
            )).scalar_one_or_none()
            if raced is not None:
                raise _already_configured_error()
            if attempt == _MAX_SLUG_ATTEMPTS - 1:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate a unique slug")
    raise AssertionError("unreachable")  # loop always returns or raises


@router.get("/config")
async def get_leadgen_config(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> LeadgenConfigStatusOut:
    config = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if config is None:
        return LeadgenConfigStatusOut(configured=False)
    return LeadgenConfigStatusOut(configured=True, **LeadgenConfigOut.model_validate(config).model_dump())


class Question(BaseModel):
    key: str
    text: str
    type: Literal["free_text", "multiple_choice", "scale"]
    required: bool
    removable: bool
    options: list[str] | None = None


class LeadgenConfigPatch(BaseModel):
    hc_slug: str | None = None  # accepted but always ignored — read-only, see spec Non-goals
    questionnaire: list[Question] | None = None
    test_panel: dict | None = None
    consultation_fee_inr: int | None = None
    consultation_duration_min: int | None = None
    scheduling_link: str | None = None
    notification_delivery: str | None = None
    lead_expiry_days: int | None = None


# Fields backed by NOT NULL columns on hc_leadgen_config. LeadgenConfigPatch types these
# as `X | None = None` so exclude_unset=True can distinguish "omitted" from "sent" —
# but that means an explicit `null` in the request body would otherwise reach the DB.
# For the scalar columns (consultation_duration_min, notification_delivery,
# lead_expiry_days) that would raise a NOT NULL violation (raw 500) — see PHASE-01
# final-review I-2. For the JSONB columns (questionnaire, test_panel) it's worse:
# SQLAlchemy's JSONB defaults to none_as_null=False, so a Python None is written as
# the JSON literal `null`, which satisfies the SQL NOT NULL constraint — the write
# commits, and the row is left permanently corrupted (every subsequent GET/PATCH on
# that HC's config 500s in LeadgenConfigOut.model_validate, with no API-level
# recovery path). See PHASE-01 final-review N-1.
_NOT_NULL_PATCH_FIELDS = (
    "consultation_duration_min",
    "notification_delivery",
    "lead_expiry_days",
    "questionnaire",
    "test_panel",
)


def _validate_no_null_for_not_null_fields(update_data: dict) -> None:
    nulled = sorted(f for f in _NOT_NULL_PATCH_FIELDS if f in update_data and update_data[f] is None)
    if nulled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Field(s) cannot be null: {nulled}",
        )


def _validate_questionnaire_keeps_fixed_questions(new_list: list[dict]) -> None:
    fixed_by_key = {q["key"]: q for q in _FIXED_QUESTIONS}
    new_keys = {q.get("key") for q in new_list}
    missing = set(fixed_by_key) - new_keys
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot remove fixed questions: {sorted(missing)}",
        )
    for q in new_list:
        key = q.get("key")
        fixed = fixed_by_key.get(key)
        if fixed is None:
            continue  # custom question — not subject to fixed-question invariants
        if q.get("removable", False):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Fixed question '{key}' cannot be marked removable")
        # D-2: fixed questions are frozen as free_text/required — PHASE-02's render path
        # depends on this invariant holding, not just on the key being present.
        for field in ("type", "required", "text"):
            if q.get(field) != fixed[field]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Fixed question '{key}' field '{field}' cannot be changed",
                )


@router.patch("/config")
async def patch_leadgen_config(
    body: LeadgenConfigPatch,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> LeadgenConfigOut:
    config = (await db.execute(
        select(HcLeadgenConfig).where(HcLeadgenConfig.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leadgen not configured yet")

    update_data = body.model_dump(exclude_unset=True, exclude={"hc_slug"})
    _validate_no_null_for_not_null_fields(update_data)
    if "questionnaire" in update_data and update_data["questionnaire"] is not None:
        _validate_questionnaire_keeps_fixed_questions(update_data["questionnaire"])
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    return LeadgenConfigOut.model_validate(config)
