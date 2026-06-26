# PHASE-01: Supplement Recommendations

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Unit**: Unit_002_SupplementRecommendations
**Status**: Draft
**Verification date**: _(fill after verification)_
**Implements**: `Unit_002_SupplementRecommendations/SPEC-0001-supplement-recommendations.md` — all acceptance criteria
**ADRs implemented**: ADR-0001 (stack), ADR-0005 (auth / tenant scoping), ADR-0006 (observability)

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific not provided. Ready?

---

## 1. Scope

Build end-to-end supplement recommendation CRUD for the HC — DB table, four API endpoints, frontend API client, and a new section on the client detail page. Standalone feature; no session linking. Mock supplement catalog hardcoded in frontend.

Not in scope: brand catalog, client-facing view, active/ended visual state, client page layout redesign.

---

## 2. Deliverables shipped

_(Fill in after phase ships)_

---

## 3. Decisions made during this phase

_(Fill in after phase ships)_

---

## 4. Bugs fixed mid-phase

None recorded.

---

## 5. Source docs consulted

- `docs/specs/Unit_002_SupplementRecommendations/SPEC-0001-supplement-recommendations.md` — full spec
- `backend/src/db/models/clients.py` — model pattern reference
- `backend/src/api/diet_charts.py` — nested-under-clients router pattern
- `backend/src/main.py` — router registration pattern
- `backend/tests/integration/test_action_items.py` — integration test pattern
- `frontend/src/lib/api/clients.ts` — Zod schema + fetchWithAuth pattern
- `frontend/src/app/(app)/clients/[clientId]/page.tsx` — client detail page to modify

---

## 6. Verification

- **Verification date**: _(fill after verification)_
- **Test count at end of phase**: _(fill after verification)_
- **Key checks**: _(fill after verification)_

---

## 7. Lessons learned

_(Fill in after phase ships)_

---

## 8. Carry-over to subsequent phases

- `backend/src/db/models/supplements.py` — `SupplementRecommendation` model; downstream phases can FK to this table when brand catalog is added
- `backend/src/api/supplements.py` — router; future brand/catalog endpoints extend here
- `frontend/src/lib/api/supplements.ts` — API client; extend when client-facing view is added

---

## Implementation plan

**Goal:** Add supplement recommendation CRUD — DB → API → frontend section on the client detail page.

**Architecture:** New `supplement_recommendations` table, soft-delete via `archived_at`, four tenant-scoped REST endpoints following the existing `diet_charts.py` pattern, a Zod-typed frontend API client, and an inline-form section inserted in the client detail page left column.

**Tech stack:** Python / FastAPI / SQLAlchemy 2.0 / Alembic / asyncpg (backend); Next.js / TypeScript / Zod / shadcn-ui (frontend).

### Global constraints

- All backend routes require HC JWT — `require_role('hc')` via `HcClaimsDep` + `TenantDep`
- Cross-tenant access → 404, never 403 (platform convention)
- Soft-delete only — `archived_at` timestamp; no physical row deletion via API
- `name` field is required; all others optional
- `duration_days` must be ≥ 1 if supplied (422 otherwise)
- Frontend uses `fetchWithAuth` + Zod parse on every API response
- TDD: write the failing test before the implementation in every backend task
- Activate venv: `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate`

---

### Task 1: DB model + Alembic migration

**Files:**
- Create: `backend/src/db/models/supplements.py`
- Modify: `backend/src/db/models/__init__.py`
- Run: `alembic revision --autogenerate` to generate migration file

**Interfaces:**
- Produces: `SupplementRecommendation` SQLAlchemy model — imported by Task 2's router

---

- [ ] **Step 1: Create the SQLAlchemy model**

