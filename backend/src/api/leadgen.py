"""HC leadgen setup endpoints (Unit_003 Stage 1). All routes scoped to JWT hc_id (tenant)."""
import random
import re
import string
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "already_configured", "message": "Leadgen is already set up for this account."},
        )

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
            if attempt == _MAX_SLUG_ATTEMPTS - 1:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate a unique slug")
    raise AssertionError("unreachable")  # loop always returns or raises
