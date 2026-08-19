# PHASE-01 — Leadgen Data Layer & HC Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Unit**: Unit_003_ClientDiscoveryPipeline
**Implements**: `SPEC-0001-client-discovery-pipeline.md` Stage 1 (HC one-time setup), Data §New tables (all 5), Acceptance criteria §Setup
**Depends on**: `Unit_006_PlatformFoundations` PHASE-01 (HC Settings & Profile) — worked around temporarily in Task 1; see Global Constraints and Decisions Log.

**Goal:** Stand up the full Unit_003 data layer (`leads`, `lead_questionnaire_responses`, `lead_upload_tokens`, `lead_files`, `hc_leadgen_config`) and implement Stage 1 — the HC's one-time leadgen setup flow (`/settings/leadgen`): slug generation, questionnaire/test-panel/settings configuration. Nothing public-facing yet — that's PHASE-02.

**Architecture:** Five new tables in one migration, following the existing per-domain model-file split (`backend/src/db/models/leadgen.py`, mirroring `clients.py`/`auth.py`). Three new HC-authenticated endpoints (`POST /api/leadgen/config/init`, `GET /api/leadgen/config`, `PATCH /api/leadgen/config`) under `backend/src/api/leadgen.py`, following the exact `require_role('hc')` + `current_tenant()` + tenant-scoped-404 pattern already used in `backend/src/api/clients.py`. One new frontend page (`/settings/leadgen`) using the existing `Tabs` component (three tabs: Setup, Intake Form, Test Panel) and a new `frontend/src/lib/api/leadgen.ts` API module, mirroring `frontend/src/lib/api/clients.ts`.

**Tech Stack:** Same as the rest of the repo — FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, Next.js/TypeScript, Zod. No new backend dependencies for this phase (`slowapi` is needed starting PHASE-02, not here — PHASE-01 has no public/unauthenticated endpoints).

---

## Global Constraints