Create `backend/src/db/models/supplements.py`:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class SupplementRecommendation(Base):
    __tablename__ = "supplement_recommendations"
    __table_args__ = (
        Index("idx_supplement_rec_hc_client", "hc_user_id", "client_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    dosage: Mapped[str | None] = mapped_column(Text)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    recommended_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
```

- [ ] **Step 2: Export the model from `__init__.py`**

In `backend/src/db/models/__init__.py`, add the import and export:

```python
from src.db.models.supplements import SupplementRecommendation
```

Add `"SupplementRecommendation"` to `__all__`.

- [ ] **Step 3: Generate the Alembic migration**

```bash
cd /mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform/backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
alembic revision --autogenerate -m "add_supplement_recommendations"
```

Expected: a new file appears in `alembic/versions/` with `down_revision = "df7c84b2de4f"`.

- [ ] **Step 4: Inspect the generated migration**

Open the generated file and confirm it contains:
- `op.create_table("supplement_recommendations", ...)` with all columns
- `op.create_index("idx_supplement_rec_hc_client", "supplement_recommendations", ["hc_user_id", "client_id"])`
- A valid `downgrade()` that drops the table and index

If Alembic generated anything unexpected (e.g., missed columns), edit the migration manually to match.

- [ ] **Step 5: Apply the migration**

```bash
alembic upgrade head
```

Expected output ends with: `Running upgrade df7c84b2de4f -> <new_revision>, add_supplement_recommendations`

- [ ] **Step 6: Commit**

```bash
git add backend/src/db/models/supplements.py backend/src/db/models/__init__.py backend/alembic/versions/
git commit -m "feat(db): add supplement_recommendations table and model"
```

---

### Task 2: API router + integration tests (TDD)

**Files:**
- Create: `backend/src/api/supplements.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/integration/test_supplements.py`

**Interfaces:**
- Consumes: `SupplementRecommendation` from `src.db.models.supplements`, `Client` from `src.db.models.clients`, `DbDep`, `HcClaimsDep`, `TenantDep` from `src.api.deps`
- Produces: `GET/POST/PATCH/DELETE /api/clients/{client_id}/supplements[/{id}]`

---

- [ ] **Step 1: Write the integration tests first**

Create `backend/tests/integration/test_supplements.py`:

```python
"""Integration tests for /api/clients/{client_id}/supplements. SPEC-0001 acceptance criteria."""
import uuid
from datetime import datetime, timezone

import pytest


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_client(http_client, headers) -> dict:
    r = await http_client.post(
        "/api/clients", headers=headers, json={"full_name": f"C-{uuid.uuid4().hex[:4]}"}
    )
    assert r.status_code == 201
    return r.json()


async def _make_supplement(http_client, headers, client_id: str, **overrides) -> dict:
    payload = {
        "name": "Vitamin D3",
        "dosage": "2000 IU daily",
        "duration_days": 30,
        "notes": "for gut health",
    } | overrides
    r = await http_client.post(
        f"/api/clients/{client_id}/supplements", headers=headers, json=payload
    )
    assert r.status_code == 201, r.text
    return r.json()


# ── POST ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_supplement_returns_201(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc_headers,
        json={"name": "Omega-3 / Fish Oil", "dosage": "1g daily", "duration_days": 60},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Omega-3 / Fish Oil"
    assert body["dosage"] == "1g daily"
    assert body["duration_days"] == 60
    assert body["notes"] is None
    assert "id" in body
    assert "recommended_at" in body


@pytest.mark.asyncio
async def test_create_supplement_missing_name_returns_422(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc_headers,
        json={"dosage": "1g daily"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_supplement_invalid_duration_returns_422(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc_headers,
        json={"name": "Zinc", "duration_days": 0},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_supplement_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.post(
        f"/api/clients/{client['id']}/supplements",
        headers=hc2_headers,
        json={"name": "Zinc"},
    )
    assert r.status_code == 404


# ── GET ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_supplements_returns_newest_first(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    await _make_supplement(http_client, hc_headers, client["id"], name="Iron")
    await _make_supplement(http_client, hc_headers, client["id"], name="Zinc")

    r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc_headers
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert items[0]["name"] == "Zinc"   # newest first
    assert items[1]["name"] == "Iron"


@pytest.mark.asyncio
async def test_list_supplements_excludes_archived(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc_headers
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_supplements_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc2_headers
    )
    assert r.status_code == 404


# ── PATCH ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_supplement_updates_fields(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.patch(
        f"/api/clients/{client['id']}/supplements/{s['id']}",
        headers=hc_headers,
        json={"dosage": "4000 IU daily", "duration_days": 60},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dosage"] == "4000 IU daily"
    assert body["duration_days"] == 60
    assert body["name"] == s["name"]   # unchanged


@pytest.mark.asyncio
async def test_patch_archived_supplement_returns_404(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    r = await http_client.patch(
        f"/api/clients/{client['id']}/supplements/{s['id']}",
        headers=hc_headers,
        json={"dosage": "new"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_supplement_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.patch(
        f"/api/clients/{client['id']}/supplements/{s['id']}",
        headers=hc2_headers,
        json={"dosage": "new"},
    )
    assert r.status_code == 404


# ── DELETE ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_supplement_returns_204_and_soft_deletes(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    assert r.status_code == 204
    # Must no longer appear in list
    list_r = await http_client.get(
        f"/api/clients/{client['id']}/supplements", headers=hc_headers
    )
    assert list_r.json() == []


@pytest.mark.asyncio
async def test_delete_already_archived_returns_404(http_client, hc_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    r = await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_supplement_cross_tenant_returns_404(http_client, hc_headers, hc2_headers):
    client = await _make_client(http_client, hc_headers)
    s = await _make_supplement(http_client, hc_headers, client["id"])
    r = await http_client.delete(
        f"/api/clients/{client['id']}/supplements/{s['id']}", headers=hc2_headers
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run the tests — confirm they all fail with import errors**

```bash
cd /mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform/backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
pytest tests/integration/test_supplements.py -v 2>&1 | head -30
```

Expected: all tests fail with `404` or `ImportError` — the router doesn't exist yet.

- [ ] **Step 3: Write the API router**

Create `backend/src/api/supplements.py`:

```python
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
    if body.name is not None:
        rec.name = body.name
    if body.dosage is not None:
        rec.dosage = body.dosage
    if body.duration_days is not None:
        rec.duration_days = body.duration_days
    if body.recommended_at is not None:
        rec.recommended_at = body.recommended_at
    if body.notes is not None:
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
```

- [ ] **Step 4: Register the router in `main.py`**

Add to `backend/src/main.py`:

```python
from src.api.supplements import router as supplements_router
```

And in the `include_router` block:

```python
app.include_router(supplements_router)
```

- [ ] **Step 5: Run the tests — all should pass**

```bash
pytest tests/integration/test_supplements.py -v
```

Expected: all tests pass. If any fail, fix before continuing.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: no regressions. All pre-existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/src/api/supplements.py backend/src/main.py backend/tests/integration/test_supplements.py
git commit -m "feat(api): add supplement recommendations CRUD endpoints"
```

---

### Task 3: Frontend API client

**Files:**
- Create: `frontend/src/lib/api/supplements.ts`

**Interfaces:**
- Consumes: `fetchWithAuth` from `@/lib/auth/client`, `API_URL` from `@/lib/config`
- Produces: `SupplementOut` type and `listSupplements`, `createSupplement`, `patchSupplement`, `deleteSupplement` — consumed by Task 4

---

- [ ] **Step 1: Create `frontend/src/lib/api/supplements.ts`**

```typescript
import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const SupplementOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  dosage: z.string().nullable(),
  duration_days: z.number().nullable(),
  recommended_at: z.string(),
  notes: z.string().nullable(),
  created_at: z.string(),
});

export type SupplementOut = z.infer<typeof SupplementOutSchema>;

export interface SupplementCreateInput {
  name: string;
  dosage?: string | null;
  duration_days?: number | null;
  recommended_at?: string;
  notes?: string | null;
}

export interface SupplementPatchInput {
  name?: string;
  dosage?: string | null;
  duration_days?: number | null;
  recommended_at?: string;
  notes?: string | null;
}

// ── API calls ────────────────────────────────────────────────────────────────

export async function listSupplements(clientId: string): Promise<SupplementOut[]> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/supplements`);
  if (!res.ok) throw new Error("Failed to fetch supplements");
  return z.array(SupplementOutSchema).parse(await res.json());
}

export async function createSupplement(
  clientId: string,
  data: SupplementCreateInput,
): Promise<SupplementOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/supplements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create supplement");
  return SupplementOutSchema.parse(await res.json());
}

export async function patchSupplement(
  clientId: string,
  supplementId: string,
  data: SupplementPatchInput,
): Promise<SupplementOut> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/supplements/${supplementId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) throw new Error("Failed to update supplement");
  return SupplementOutSchema.parse(await res.json());
}

export async function deleteSupplement(
  clientId: string,
  supplementId: string,
): Promise<void> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/supplements/${supplementId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error("Failed to delete supplement");
}
```

- [ ] **Step 2: Type-check**

```bash
cd /mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform/frontend
npm run type-check 2>&1 | tail -20
```

Expected: no errors in `supplements.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api/supplements.ts
git commit -m "feat(frontend): add supplements API client"
```

---

### Task 4: Frontend UI — supplements section on client detail page

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx`

**Interfaces:**
- Consumes: `listSupplements`, `createSupplement`, `patchSupplement`, `deleteSupplement`, `SupplementOut` from `@/lib/api/supplements` (Task 3)

---

- [ ] **Step 1: Add imports and constants at the top of `page.tsx`**

Add to the import block:

```typescript
import {
  listSupplements,
  createSupplement,
  patchSupplement,
  deleteSupplement,
  type SupplementOut,
} from "@/lib/api/supplements";
```

Add the mock catalog constant (before the component function):

```typescript
const SUPPLEMENT_CATALOG = [
  "Vitamin D3", "Vitamin B12", "Vitamin C", "Omega-3 / Fish Oil",
  "Magnesium", "Iron", "Zinc", "Calcium", "Ashwagandha",
  "Curcumin / Turmeric", "Probiotics", "Whey Protein", "Plant Protein",
  "Multivitamin", "Collagen", "Biotin", "CoQ10", "Melatonin",
];
```

- [ ] **Step 2: Add supplements state inside the component**

Inside `ClientDetailPage`, after the existing state declarations, add:

```typescript
const [supplements, setSupplements] = useState<SupplementOut[] | null>(null);
const [suppLoadError, setSuppLoadError] = useState(false);
const [showSuppForm, setShowSuppForm] = useState(false);
const [editingSuppId, setEditingSuppId] = useState<string | null>(null);
const [suppForm, setSuppForm] = useState({
  name: "",
  dosage: "",
  duration_days: "",
  recommended_at: new Date().toISOString().slice(0, 10),
  notes: "",
});
const [suppSaving, setSuppSaving] = useState(false);
const [suppFormError, setSuppFormError] = useState<string | null>(null);
```

- [ ] **Step 3: Add `listSupplements` to the parallel fetch in `useEffect`**

In the existing `useEffect`, add `listSupplements(clientId)` to the `Promise.all` array:

```typescript
Promise.all([
  getClient(clientId),
  getClientAst(clientId),
  listSessions({ client_id: clientId, limit: 20 }),
  listActionItems({ client_id: clientId, status: "completed", limit: 50 }),
  getClientDietChart(clientId),
  listSupplements(clientId),
])
  .then(([c, a, s, closed, dc, supps]) => {
    setClient(c);
    setAst(a);
    setSessions(s.items);
    setClosedItems(closed.items);
    setDietChart(dc);
    setSupplements(supps);
  })
  .catch(() => {
    setLoadError(true);
    setSuppLoadError(true);
  });
```

- [ ] **Step 4: Add supplement form handler functions**

Add these handlers inside the component, before the `return` statement:

```typescript
function openAddForm() {
  setEditingSuppId(null);
  setSuppForm({
    name: "",
    dosage: "",
    duration_days: "",
    recommended_at: new Date().toISOString().slice(0, 10),
    notes: "",
  });
  setSuppFormError(null);
  setShowSuppForm(true);
}

function openEditForm(s: SupplementOut) {
  setEditingSuppId(s.id);
  setSuppForm({
    name: s.name,
    dosage: s.dosage ?? "",
    duration_days: s.duration_days?.toString() ?? "",
    recommended_at: s.recommended_at.slice(0, 10),
    notes: s.notes ?? "",
  });
  setSuppFormError(null);
  setShowSuppForm(true);
}

function closeSuppForm() {
  setShowSuppForm(false);
  setEditingSuppId(null);
  setSuppFormError(null);
}

async function handleSuppSave() {
  if (!suppForm.name.trim()) {
    setSuppFormError("Supplement name is required.");
    return;
  }
  setSuppSaving(true);
  setSuppFormError(null);
  const payload = {
    name: suppForm.name.trim(),
    dosage: suppForm.dosage.trim() || null,
    duration_days: suppForm.duration_days ? parseInt(suppForm.duration_days, 10) : null,
    recommended_at: suppForm.recommended_at
      ? new Date(suppForm.recommended_at).toISOString()
      : undefined,
    notes: suppForm.notes.trim() || null,
  };
  try {
    if (editingSuppId) {
      const updated = await patchSupplement(clientId, editingSuppId, payload);
      setSupplements((prev) =>
        prev ? prev.map((s) => (s.id === editingSuppId ? updated : s)) : prev
      );
    } else {
      const created = await createSupplement(clientId, payload);
      setSupplements((prev) => (prev ? [created, ...prev] : [created]));
    }
    closeSuppForm();
  } catch {
    setSuppFormError("Could not save. Please try again.");
  } finally {
    setSuppSaving(false);
  }
}

async function handleSuppDelete(id: string) {
  if (!confirm("Remove this supplement entry?")) return;
  try {
    await deleteSupplement(clientId, id);
    setSupplements((prev) => (prev ? prev.filter((s) => s.id !== id) : prev));
    closeSuppForm();
  } catch {
    setSuppFormError("Could not remove. Please try again.");
  }
}
```

- [ ] **Step 5: Add the supplements section to the JSX**

In the JSX, locate the closing `</section>` of the "Closed action items" section and the opening `<section>` of the "Sessions" section. Insert the supplements section between them:

```tsx
{/* Supplement recommendations */}
<section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
  <div className="flex items-center justify-between">
    <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
      Supplement recommendations
    </h2>
    {!showSuppForm && (
      <button
        type="button"
        onClick={openAddForm}
        className="font-sans text-xs text-primary underline-offset-4 hover:underline"
      >
        + Add
      </button>
    )}
  </div>
  <Separator />

  {/* Inline form */}
  {showSuppForm && (
    <div className="space-y-3 rounded-xl border border-border bg-background p-4">
      <div className="space-y-1">
        <label className="font-sans text-xs text-muted-foreground">
          Name <span className="text-destructive">*</span>
        </label>
        <input
          list="supplement-catalog"
          value={suppForm.name}
          onChange={(e) => setSuppForm((f) => ({ ...f, name: e.target.value }))}
          placeholder="Type or select a supplement"
          className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
        />
        <datalist id="supplement-catalog">
          {SUPPLEMENT_CATALOG.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="font-sans text-xs text-muted-foreground">Dosage</label>
          <input
            value={suppForm.dosage}
            onChange={(e) => setSuppForm((f) => ({ ...f, dosage: e.target.value }))}
            placeholder="e.g. 2000 IU daily"
            className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="space-y-1">
          <label className="font-sans text-xs text-muted-foreground">Duration (days)</label>
          <input
            type="number"
            min={1}
            value={suppForm.duration_days}
            onChange={(e) => setSuppForm((f) => ({ ...f, duration_days: e.target.value }))}
            placeholder="e.g. 30"
            className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="font-sans text-xs text-muted-foreground">Date recommended</label>
        <input
          type="date"
          value={suppForm.recommended_at}
          onChange={(e) => setSuppForm((f) => ({ ...f, recommended_at: e.target.value }))}
          className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      <div className="space-y-1">
        <label className="font-sans text-xs text-muted-foreground">Notes (optional)</label>
        <textarea
          value={suppForm.notes}
          onChange={(e) => setSuppForm((f) => ({ ...f, notes: e.target.value }))}
          placeholder="Reason or context"
          rows={2}
          className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {suppFormError && (
        <p className="font-sans text-xs text-destructive">{suppFormError}</p>
      )}

      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSuppSave}
            disabled={suppSaving}
            className="rounded-md bg-primary px-3 py-1.5 font-sans text-xs font-bold text-primary-foreground disabled:opacity-50"
          >
            {suppSaving ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={closeSuppForm}
            className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            Cancel
          </button>
        </div>
        {editingSuppId && (
          <button
            type="button"
            onClick={() => handleSuppDelete(editingSuppId)}
            className="font-sans text-xs text-destructive underline-offset-4 hover:underline"
          >
            Remove
          </button>
        )}
      </div>
    </div>
  )}

  {/* List */}
  {supplements === null ? (
    <div className="space-y-2">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  ) : suppLoadError ? (
    <p className="font-sans text-sm text-destructive">Could not load supplements.</p>
  ) : supplements.length === 0 && !showSuppForm ? (
    <p className="font-sans text-sm italic text-muted-foreground">
      No supplements logged yet.
    </p>
  ) : (
    <ul className="divide-y divide-border">
      {supplements.map((s) => (
        <li key={s.id} className="py-3">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-0.5">
              <p className="font-sans text-sm text-foreground">{s.name}</p>
              <p className="font-sans text-xs text-muted-foreground">
                {[
                  s.dosage,
                  s.duration_days ? `${s.duration_days} days` : null,
                  new Date(s.recommended_at).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  }),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {s.notes && (
                <p className="font-sans text-xs italic text-muted-foreground">{s.notes}</p>
              )}
            </div>
            <button
              type="button"
              onClick={() => openEditForm(s)}
              className="shrink-0 font-sans text-xs text-primary underline-offset-4 hover:underline"
            >
              Edit
            </button>
          </div>
        </li>
      ))}
    </ul>
  )}
</section>
```

- [ ] **Step 6: Type-check**

```bash
cd /mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform/frontend
npm run type-check 2>&1 | tail -20
```

Expected: no errors.

- [ ] **Step 7: Run the app and manually verify**

Start the dev stack (use your usual dev command — refer to `README.md` if unsure). Open a client detail page and confirm:

- [ ] Supplements section appears between Closed action items and Sessions
- [ ] "+ Add" expands the inline form
- [ ] Typing in the Name field shows the catalog dropdown; custom text is accepted
- [ ] Saving a new entry adds it to the top of the list and collapses the form
- [ ] Clicking Edit pre-fills the form with that entry's data
- [ ] Saving after edit updates the entry in place
- [ ] Clicking Remove (inside edit form) removes the entry after confirmation
- [ ] Empty state shows "No supplements logged yet." when no entries exist
- [ ] Skeleton rows show while loading

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/\(app\)/clients/\[clientId\]/page.tsx
git commit -m "feat(frontend): add supplement recommendations section to client detail page"
```

---

### Self-review checklist (implementer runs before marking phase complete)

- [ ] All 14 acceptance criteria in `SPEC-0001` are checked off
- [ ] `pytest tests/integration/test_supplements.py -v` — all pass
- [ ] `pytest tests/ -v` — no regressions
- [ ] `npm run type-check` — no errors
- [ ] Manual smoke test on a real client page passes (Step 7 above)
- [ ] No hardcoded IDs, secrets, or absolute paths introduced
- [ ] `archived_at` is set on delete; no physical rows removed
