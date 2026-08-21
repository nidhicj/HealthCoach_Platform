"""HC-facing /api/settings/* endpoints — the authenticated HC's own profile.

Deliberately not /api/me/* — that namespace is the client actor's (ADR-0005 §8,
src/api/me.py) and the client-facing frontend route prefix (Unit_004 D-31).
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.api.deps import DbDep, HcClaimsDep
from src.db.models.users import User

router = APIRouter(tags=["settings"])


# ── schemas ────────────────────────────────────────────────────────────────────


class SettingsProfileOut(BaseModel):
    business_name: str | None
    first_name: str | None
    last_name: str | None
    display_name: str | None
    photo_url: str | None
    email: str

    model_config = {"from_attributes": True}


class SettingsProfilePatch(BaseModel):
    business_name: str | None = Field(default=None, max_length=200)
    first_name: str | None = Field(default=None, max_length=200)
    last_name: str | None = Field(default=None, max_length=200)

    @field_validator("business_name")
    @classmethod
    def _normalize_empty(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None

    @field_validator("first_name", "last_name")
    @classmethod
    def _reject_empty(cls, v: str | None) -> str | None:
        # Unlike business_name, first_name/last_name are "required once set" and
        # cannot be cleared back to null via this endpoint — so an explicit empty
        # string, whitespace-only string, or explicit JSON null (as opposed to the
        # field being omitted from the body entirely, which never reaches this
        # validator) is rejected rather than silently normalized.
        if v is None:
            raise ValueError("must not be null — this field cannot be cleared via this endpoint")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("must not be empty or whitespace-only")
        return trimmed


# ── routes ─────────────────────────────────────────────────────────────────────


@router.get("/api/settings/profile")
async def get_profile(claims: HcClaimsDep, db: DbDep) -> SettingsProfileOut:
    # require_role only decodes/validates the JWT — it never touches the DB —
    # so the user row may be missing (e.g. deleted account) even with a valid token.
    # Guarded here for defense-in-depth; also matters once PHASE-02 adds account deletion.
    user = await db.get(User, UUID(claims.sub))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return SettingsProfileOut.model_validate(user)


@router.patch("/api/settings/profile")
async def patch_profile(body: SettingsProfilePatch, claims: HcClaimsDep, db: DbDep) -> SettingsProfileOut:
    # See get_profile above: require_role doesn't validate against the DB, so guard here too.
    user = await db.get(User, UUID(claims.sub))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if "business_name" in body.model_fields_set:
        user.business_name = body.business_name
    if "first_name" in body.model_fields_set:
        user.first_name = body.first_name
    if "last_name" in body.model_fields_set:
        user.last_name = body.last_name
    await db.commit()
    await db.refresh(user)
    return SettingsProfileOut.model_validate(user)