- Python ≥ 3.12, FastAPI, SQLAlchemy ≥ 2.0 (async), Pydantic ≥ 2.7 — same floors as the rest of the repo.
- Activate the Python env before any backend command: `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate`
- **This worktree's Postgres runs on port 5436, not 5432** (`docker-compose.yml`: compose project `tapas_unit003`, container `tapas_unit003-postgres-1`). Before running any DB command, run `scripts/db-check.sh` from repo root to confirm the container is up and `.env` points at the right port. Never hardcode `5432` in any command in this plan.
- Tests hit the real `tapas_test` Postgres DB (`backend/tests/integration/conftest.py`) — no mocking the DB.
- After generating each migration, run `alembic upgrade head` against **both** `tapas_test` (used automatically by the test suite) and `tapas_dev` (this worktree's default `DATABASE_URL`, port 5436) — `tapas_test` rebuilds fresh every test run and will hide drift between the two.
- New router file registers in `backend/src/main.py` — mirror the existing `app.include_router(clients_router)` pattern (line ~80); add `app.include_router(leadgen_router)` in the same block.
- New models file exports through `backend/src/db/models/__init__.py` (`__all__` list) — Alembic autogenerate and every other module import models from there, not from the per-domain files directly.
- Cross-tenant access pattern: always 404, never 403, for resource-not-found-or-not-yours (established repo-wide convention — see `backend/src/api/clients.py` `_get_owned_client()` and its comment).
- **Cross-branch coordination risk (flag for SoJo, not resolvable in this session):** Task 1 below adds `users.first_name`/`users.last_name` as a *temporary* migration owned by this branch (`feature/unit-003-client-discovery-pipeline`), even though those columns conceptually belong to `Unit_006_PlatformFoundations` (per the 2026-07-21 spec decision). If `feature/unit-006-platform-foundations` also adds a migration for the same two columns before the branches merge, whichever merges second will hit a duplicate-column migration conflict. SoJo needs to actively coordinate this at merge time — e.g. by dropping this phase's temporary migration once Unit_006's real one exists, and rebasing the seed script data forward. Do not silently resolve this by guessing which branch "wins" — surface the conflict if it's discovered during merge.

---

## Decisions Log (this phase)

- **D-1**: `hc_leadgen_config.questionnaire` is the single source of truth for the intake form — including the six fixed fields, not just HC-added custom questions. `POST /api/leadgen/config/init` seeds it with six fixed entries (`removable: false`); `PATCH` can append/edit custom entries (`removable: true`) but must reject any attempt to remove or retype a fixed entry. Rationale: Stage 2 (PHASE-02) renders the questionnaire by reading this one JSONB blob — splitting fixed vs. custom across two data sources would mean Stage 2 has to merge them at render time for no benefit.
- **D-2**: Fixed question keys are frozen as `full_name`, `age`, `email`, `phone`, `primary_health_goal`, `current_health_concerns` (all type `free_text`, `required: true`). PHASE-02's questionnaire-submission handler will map `full_name`/`email`/`phone` responses onto `leads.full_name`/`email`/`phone` by these exact keys — do not rename them in a later phase without updating that mapping.
- **D-3**: `test_panel` is seeded empty (`{"standard_tests": [], "condition_rules": []}`) at init — the curated standard-test list and condition-rule UI are HC-configured via `PATCH`, not pre-populated by the system.

---

## Task 1: `users.first_name` / `users.last_name` (temporary — see Global Constraints)

**Files:**
- Modify: `backend/src/db/models/users.py`
- Create: Alembic migration (filename generated below)
- Test: `backend/tests/unit/test_model_users_first_last_name.py`

**Interfaces:**
- Produces: `User.first_name: str | None`, `User.last_name: str | None` — nullable `TEXT` columns, read (never written) by Task 5.

- [ ] **Step 1.1: Write the failing test**

Create `backend/tests/unit/test_model_users_first_last_name.py`:

```python
"""Unit test: users.first_name / users.last_name columns exist, nullable, TEXT.

Temporary — conceptually owned by Unit_006_PlatformFoundations PHASE-01.
See Unit_003 PHASE-01 Global Constraints for the cross-branch coordination note.
"""
from sqlalchemy import Text

from src.db.models.users import User


def test_user_has_first_and_last_name_columns():
    cols = User.__table__.columns
    assert "first_name" in cols
    assert isinstance(cols["first_name"].type, Text)
    assert cols["first_name"].nullable is True
    assert "last_name" in cols
    assert isinstance(cols["last_name"].type, Text)
    assert cols["last_name"].nullable is True
```

- [ ] **Step 1.2: Run test — confirm it fails**

```bash
cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate && python -m pytest tests/unit/test_model_users_first_last_name.py -v
```

Expected: FAIL — `AssertionError` (`"first_name" in cols` is `False`).

- [ ] **Step 1.3: Add the columns**

In `backend/src/db/models/users.py`, add directly after `photo_url`:

```python
    photo_url: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)  # temporary — see Unit_003 PHASE-01 Global Constraints
    last_name: Mapped[str | None] = mapped_column(Text)   # temporary — see Unit_003 PHASE-01 Global Constraints
```

- [ ] **Step 1.4: Run test — confirm it passes**

```bash
cd backend && python -m pytest tests/unit/test_model_users_first_last_name.py -v
```

Expected: PASS.

- [ ] **Step 1.5: Generate and fill the Alembic migration**

```bash
cd backend && alembic revision -m "add_first_last_name_to_users_temp"
```

Open the generated file under `backend/alembic/versions/` and fill in:

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
```

- [ ] **Step 1.6: Apply migration to both databases**

```bash
cd backend && DATABASE_URL=$TEST_DATABASE_URL alembic upgrade head   # tapas_test
cd backend && alembic upgrade head                                    # tapas_dev, port 5436 per this worktree's .env
```

- [ ] **Step 1.7: Commit**

```bash
git add backend/src/db/models/users.py backend/alembic/versions/*add_first_last_name_to_users_temp.py backend/tests/unit/test_model_users_first_last_name.py
git commit -m "feat(leadgen): add temporary users.first_name/last_name columns"
```

---

## Task 2: `hc_leadgen_config` model + migration

**Files:**
- Create: `backend/src/db/models/leadgen.py`
- Modify: `backend/src/db/models/__init__.py`
- Create: Alembic migration
- Test: `backend/tests/unit/test_model_hc_leadgen_config.py`

**Interfaces:**
- Produces: `HcLeadgenConfig` model — consumed by Task 5 (endpoints).

- [ ] **Step 2.1: Write the failing test**

Create `backend/tests/unit/test_model_hc_leadgen_config.py`:

```python
"""Unit test: HcLeadgenConfig model — columns, types, defaults."""
import sqlalchemy as sa

from src.db.models.leadgen import HcLeadgenConfig


def test_hc_leadgen_config_columns():
    cols = HcLeadgenConfig.__table__.columns
    assert cols["hc_user_id"].nullable is False
    assert cols["hc_slug"].nullable is False
    assert cols["hc_slug"].unique is True
    assert isinstance(cols["questionnaire"].type, sa.dialects.postgresql.JSONB)
    assert isinstance(cols["test_panel"].type, sa.dialects.postgresql.JSONB)
    assert cols["consultation_duration_min"].nullable is False
    assert cols["lead_expiry_days"].nullable is False
```

- [ ] **Step 2.2: Run test — confirm it fails**

```bash
cd backend && python -m pytest tests/unit/test_model_hc_leadgen_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.db.models.leadgen'`.

- [ ] **Step 2.3: Write the model**

Create `backend/src/db/models/leadgen.py`:

```python
"""Leadgen models: hc_leadgen_config. Per SPEC-0001-client-discovery-pipeline.md."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class HcLeadgenConfig(Base):
    """One row per HC. hc_slug is immutable after creation — no update path exists."""
    __tablename__ = "hc_leadgen_config"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    hc_slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    questionnaire: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    test_panel: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        default=lambda: {"standard_tests": [], "condition_rules": []},
        server_default=text("'{\"standard_tests\": [], \"condition_rules\": []}'::jsonb"),
    )
    consultation_fee_inr: Mapped[int | None] = mapped_column()
    consultation_duration_min: Mapped[int] = mapped_column(nullable=False, default=45, server_default=text("45"))
    scheduling_link: Mapped[str | None] = mapped_column(Text)
    notification_delivery: Mapped[str] = mapped_column(Text, nullable=False, default="email", server_default=text("'email'"))
    lead_expiry_days: Mapped[int] = mapped_column(nullable=False, default=60, server_default=text("60"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
```

- [ ] **Step 2.4: Export from `__init__.py`**

In `backend/src/db/models/__init__.py`, add the import and `__all__` entry:

```python
from src.db.models.leadgen import HcLeadgenConfig
```

Add `"HcLeadgenConfig"` to `__all__`.

- [ ] **Step 2.5: Run test — confirm it passes**

```bash
cd backend && python -m pytest tests/unit/test_model_hc_leadgen_config.py -v
```

Expected: PASS.

- [ ] **Step 2.6: Generate and fill the Alembic migration**

```bash
cd backend && alembic revision -m "add_hc_leadgen_config_table"
```

Fill in (mirroring `c4f6effa2ddf_add_diet_chart_sends_table.py`'s inline-FK style):

```python
def upgrade() -> None:
    op.create_table(
        "hc_leadgen_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hc_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("hc_slug", sa.Text(), nullable=False, unique=True),
        sa.Column("questionnaire", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("test_panel", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                   server_default=sa.text('\'{"standard_tests": [], "condition_rules": []}\'::jsonb')),
        sa.Column("consultation_fee_inr", sa.Integer(), nullable=True),
        sa.Column("consultation_duration_min", sa.Integer(), nullable=False, server_default=sa.text("45")),
        sa.Column("scheduling_link", sa.Text(), nullable=True),
        sa.Column("notification_delivery", sa.Text(), nullable=False, server_default=sa.text("'email'")),
        sa.Column("lead_expiry_days", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("hc_leadgen_config")
```

- [ ] **Step 2.7: Apply migration to both databases** (same commands as Step 1.6)

- [ ] **Step 2.8: Commit**

```bash
git add backend/src/db/models/leadgen.py backend/src/db/models/__init__.py backend/alembic/versions/*add_hc_leadgen_config_table.py backend/tests/unit/test_model_hc_leadgen_config.py
git commit -m "feat(leadgen): add hc_leadgen_config table and model"
```

---

## Task 3: `leads`, `lead_questionnaire_responses`, `lead_upload_tokens`, `lead_files` models + migration

Not used by any endpoint until PHASE-02–06, but built now (data-layer-upfront, matching how Unit_001 PHASE-01 built its whole schema before PHASE-02/03 consumed it).

**Files:**
- Modify: `backend/src/db/models/leadgen.py` (add all four classes)
- Modify: `backend/src/db/models/__init__.py`
- Create: Alembic migration
- Test: `backend/tests/unit/test_model_leadgen_core_tables.py`

**Interfaces:**
- Produces: `Lead`, `LeadQuestionnaireResponse`, `LeadUploadToken`, `LeadFile` models — consumed starting PHASE-02.
- Consumes: `Client` (`backend/src/db/models/clients.py`) for `Lead.converted_client_id` FK; `LlmCall` (`backend/src/db/models/llm.py`) for `Lead.brief_llm_call_id` FK.

- [ ] **Step 3.1: Write the failing test**

Create `backend/tests/unit/test_model_leadgen_core_tables.py`:

```python
"""Unit test: Lead, LeadQuestionnaireResponse, LeadUploadToken, LeadFile — columns and constraints."""
from src.db.models.leadgen import Lead, LeadFile, LeadQuestionnaireResponse, LeadUploadToken


def test_lead_columns():
    cols = Lead.__table__.columns
    assert cols["hc_user_id"].nullable is False
    assert cols["full_name"].nullable is False
    assert cols["email"].nullable is False
    assert cols["status"].nullable is False
    assert cols["converted_client_id"].nullable is True


def test_lead_unique_hc_email_constraint():
    constraint_cols = {tuple(c.columns.keys()) for c in Lead.__table__.constraints if hasattr(c, "columns") and len(c.columns) == 2}
    assert ("hc_user_id", "email") in constraint_cols


def test_lead_questionnaire_response_cascades_from_lead():
    fk = next(iter(LeadQuestionnaireResponse.__table__.columns["lead_id"].foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_lead_upload_token_hash_unique():
    assert LeadUploadToken.__table__.columns["token_hash"].unique is True


def test_lead_file_has_direct_tenant_scoping():
    cols = LeadFile.__table__.columns
    assert "hc_user_id" in cols  # direct scoping, not solely via lead join — per spec
```

- [ ] **Step 3.2: Run test — confirm it fails**

```bash
cd backend && python -m pytest tests/unit/test_model_leadgen_core_tables.py -v
```

Expected: FAIL — `ImportError` (names don't exist yet in `src.db.models.leadgen`).

- [ ] **Step 3.3: Add the four model classes**

Append to `backend/src/db/models/leadgen.py` (add these imports at the top: `from sqlalchemy import Index, Integer, UniqueConstraint`):

```python
class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("hc_user_id", "email", name="uq_leads_hc_user_id_email"),
        Index("idx_leads_hc_user_id", "hc_user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    test_recommendation: Mapped[dict | None] = mapped_column(JSONB)
    brief_text: Mapped[str | None] = mapped_column(Text)
    brief_llm_call_id: Mapped[UUID | None] = mapped_column(ForeignKey("llm_calls.id"))
    consent_given_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    consent_purpose: Mapped[str | None] = mapped_column(Text)
    converted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    converted_client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id"))
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class LeadQuestionnaireResponse(Base):
    __tablename__ = "lead_questionnaire_responses"
    __table_args__ = (Index("idx_lead_qr_lead_id", "lead_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    question_key: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class LeadUploadToken(Base):
    __tablename__ = "lead_upload_tokens"
    __table_args__ = (Index("idx_lead_upload_tokens_lead_id", "lead_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class LeadFile(Base):
    __tablename__ = "lead_files"
    __table_args__ = (Index("idx_lead_files_lead_id", "lead_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="blood_report", server_default=text("'blood_report'"))
```

- [ ] **Step 3.4: Export all four from `__init__.py`** (same pattern as Step 2.4)

- [ ] **Step 3.5: Run test — confirm it passes**

```bash
cd backend && python -m pytest tests/unit/test_model_leadgen_core_tables.py -v
```

Expected: PASS.

- [ ] **Step 3.6: Generate and fill the Alembic migration**

```bash
cd backend && alembic revision -m "add_leads_core_tables"
```

Fill `upgrade()` creating the four tables in dependency order (`leads` first, since the other three FK into it), using the same inline-FK style as Task 2 Step 2.6. Include the `uq_leads_hc_user_id_email` unique constraint and all four indexes from Step 3.3. Write the matching `downgrade()` dropping tables in reverse order.

- [ ] **Step 3.7: Apply migration to both databases** (same commands as Step 1.6)

- [ ] **Step 3.8: Commit**

```bash
git add backend/src/db/models/leadgen.py backend/src/db/models/__init__.py backend/alembic/versions/*add_leads_core_tables.py backend/tests/unit/test_model_leadgen_core_tables.py
git commit -m "feat(leadgen): add leads, lead_questionnaire_responses, lead_upload_tokens, lead_files tables"
```

---

## Task 4: Seed script — backfill `first_name`/`last_name` for existing pilot HC(s)

Temporary, per the sequencing decision in Global Constraints — unblocks Unit_003 work without waiting on Unit_006's settings UI.

**Files:**
- Create: `backend/scripts/seed_hc_names.py`

**Interfaces:**
- Consumes: `User` model (Task 1's new columns).

- [ ] **Step 4.1: Write the script**

Create `backend/scripts/seed_hc_names.py`:

```python
"""One-off: backfill users.first_name/last_name for pilot HCs, ahead of Unit_006.

Temporary — see Unit_003 PHASE-01 Global Constraints. Run manually, once per HC,
against this worktree's tapas_dev database (port 5436).

Usage:
    python scripts/seed_hc_names.py <email> <first_name> <last_name>
"""
import asyncio
import sys

from sqlalchemy import select

from src.db.session import get_session_factory
from src.db.models.users import User


async def main(email: str, first_name: str, last_name: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user found with email {email!r}")
            sys.exit(1)
        user.first_name = first_name
        user.last_name = last_name
        await db.commit()
        print(f"Set {email}: first_name={first_name!r} last_name={last_name!r}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/seed_hc_names.py <email> <first_name> <last_name>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
```

**Note for the implementing agent:** verify the exact async session factory import path before writing this — `backend/src/db/session.py` is referenced by name convention (`get_db()` dependency lives there per Task 1's research and prior phases) but this plan was not able to confirm the standalone (non-FastAPI-dependency) session factory's exact function name. Grep `backend/src/db/session.py` and `backend/scripts/` for an existing standalone-script DB access pattern (there should be one, since `backend/scripts/create_hc_user.py` already exists per `SESSION_LOG.md`'s 2026-05-02 entry) and match it exactly rather than trusting the import above verbatim.

- [ ] **Step 4.2: Run it against this worktree's dev DB for whichever pilot HC(s) SoJo specifies**

```bash
cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate && python scripts/seed_hc_names.py <hc-email> <FirstName> <LastName>
```

No automated test for this task — it's a manual operational script, not application logic. Confirm success by querying: `SELECT email, first_name, last_name FROM users WHERE email = '<hc-email>';` via `psql` against port 5436.

- [ ] **Step 4.3: Commit**

```bash
git add backend/scripts/seed_hc_names.py
git commit -m "chore(leadgen): add temporary seed script for HC first/last name"
```

---

## Task 5: `POST /api/leadgen/config/init`

**Files:**
- Create: `backend/src/api/leadgen.py`
- Modify: `backend/src/main.py` (register router)
- Test: `backend/tests/integration/test_leadgen_config.py`

**Interfaces:**
- Consumes: `HcClaimsDep`, `TenantDep`, `DbDep` (`backend/src/api/deps.py`); `User`, `HcLeadgenConfig` models.
- Produces: `router = APIRouter(prefix="/api/leadgen", tags=["leadgen"])` — consumed by Tasks 6, 7 (same router, more routes added to this file) and `main.py`.

- [ ] **Step 5.1: Write the failing tests**

Create `backend/tests/integration/test_leadgen_config.py`:

```python
"""Integration tests: /api/leadgen/config* endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_init_fails_when_profile_incomplete(http_client: AsyncClient, hc_headers):
    # hc_user fixture has no first_name/last_name set by default
    resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["error"] == "profile_incomplete"


async def test_init_succeeds_and_generates_slug(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()

    resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp.status_code == 201
    body = resp.json()
    import re
    assert re.match(r"^asha-rao-[a-z0-9]{5}$", body["hc_slug"])
    assert len(body["questionnaire"]) == 6
    assert all(q["removable"] is False for q in body["questionnaire"])
    assert body["test_panel"] == {"standard_tests": [], "condition_rules": []}


async def test_init_conflicts_if_already_configured(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    resp1 = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp1.status_code == 201

    resp2 = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["error"] == "already_configured"
```

- [ ] **Step 5.2: Run tests — confirm they fail**

```bash
cd backend && python -m pytest tests/integration/test_leadgen_config.py -v
```

Expected: FAIL — `404 Not Found` (route doesn't exist yet).

- [ ] **Step 5.3: Write the router**

Create `backend/src/api/leadgen.py`:

```python
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
```

- [ ] **Step 5.4: Register the router**

In `backend/src/main.py`, add the import alongside the other routers and register it in the `include_router` block (mirroring line ~80):

```python
app.include_router(leadgen_router)
```

- [ ] **Step 5.5: Run tests — confirm they pass**

```bash
cd backend && python -m pytest tests/integration/test_leadgen_config.py -v
```

Expected: PASS (all three).

- [ ] **Step 5.6: Commit**

```bash
git add backend/src/api/leadgen.py backend/src/main.py backend/tests/integration/test_leadgen_config.py
git commit -m "feat(leadgen): add POST /api/leadgen/config/init"
```

---

## Task 6: `GET /api/leadgen/config`

**Files:**
- Modify: `backend/src/api/leadgen.py`
- Modify: `backend/tests/integration/test_leadgen_config.py`

**Interfaces:**
- Consumes: `LeadgenConfigOut` (Task 5).

- [ ] **Step 6.1: Write the failing tests**

Append to `backend/tests/integration/test_leadgen_config.py`:

```python
async def test_get_config_returns_setup_incomplete_when_not_configured(http_client: AsyncClient, hc_headers):
    resp = await http_client.get("/api/leadgen/config", headers=hc_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False


async def test_get_config_returns_full_config_when_configured(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    init_resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    assert init_resp.status_code == 201

    resp = await http_client.get("/api/leadgen/config", headers=hc_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["hc_slug"] == init_resp.json()["hc_slug"]


async def test_get_config_cross_tenant_isolation(http_client: AsyncClient, hc_user, hc_headers, hc2_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.get("/api/leadgen/config", headers=hc2_headers)
    assert resp.status_code == 200
    assert resp.json()["configured"] is False  # HC2 sees their own (nonexistent) config, never HC1's
```

- [ ] **Step 6.2: Run tests — confirm they fail**

```bash
cd backend && python -m pytest tests/integration/test_leadgen_config.py -k "get_config" -v
```

Expected: FAIL — `404 Not Found`.

- [ ] **Step 6.3: Add the endpoint**

Append to `backend/src/api/leadgen.py`:

```python
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
```

- [ ] **Step 6.4: Run tests — confirm they pass**

```bash
cd backend && python -m pytest tests/integration/test_leadgen_config.py -v
```

Expected: PASS (all six tests in the file so far).

- [ ] **Step 6.5: Commit**

```bash
git add backend/src/api/leadgen.py backend/tests/integration/test_leadgen_config.py
git commit -m "feat(leadgen): add GET /api/leadgen/config"
```

---

## Task 7: `PATCH /api/leadgen/config`

**Files:**
- Modify: `backend/src/api/leadgen.py`
- Modify: `backend/tests/integration/test_leadgen_config.py`

- [ ] **Step 7.1: Write the failing tests**

Append to `backend/tests/integration/test_leadgen_config.py`:

```python
async def test_patch_updates_settings_fields(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.patch(
        "/api/leadgen/config", headers=hc_headers,
        json={"consultation_fee_inr": 2000, "scheduling_link": "https://calendly.com/asha"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["consultation_fee_inr"] == 2000
    assert body["scheduling_link"] == "https://calendly.com/asha"


async def test_patch_ignores_hc_slug_field(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    init_resp = await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})
    original_slug = init_resp.json()["hc_slug"]

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"hc_slug": "hacked-slug-00000"})
    assert resp.status_code == 200
    assert resp.json()["hc_slug"] == original_slug  # unchanged


async def test_patch_rejects_removing_fixed_question(http_client: AsyncClient, hc_user, hc_headers, db):
    hc_user.first_name = "Asha"
    hc_user.last_name = "Rao"
    await db.commit()
    await http_client.post("/api/leadgen/config/init", headers=hc_headers, json={})

    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"questionnaire": []})
    assert resp.status_code == 422


async def test_patch_returns_404_when_not_configured(http_client: AsyncClient, hc_headers):
    resp = await http_client.patch("/api/leadgen/config", headers=hc_headers, json={"consultation_fee_inr": 1000})
    assert resp.status_code == 404
```

- [ ] **Step 7.2: Run tests — confirm they fail**

```bash
cd backend && python -m pytest tests/integration/test_leadgen_config.py -k "patch" -v
```

Expected: FAIL — `405 Method Not Allowed`.

- [ ] **Step 7.3: Add the endpoint**

Append to `backend/src/api/leadgen.py`:

```python
class LeadgenConfigPatch(BaseModel):
    hc_slug: str | None = None  # accepted but always ignored — read-only, see spec Non-goals
    questionnaire: list[dict] | None = None
    test_panel: dict | None = None
    consultation_fee_inr: int | None = None
    consultation_duration_min: int | None = None
    scheduling_link: str | None = None
    notification_delivery: str | None = None
    lead_expiry_days: int | None = None


def _validate_questionnaire_keeps_fixed_questions(new_list: list[dict]) -> None:
    fixed_keys = {q["key"] for q in _FIXED_QUESTIONS}
    new_keys = {q.get("key") for q in new_list}
    missing = fixed_keys - new_keys
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot remove fixed questions: {sorted(missing)}",
        )
    for q in new_list:
        if q.get("key") in fixed_keys and q.get("removable", False):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Fixed question '{q['key']}' cannot be marked removable")


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
    if "questionnaire" in update_data:
        _validate_questionnaire_keeps_fixed_questions(update_data["questionnaire"])
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    return LeadgenConfigOut.model_validate(config)
```

- [ ] **Step 7.4: Run tests — confirm they pass**

```bash
cd backend && python -m pytest tests/integration/test_leadgen_config.py -v
```

Expected: PASS (all ten tests in the file).

- [ ] **Step 7.5: Commit**

```bash
git add backend/src/api/leadgen.py backend/tests/integration/test_leadgen_config.py
git commit -m "feat(leadgen): add PATCH /api/leadgen/config"
```

---

## Task 8: Frontend — `/settings/leadgen` page (Setup, Intake Form, Test Panel tabs)

> **2026-08-13 correction — read before touching this page.** This page now lives at `frontend/src/app/(app)/settings/(hub)/onboarding/` (route `/settings/onboarding`), not the `settings/leadgen/` path described below. It was moved into `Unit_006_PlatformFoundations`'s Settings hub, filling that unit's empty "Onboarding" sidebar placeholder — the two were independently-named versions of the same concept, built on sibling branches. See SPEC-0001 §Shared surfaces and Changelog (2026-08-13). The task write-up below is left as-is as a historical record of what Task 8 originally built and verified; treat every `settings/leadgen` path in it as superseded by `settings/(hub)/onboarding`.

**Files:**
- Create: `frontend/src/lib/api/leadgen.ts`
- Create: `frontend/src/app/(app)/settings/leadgen/page.tsx`

**Interfaces:**
- Consumes: `fetchWithAuth` (`frontend/src/lib/auth/client.ts`), `API_URL` (`frontend/src/lib/config`), `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` (`frontend/src/components/ui/tabs.tsx`).

No automated tests for this task — the existing settings pages (`diet-chart-templates`, `sessions`) have no frontend test coverage either; this phase follows the same convention. Verify manually per Step 8.4.

- [ ] **Step 8.1: Write the API module**

Create `frontend/src/lib/api/leadgen.ts`:

```typescript
import { z } from "zod";
import { fetchWithAuth } from "@/lib/auth/client";
import { API_URL } from "@/lib/config";

const QuestionSchema = z.object({
  key: z.string(),
  text: z.string(),
  type: z.enum(["free_text", "multiple_choice", "scale"]),
  required: z.boolean(),
  removable: z.boolean(),
  options: z.array(z.string()).optional(),
});

const TestPanelSchema = z.object({
  standard_tests: z.array(z.string()),
  condition_rules: z.array(z.object({ keywords: z.array(z.string()), tests: z.array(z.string()) })),
});

export const LeadgenConfigStatusSchema = z.object({
  configured: z.boolean(),
  hc_slug: z.string().nullable().optional(),
  questionnaire: z.array(QuestionSchema).nullable().optional(),
  test_panel: TestPanelSchema.nullable().optional(),
  consultation_fee_inr: z.number().nullable().optional(),
  consultation_duration_min: z.number().nullable().optional(),
  scheduling_link: z.string().nullable().optional(),
  notification_delivery: z.string().nullable().optional(),
  lead_expiry_days: z.number().nullable().optional(),
});
export type LeadgenConfigStatus = z.infer<typeof LeadgenConfigStatusSchema>;

export async function getLeadgenConfig(): Promise<LeadgenConfigStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/leadgen/config`);
  if (!res.ok) throw new Error(`Failed to fetch leadgen config: ${res.status}`);
  return LeadgenConfigStatusSchema.parse(await res.json());
}

export async function initLeadgenConfig(): Promise<LeadgenConfigStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/leadgen/config/init`, { method: "POST", body: "{}" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? `Failed to initialize leadgen config: ${res.status}`);
  }
  return LeadgenConfigStatusSchema.parse({ configured: true, ...(await res.json()) });
}

export async function patchLeadgenConfig(patch: Record<string, unknown>): Promise<LeadgenConfigStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/leadgen/config`, {
    method: "PATCH",
    body: JSON.stringify(patch),
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Failed to update leadgen config: ${res.status}`);
  return LeadgenConfigStatusSchema.parse({ configured: true, ...(await res.json()) });
}
```

- [ ] **Step 8.2: Write the page shell with tabs and the init flow**

Create `frontend/src/app/(app)/settings/leadgen/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { getLeadgenConfig, initLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";

export default function LeadgenSettingsPage() {
  const [config, setConfig] = useState<LeadgenConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("setup");

  useEffect(() => {
    getLeadgenConfig().then(setConfig).finally(() => setLoading(false));
  }, []);

  async function handleInit() {
    setInitError(null);
    try {
      const result = await initLeadgenConfig();
      setConfig(result);
    } catch (err) {
      setInitError(err instanceof Error ? err.message : "Setup failed");
    }
  }

  if (loading) return <div className="p-6">Loading...</div>;

  if (!config?.configured) {
    return (
      <div className="p-6 max-w-lg">
        <h1 className="text-xl font-semibold mb-2">Set up lead generation</h1>
        <p className="text-sm text-muted-foreground mb-4">
          This creates your shareable intake link. Your name and business details come from your{" "}
          <a href="/settings/profile" className="underline">profile settings</a> — make sure that&apos;s filled in first.
        </p>
        {initError && (
          <p className="text-sm text-destructive mb-4">
            {initError}{" "}
            <a href="/settings/profile" className="underline">Go to profile settings</a>
          </p>
        )}
        <button
          onClick={handleInit}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Set up my intake link
        </button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-4">
        <p className="text-sm text-muted-foreground">Your intake link</p>
        <code className="text-sm">tapas.app/intake/{config.hc_slug}</code>
      </div>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="overflow-x-auto">
          <TabsList variant="line">
            <TabsTrigger value="setup">Setup</TabsTrigger>
            <TabsTrigger value="intake-form">Intake Form</TabsTrigger>
            <TabsTrigger value="test-panel">Test Panel</TabsTrigger>
          </TabsList>
        </div>
        <div className="mt-6">
          <TabsContent value="setup">
            <SetupTab config={config} onUpdate={setConfig} />
          </TabsContent>
          <TabsContent value="intake-form">
            <IntakeFormTab config={config} onUpdate={setConfig} />
          </TabsContent>
          <TabsContent value="test-panel">
            <TestPanelTab config={config} onUpdate={setConfig} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
```

**Note for the implementing agent:** `SetupTab`, `IntakeFormTab`, `TestPanelTab` are stubbed as separate components in Step 8.3 below — do not inline them into `page.tsx`, which would make the file too large per this repo's "one clear responsibility per file" convention.

- [ ] **Step 8.3: Write the three tab components**

Create `frontend/src/app/(app)/settings/leadgen/SetupTab.tsx`:

```tsx
"use client";

import { useState } from "react";
import { patchLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";

export function SetupTab({ config, onUpdate }: { config: LeadgenConfigStatus; onUpdate: (c: LeadgenConfigStatus) => void }) {
  const [fee, setFee] = useState(config.consultation_fee_inr?.toString() ?? "");
  const [duration, setDuration] = useState(config.consultation_duration_min?.toString() ?? "45");
  const [schedulingLink, setSchedulingLink] = useState(config.scheduling_link ?? "");
  const [expiryDays, setExpiryDays] = useState(config.lead_expiry_days?.toString() ?? "60");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await patchLeadgenConfig({
        consultation_fee_inr: fee ? Number(fee) : null,
        consultation_duration_min: Number(duration),
        scheduling_link: schedulingLink || null,
        lead_expiry_days: Number(expiryDays),
      });
      onUpdate(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-md">
      <label className="block">
        <span className="text-sm font-medium">Consultation fee (INR)</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={fee} onChange={(e) => setFee(e.target.value)} type="number" />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Duration (minutes)</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={duration} onChange={(e) => setDuration(e.target.value)} type="number" />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Scheduling link</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={schedulingLink} onChange={(e) => setSchedulingLink(e.target.value)} placeholder="https://calendly.com/..." />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Lead expiry (days)</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={expiryDays} onChange={(e) => setExpiryDays(e.target.value)} type="number" />
      </label>
      <button onClick={handleSave} disabled={saving} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
```

Create `frontend/src/app/(app)/settings/leadgen/IntakeFormTab.tsx`:

```tsx
"use client";

import { useState } from "react";
import { patchLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";

type Question = NonNullable<LeadgenConfigStatus["questionnaire"]>[number];

export function IntakeFormTab({ config, onUpdate }: { config: LeadgenConfigStatus; onUpdate: (c: LeadgenConfigStatus) => void }) {
  const [questions, setQuestions] = useState<Question[]>(config.questionnaire ?? []);
  const [saving, setSaving] = useState(false);

  function addCustomQuestion() {
    setQuestions([...questions, { key: `custom_${Date.now()}`, text: "", type: "free_text", required: false, removable: true }]);
  }

  function removeQuestion(key: string) {
    setQuestions(questions.filter((q) => q.key !== key || !q.removable ? q.key !== key : true).filter((q) => !(q.key === key && q.removable)));
  }

  async function handleSave() {
    setSaving(true);
    try {
      onUpdate(await patchLeadgenConfig({ questionnaire: questions }));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-lg">
      <div>
        <p className="text-sm font-medium mb-2">Required fields (always present)</p>
        {questions.filter((q) => !q.removable).map((q) => (
          <div key={q.key} className="text-sm text-muted-foreground py-1">{q.text}</div>
        ))}
      </div>
      <div>
        <p className="text-sm font-medium mb-2">Custom questions</p>
        {questions.filter((q) => q.removable).map((q) => (
          <div key={q.key} className="flex items-center gap-2 py-1">
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm"
              value={q.text}
              onChange={(e) => setQuestions(questions.map((x) => (x.key === q.key ? { ...x, text: e.target.value } : x)))}
            />
            <button onClick={() => removeQuestion(q.key)} className="text-sm text-destructive">Remove</button>
          </div>
        ))}
        <button onClick={addCustomQuestion} className="mt-2 text-sm underline">+ Add question</button>
      </div>
      <button onClick={handleSave} disabled={saving} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
```

Create `frontend/src/app/(app)/settings/leadgen/TestPanelTab.tsx`:

```tsx
"use client";

import { useState } from "react";
import { patchLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";

export function TestPanelTab({ config, onUpdate }: { config: LeadgenConfigStatus; onUpdate: (c: LeadgenConfigStatus) => void }) {
  const [standardTests, setStandardTests] = useState<string>((config.test_panel?.standard_tests ?? []).join(", "));
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await patchLeadgenConfig({
        test_panel: {
          standard_tests: standardTests.split(",").map((s) => s.trim()).filter(Boolean),
          condition_rules: config.test_panel?.condition_rules ?? [],
        },
      });
      onUpdate(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-lg">
      <label className="block">
        <span className="text-sm font-medium">Standard baseline tests (comma-separated)</span>
        <textarea
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          rows={3}
          value={standardTests}
          onChange={(e) => setStandardTests(e.target.value)}
          placeholder="CBC, HbA1c, TSH, Lipid Profile"
        />
      </label>
      <p className="text-xs text-muted-foreground">
        Condition-specific rules (keyword → additional test) are not yet editable in this UI — coming in a later phase.
      </p>
      <button onClick={handleSave} disabled={saving} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
```

- [ ] **Step 8.4: Manual verification**

```bash
cd frontend && export PATH=~/.nvm/versions/node/v22.15.1/bin:$PATH && npm run dev
```

Navigate to `/settings/leadgen` while signed in as an HC whose `first_name`/`last_name` are set (via Task 4's seed script). Confirm:
- HC without profile fields set sees the "profile incomplete" error with a working link to `/settings/profile`
- Clicking "Set up my intake link" generates a slug matching `firstname-lastname-xxxxx`
- All three tabs render; Setup tab saves fee/duration/scheduling-link/expiry and they persist on reload
- Intake Form tab shows the 6 fixed questions read-only, custom questions can be added/removed/saved
- Test Panel tab saves a comma-separated standard test list and it persists on reload

- [ ] **Step 8.5: Commit**

```bash
git add frontend/src/lib/api/leadgen.ts frontend/src/app/\(app\)/settings/leadgen/
git commit -m "feat(leadgen): add /settings/leadgen page with Setup, Intake Form, Test Panel tabs"
```

---

## Self-Review Notes

- **Spec coverage**: Stage 1 steps 1–6 (SPEC-0001 §Stage 1) are covered by Tasks 1–8. Step 7 (HC copies/shares the link) needs no backend/frontend work beyond displaying the slug (done in Step 8.2) — the URL being channel-agnostic is a documentation fact, not a code deliverable. All 5 "New tables" from the Data section are covered (Tasks 2–3). Acceptance criteria §Setup's four checkboxes map to Task 5 (slug format, init), Task 7 (PATCH ignores hc_slug — no endpoint updates it), Task 5+6 (profile-incomplete path). The intake-link-returns-200 criterion (`GET /api/intake/:slug` — public) is explicitly **PHASE-02**, not this phase.
- **Type consistency checked**: `LeadgenConfigOut` (Task 5) and `LeadgenConfigStatusOut` (Task 6) both read from the same `HcLeadgenConfig` model fields; `LeadgenConfigPatch` (Task 7) field names match both. Frontend `LeadgenConfigStatusSchema` (Task 8) mirrors the same field set.
- **No placeholders**: confirmed no TBD/TODO markers remain in any task's code.

---

## Post-phase correction — 2026-08-13

Task 8's final review (see `docs/SESSION_LOG.md`, this phase's entry) already flagged that `/settings/leadgen` was "not yet reachable from any in-app nav" and ruled it a non-blocking gap at ship time. It stayed unresolved because `Unit_006_PlatformFoundations` PHASE-01 — which introduced the Settings hub this page needed to join — was built independently on a sibling branch, and the two units' work only got reconciled once both had merged into a shared `main`. Resolution: Task 8's four files moved from `frontend/src/app/(app)/settings/leadgen/` to `frontend/src/app/(app)/settings/(hub)/onboarding/`, filling Unit_006's reserved-but-empty "Onboarding" sidebar slot. No backend change; `/api/leadgen/*` untouched. Full record: SPEC-0001 §Shared surfaces and Changelog.
