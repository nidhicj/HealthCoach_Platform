"""Public HC intake endpoints (Unit_003 PHASE-02). No auth — resolved by hc_slug.

Security note: responses here are a strict allowlist. Never call `.model_validate()`
(or similar) on the full `HcLeadgenConfig`/`User` objects — build the response model
field-by-field so a future column addition to those tables can't silently leak
through this public endpoint.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import DbDep
from src.db.models import HcLeadgenConfig, User

router = APIRouter(prefix="/api/intake", tags=["intake"])


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
