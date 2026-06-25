"""Supplement recommendation endpoints — HC-facing CRUD, tenant-scoped."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models.clients import Client
from src.db.models.supplements import SupplementRecommendation

router = APIRouter(tags=["supplements"])


# ── schemas ────────────────────────────────────────────────────────────────────


class SupplementCreate(BaseModel):
    name: str
    dosage: str | None = None
    duration_days: int | None = None
    recommended_at: datetime | None = None
    notes: str | None = None

    @field_validator("duration_days")
    @classmethod
    def _validate_duration(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("duration_days must be at least 1")
        return v


class SupplementPatch(BaseModel):
    name: str | None = None
    dosage: str | None = None
    duration_days: int | None = None
    recommended_at: datetime | None = None
    notes: str | None = None

    @field_validator("duration_days")
    @classmethod
    def _validate_duration(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("duration_days must be at least 1")
        return v


class SupplementOut(BaseModel):
    id: UUID
    name: str
    dosage: str | None
    duration_days: int | None
    recommended_at: datetime
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── shared helper ──────────────────────────────────────────────────────────────


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    row = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return row


async def _get_owned_supplement(
    db: DbDep, client_id: UUID, supplement_id: UUID, hc_id: str
) -> SupplementRecommendation:
    row = (await db.execute(
        select(SupplementRecommendation).where(
            SupplementRecommendation.id == supplement_id,
            SupplementRecommendation.client_id == client_id,
            SupplementRecommendation.hc_user_id == UUID(hc_id),
            SupplementRecommendation.archived_at.is_(None),
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Supplement recommendation not found")
    return row


# ── routes ─────────────────────────────────────────────────────────────────────


@router.post(
    "/api/clients/{client_id}/supplements",
    status_code=status.HTTP_201_CREATED,
)
async def create_supplement(
    client_id: UUID,
    body: SupplementCreate,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> SupplementOut:
    await _get_owned_client(db, client_id, hc_id)
    rec = SupplementRecommendation(
        hc_user_id=UUID(hc_id),
        client_id=client_id,
        name=body.name,
        dosage=body.dosage,
        duration_days=body.duration_days,
        recommended_at=body.recommended_at or datetime.now(timezone.utc),
        notes=body.notes,
    )
    db.add(rec)
    await db.flush()
    await db.commit()
    return SupplementOut.model_validate(rec)


@router.get("/api/clients/{client_id}/supplements")
async def list_supplements(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> list[SupplementOut]:
    await _get_owned_client(db, client_id, hc_id)
    rows = (await db.execute(
        select(SupplementRecommendation)
        .where(
            SupplementRecommendation.client_id == client_id,
            SupplementRecommendation.hc_user_id == UUID(hc_id),
            SupplementRecommendation.archived_at.is_(None),
        )
        .order_by(SupplementRecommendation.recommended_at.desc())
    )).scalars().all()
    return [SupplementOut.model_validate(r) for r in rows]


@router.patch("/api/clients/{client_id}/supplements/{supplement_id}")
async def patch_supplement(
    client_id: UUID,
    supplement_id: UUID,
    body: SupplementPatch,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> SupplementOut:
    rec = await _get_owned_supplement(db, client_id, supplement_id, hc_id)
    if "name" in body.model_fields_set and body.name is not None:
        rec.name = body.name
    if "dosage" in body.model_fields_set:
        rec.dosage = body.dosage
    if "duration_days" in body.model_fields_set:
        rec.duration_days = body.duration_days
    if "recommended_at" in body.model_fields_set and body.recommended_at is not None:
        rec.recommended_at = body.recommended_at
    if "notes" in body.model_fields_set:
        rec.notes = body.notes
    await db.flush()
    await db.commit()
    return SupplementOut.model_validate(rec)


@router.delete(
    "/api/clients/{client_id}/supplements/{supplement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_supplement(
    client_id: UUID,
    supplement_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> None:
    rec = await _get_owned_supplement(db, client_id, supplement_id, hc_id)
    rec.archived_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
