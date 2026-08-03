"""HC-facing /api/settings/* endpoints — the authenticated HC's own profile.

Deliberately not /api/me/* — that namespace is the client actor's (ADR-0005 §8,
src/api/me.py) and the client-facing frontend route prefix (Unit_004 D-31).
"""
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from src.api.deps import DbDep, HcClaimsDep
from src.db.models.users import User

router = APIRouter(tags=["settings"])


# ── schemas ────────────────────────────────────────────────────────────────────


class SettingsProfileOut(BaseModel):
    business_name: str | None
    display_name: str | None
    photo_url: str | None
    email: str

    model_config = {"from_attributes": True}


class SettingsProfilePatch(BaseModel):
    business_name: str | None = Field(max_length=200)

    @field_validator("business_name")
    @classmethod
    def _normalize_empty(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            return None
        return v


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/api/settings/profile")
async def get_profile(claims: HcClaimsDep, db: DbDep) -> SettingsProfileOut:
    user = await db.get(User, UUID(claims.sub))
    return SettingsProfileOut.model_validate(user)


@router.patch("/api/settings/profile")
async def patch_profile(body: SettingsProfilePatch, claims: HcClaimsDep, db: DbDep) -> SettingsProfileOut:
    user = await db.get(User, UUID(claims.sub))
    user.business_name = body.business_name
    await db.commit()
    await db.refresh(user)
    return SettingsProfileOut.model_validate(user)
