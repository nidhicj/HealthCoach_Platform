# PHASE-01: HC Settings & Profile

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Unit**: Unit_006_PlatformFoundations
**Status**: Verified
**Verification date**: 2026-08-03 — see `docs/VERIFICATION.md` § Unit_006 PHASE-01 — HC Settings & Profile
**Implements**: `Unit_006_PlatformFoundations/SPEC-0001-platform-foundations.md` — PHASE-01 scope (Flow, Data, API surface, Acceptance criteria — all items)
**ADRs implemented**: ADR-0001 (stack — no new dependencies), ADR-0005 (auth / tenant scoping — `require_role('hc')` + `claims.sub` pattern, and the `/api/me/*` actor boundary this phase deliberately does not collide with)

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific I haven't provided. Ready?

---

## 1. Scope

Give the HC an editable business name — distinct from their personal Google identity — and a read-only view of their signed-in Google account (name, photo, email), closing the smallest of the seven Platform Foundations gaps identified in `SPEC-0001-platform-foundations.md` (Option C / D-3). Delivered via one new nullable column (`users.business_name`), one new backend router (`/api/settings/profile`, GET + PATCH, scoped to the authenticated HC), and one new frontend settings page.

Not in scope: profile-photo upload, an HC-level timezone field, notification preference toggles — all explicitly deferred per SPEC-0001 D-3, each with a stated reason.

---

## 2. Deliverables shipped

- `backend/src/db/models/users.py` — `business_name: Mapped[str | None] = mapped_column(Text)`, added to the existing `User` class
- `backend/alembic/versions/6503e78ca409_add_business_name_to_users.py` — migration adding nullable `users.business_name TEXT`; applied to both `tapas_dev` and `tapas_test`
- `backend/src/api/settings.py` — new router: `GET /api/settings/profile` and `PATCH /api/settings/profile`, both `require_role('hc')`-gated and scoped via `claims.sub` (not `TenantDep`); returns/accepts `{business_name, display_name, photo_url, email}`
- `backend/src/main.py` — `settings_router` registered alongside the existing routers
- `backend/tests/unit/test_model_users_business_name.py` — 1 unit test
- `backend/tests/integration/test_settings.py` — 10 integration tests: authenticated GET, PATCH round-trip, empty-string→null, empty-body no-op (preserves existing value), leading/trailing-whitespace trim, whitespace-only→null, max-length 422, unauthenticated 401, client-role 403, cross-HC isolation
- `frontend/src/lib/api/settings.ts` — Zod-typed API client (`SettingsProfileSchema`, `getProfile()`, `updateProfile()`)
- `frontend/src/app/(app)/settings/profile/page.tsx` — editable business-name field with save/error/"Saved" feedback states, plus a read-only block showing the HC's Google-linked avatar, name, and email
- `frontend/src/app/(app)/layout.tsx` — top nav collapsed to one "Settings" entry (→ `/settings/profile`); the standalone "Profile" nav item this phase originally added on 2026-08-03 was removed on 2026-08-04 — see §3
- `frontend/src/app/(app)/settings/layout.tsx` (added 2026-08-04) — the Settings hub: left sidebar (Profile, Onboarding placeholder, Sign out), selected section renders on the right
- `frontend/src/app/(app)/settings/onboarding/page.tsx` (added 2026-08-04) — "Coming soon" placeholder; no real feature exists yet

**(2026-08-21, Post-phase extension — Tasks 4-6, see §"Post-phase extension" below):**
- `backend/src/db/models/users.py` — removed the `# temporary — see Unit_003 PHASE-01 Global Constraints` comments on `first_name`/`last_name`; these columns (added by Unit_003's `fdec7eb` migration) are now owned by this phase, no new migration needed
- `backend/src/api/settings.py` — `first_name: str | None`, `last_name: str | None` added to `SettingsProfileOut` and to `SettingsProfilePatch` (`Field(default=None, max_length=200)`); new `_reject_empty` validator on both fields — unlike `business_name`'s normalize-to-null behavior, an explicit `null`, empty, or whitespace-only value is rejected with 422 (these fields are "required once set," not clearable via this endpoint); `patch_profile` guards both assignments with the existing `model_fields_set` no-op-on-omit pattern
- `backend/tests/integration/test_settings.py` — 9 new integration tests covering GET with/without values set, PATCH round-trip, whitespace trimming, empty-string/whitespace-only/explicit-null → 422 (value preserved), partial-update omission → no-op, max-length 422; `test_cross_hc_profile_isolation` extended to assert `first_name`/`last_name` isolation alongside `business_name`, not just added as new tests
- `frontend/src/lib/api/settings.ts` — `SettingsProfileSchema` extended with `first_name`/`last_name` (`z.string().nullable()`); `updateProfile()` signature extended to `(businessName: string | null, firstName: string, lastName: string)` — deliberately non-nullable for the two new params, since the backend never accepts `null`/empty for them
- `frontend/src/app/(app)/settings/(hub)/profile/page.tsx` — "First name" and "Last name" required inputs added above the existing "Business name" field, marked with a `*` (matching this codebase's existing required-field convention); client-side validation blocks Save (and disables the button) when either is empty/whitespace, with a dedicated inline error message distinct from the generic "Could not save" case; `business_name` behavior unchanged (still optional, still clearable to `null`)
- Deleted: `backend/scripts/seed_hc_names.py` — the temporary manual-backfill script this extension makes obsolete; no other code or docs depended on it (verified by repo-wide grep)
- No new frontend test file added — `/settings/profile` still has none, consistent with how Task 3 originally shipped (checked, not assumed)

---

## 3. Decisions made during this phase

- **Registered `settings_router` alongside the real existing routers in `main.py`**, rather than following the plan's literal Step 2.4 instruction, which referenced a nonexistent `calendar_router` (a stale artifact from another task's template) — verified there was no such router to anchor the import to, and used the actual router list instead.
- **Added a defensive `if user is None: raise HTTPException(401, "User not found")` guard to both handlers**, overriding the plan's original assumption that `require_role` already validates the row exists in the DB. It doesn't — `require_role` (`backend/src/auth/dependencies.py`) only decodes the JWT and checks `claims.role`; there is no DB round trip in the auth dependency chain. This surfaced only in the final whole-branch review (visible when reading `settings.py` and `auth/dependencies.py` together, not from either file alone), not either per-task review. Matches the existing precedent in `backend/src/auth/router.py` (~line 235-239).
- **Extended `_normalize_empty` to trim all input, not just detect the all-whitespace case** (`return v.strip() or None`) — makes the endpoint's normalization behavior correct for any client, not just the one frontend page this phase built.
- **Added a cross-HC isolation test** (`test_cross_hc_profile_isolation`) even though this endpoint deliberately doesn't use `TenantDep`/`current_tenant()` — this is the one endpoint in the codebase enforcing isolation by a different mechanism (`claims.sub`) than every other route, and nothing had verified it held. Uses the existing `hc2_headers`/`hc2_user` conftest fixtures, matching the pattern already used by `test_clients.py`, `test_sessions.py`, and others.
- **(2026-08-04) Reversed the original nav decision — "Profile" as a standalone top-level nav item was wrong.** SoJo reviewed the shipped feature and corrected it: business-name setup is a one-time thing an HC does once and rarely revisits, and the top nav shouldn't grow one item per settings section (there's already a planned "Onboarding" section coming, and more after that). Replaced with a single "Settings" top-nav entry opening a hub with a left sidebar (`frontend/src/app/(app)/settings/layout.tsx`) — Profile, Onboarding (placeholder), and Sign out at the bottom — with the selected section rendered on the right. Verified live in a browser against the running dev server (real OAuth-issued session), not just `tsc`.
- **(2026-08-04) Determined `/settings/sessions` was non-functional and unlinked it from all nav**, at SoJo's direction. Traced end-to-end: its "Sign out everywhere" button only ever called `POST /api/auth/logout`, which revokes just the *current* refresh token, not "everywhere" as labeled; its active-sessions list and per-session revoke called `GET /api/auth/sessions` / `DELETE /api/auth/sessions/{id}`, neither of which exist on the backend (the frontend file has its own comment admitting this: `// Placeholder for when GET /api/auth/sessions ships in the backend`). The file itself was left in place, untouched, in case a real multi-device session-management feature gets built later — it's just no longer reachable from any nav. The new sidebar's "Sign out" button reuses the same (correctly working, correctly labeled) logout call.

---

## 4. Bugs fixed mid-phase

- **Pydantic v2 required-field gap**: `SettingsProfilePatch.business_name: str | None = Field(max_length=200)` had no `default=None`. In Pydantic v2, a `str | None` type annotation does not make a `Field()` optional without an explicit default — `PATCH /api/settings/profile` with an empty body `{}` incorrectly returned 422 instead of being a no-op. Fixed by adding `default=None`. Caught by task review; the code was copied verbatim from this same plan's own Step 2.3 example, so the class of bug is worth remembering for future plan-authoring: illustrative code in a plan is not automatically correct.
- **Silent partial-update data loss (surfaced by the fix above)**: once `{}` was no longer rejected, the handler's unconditional `user.business_name = body.business_name` assignment meant any partial PATCH omitting `business_name` silently wiped it back to `null`. Root cause: Pydantic can't distinguish "field omitted" from "field explicitly null" without checking `model_fields_set`. Fixed by guarding the assignment: `if "business_name" in body.model_fields_set: user.business_name = body.business_name`. Caught by the implementer's own follow-up testing while fixing the first bug — not by either round of review — because the first fix's own test only checked that `{}` returned 200, which can't distinguish "wiped" from "left alone" when the fixture's starting value is already `None`. The regression test added afterward does a real round trip: set a value, PATCH `{}`, GET again, confirm the value survived.
- **Missing 401 guard for a deleted/missing user row**: see Decisions above — not a bug that manifested in any test (nothing in this codebase currently deletes a `users` row), but a real correctness gap the final whole-branch review caught before PHASE-02 (real account deletion) could make it reachable.

---

## 5. Source docs consulted

- `docs/specs/Unit_006_PlatformFoundations/SPEC-0001-platform-foundations.md` — full spec, PHASE-01 scope and D-3/D-4 decisions
- `docs/decisions/0005-auth-strategy.md` — ADR-0005 §8, the client-actor `/api/me/*` namespace this phase's `/api/settings/*` must not collide with
- `Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` — D-31, the frontend `/me/*` route prefix already locked for the client actor
- `backend/src/api/me.py` — existing client-actor endpoint pattern (namespace precedent; the one place that needs a cross-table 404 branch, unlike this phase's own-row lookup)
- `backend/src/db/models/users.py` — confirms `display_name`/`photo_url` already populated from Google OAuth, and that `deleted_at` already exists (flagged for PHASE-02, not touched here)
- `backend/src/auth/router.py` — Google OAuth callback and refresh-token issuance (confirms `hc_id == sub` for HC-role tokens)
- `frontend/AGENTS.md` — non-standard Next.js version; App Router API check required before Task 3
- `frontend/src/app/(app)/settings/sessions/page.tsx` — existing settings-page header/loading-state pattern to follow

---

## 6. Verification

- **Verification date**: 2026-08-03
- **Verification record**: `docs/VERIFICATION.md` § Unit_006 PHASE-01 — HC Settings & Profile
- **Test count at end of phase**: 273 total in `backend/` (`pytest -q`, run against this worktree's isolated `tapas_test` on port 5435) — 235 passing, 38 pre-existing failures unrelated to this phase (missing `pgcrypto` Postgres extension on this worktree's `tapas_test`, affecting only LLM/MOM-tracking tests that use `pgp_sym_encrypt`; confirmed via diff/stash comparison that these fail identically with or without this phase's changes). This phase added 11 new tests (1 unit + 10 integration), all passing.
- **Key checks**: migration confirmed applied directly against `tapas_dev` via `psql` (`business_name` column present, `alembic_version = 6503e78ca409`) — not just claimed from a migration-tool log. Full `test_settings.py` suite (10/10) covers the GET/PATCH contract, empty-string and whitespace normalization, empty-body no-op, 401/403, max-length 422, and cross-HC isolation. Frontend `npx tsc --noEmit` clean (0 new errors; 2 pre-existing, unrelated Playwright type errors in `tests/e2e/diet-chart.spec.ts` untouched by this phase). Went through subagent-driven-development's full per-task review + final whole-branch review process; one Minor finding parked (see Lessons learned).
- **(2026-08-04) Nav restructure verified live in a browser**, not just `tsc`: minted a real access token + refresh-token DB row for the actual dev HC user, drove the running dev server (frontend `:3000` + backend `:8000`, real `tapas_dev`) via Playwright. Confirmed: top nav shows one "Settings" entry that stays highlighted across both Profile and Onboarding (and correctly does *not* light up "Diet Charts", despite it also living under `/settings/*`); sidebar highlights the active section; Onboarding renders its "Coming soon" placeholder; clicking "Sign out" actually revoked the session and redirected to `/sign-in`. Test refresh token was revoked by that same sign-out click — no lingering test credential left behind.

---

## 7. Lessons learned

- **What worked**: Subagent-driven-development's per-task review caught the Pydantic required-field bug immediately, and fixing it surfaced the more serious silent-wipe bug before it ever reached a real review — the implementer's own follow-up testing habit (verify the fix actually does what the finding demands, not just that the request no longer errors) did real work here. The final whole-branch review then caught a third issue (missing 401 guard) that neither per-task review could have — it was only visible by reading two files together (`settings.py` + `auth/dependencies.py`) that no single task touched both of.
- **What surprised**: A plan's own illustrative code is not automatically correct. Both of Task 2's bugs traced back to code the plan itself specified verbatim (`Field(max_length=200)` with no default; the unconditional assignment). Per-task review still caught them because review judges the shipped code, not the plan's authority — but it's worth remembering when writing future plans that "the plan says so" is not a substitute for the plan's code being right.
- **What to do differently**: Add a cross-actor isolation test as a standing checklist item for any endpoint that deliberately departs from the repository's default tenant-scoping pattern (`TenantDep`/`current_tenant()`), rather than waiting for a final review to notice one wasn't written. `claims.sub`-scoped endpoints are rare in this codebase (this is the first), so there's no existing convention to copy from — worth adding to a future skill or checklist rather than relying on review to catch it every time.
- **(2026-08-04) What went wrong**: the original plan (and its implementation) treated "add a Profile settings page" as "add a Profile nav item," without asking how it should sit relative to the rest of the settings surface — a plausible-looking but wrong assumption about product IA that a code/spec review couldn't have caught, because the code correctly implemented what the plan said. The plan itself should have asked SoJo about navigation placement before Task 3 was built, not after. For future phases that add a new settings-adjacent page (PHASE-02 deletion, PHASE-03 consent — both already flagged in §8 as landing in this same area), confirm the nav placement with SoJo as part of writing that phase's plan, not as a follow-up correction.
- **Parked, not fixed**: the frontend's "Saved" success indicator is not cleared when the user edits the field again after a successful save — cosmetic only (no data-integrity or auth impact), ruled non-blocking rather than spun into a disallowed second fix wave. See `.superpowers/sdd/PHASE-01-hc-settings-profile/progress.md` for the full ledger.

---

## 8. Carry-over to subsequent phases

- `backend/src/api/settings.py` — establishes the `/api/settings/*` namespace; per SPEC-0001 D-2, PHASE-02 (account/data deletion) and PHASE-03 (consent) are expected to extend this same router rather than create a new namespace
- **(Superseded 2026-08-04 — see §3)** `frontend/src/app/(app)/settings/layout.tsx` is now the Settings hub: a left sidebar (`SETTINGS_SECTIONS` array) with Profile, Onboarding (placeholder), and Sign out. PHASE-02's deletion control and PHASE-03's consent toggle should each get **their own new sidebar entry and route** (e.g. `/settings/account`, `/settings/consent`) added to `SETTINGS_SECTIONS` in this layout — not crammed into the Profile page itself, and confirm the nav placement with SoJo while writing that phase's plan (per §7 lesson learned), not after building it.
- **(2026-08-13) The "Onboarding" placeholder is filled.** `Unit_003_ClientDiscoveryPipeline` moved its independently-built HC setup page (previously the unlinked `/settings/leadgen`) into this slot — it now lives at `/settings/onboarding`, inside `settings/(hub)/`. No code in this unit changed; noted here so PHASE-02/PHASE-03 authors don't plan around an "Onboarding" slot that's actually still empty. See `Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` §Shared surfaces.
- Convention: look up the authenticated user via `claims.sub` directly (not `TenantDep`/`current_tenant()`) when an endpoint reads/writes the authenticated user's *own* row rather than a tenant-scoped domain resource — later phases touching the HC's own account should follow this same distinction

---

## Implementation plan

**Goal:** Give the HC an editable business name (distinct from their personal Google identity) and a read-only view of their signed-in account, closing the smallest of the seven Platform Foundations gaps (`Unit_006_PlatformFoundations/SPEC-0001-platform-foundations.md`, Option C).

**Architecture:** One new nullable column (`users.business_name`), one new backend router (`/api/settings/profile`, GET + PATCH, scoped to the authenticated HC via `claims.sub`), one new frontend settings page. `users.display_name` and `users.photo_url` (already populated from Google OAuth) are read-only in this phase — no new upload pipeline, no new OAuth scopes. Endpoint namespace is `/api/settings/*`, deliberately not `/api/me/*`, which is already the client-actor namespace (`ADR-0005 §8`, `backend/src/api/me.py`) and the client-facing frontend route prefix (`Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` D-31) — reusing it here would collide with an actor boundary that's load-bearing elsewhere.

**Tech Stack:** FastAPI/SQLAlchemy backend, Next.js/TypeScript frontend, Zod for API schema validation, Alembic for migrations. Same stack as every other phase in this repo — no new dependencies.

### Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before running any backend command
- Tests hit the real `tapas_test` Postgres DB (`backend/tests/integration/conftest.py`) — no mocking the DB
- **After generating the migration, run `alembic upgrade head` against `tapas_dev` too** (the default `DATABASE_URL` in `.env`), not just against `tapas_test` — `tapas_test` rebuilds fresh every test run and will hide drift between the two databases
- No changes to how `users.display_name`/`users.photo_url` are populated (Google OAuth callback, `backend/src/auth/router.py`) — this phase only adds `business_name` and exposes the existing fields as read-only
- New endpoint namespace is `/api/settings/*`, not `/api/me/*` (see Architecture above)
- **This plan now lives on its own branch, `feature/unit-006-platform-foundations`** (worktree `tapas_unit006`) — the earlier "do not execute on feature/unit-004-one-stop-spot" hold has been resolved; this file was moved here specifically so Task 1 can begin.
- The frontend is a non-standard Next.js version — check `node_modules/next/dist/docs/` for any App Router API used in Task 3 before writing it (per `frontend/AGENTS.md`)

---

### Task 1: `users.business_name` column + migration

**Files:**
- Modify: `backend/src/db/models/users.py` (add `business_name` column to the existing `User` class)
- Create: an Alembic migration (filename generated by the command below)
- Test: `backend/tests/unit/test_model_users_business_name.py`

**Interfaces:**
- Produces: `User.business_name: str | None` — nullable `TEXT` column on the existing `users` table

---

- [ ] **Step 1.1: Write the failing test**

Create `backend/tests/unit/test_model_users_business_name.py`:

```python
"""Unit test: users.business_name column exists, nullable, correct type."""
from sqlalchemy import Text

from src.db.models.users import User


def test_user_has_business_name_column():
    cols = User.__table__.columns
    assert "business_name" in cols
    assert isinstance(cols["business_name"].type, Text)
    assert cols["business_name"].nullable is True
```

- [ ] **Step 1.2: Run test — confirm it fails**

```bash
cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate && python -m pytest tests/unit/test_model_users_business_name.py -v
```

Expected: FAIL — `AssertionError` (`"business_name" in cols` is `False`).

- [ ] **Step 1.3: Add the column**

In `backend/src/db/models/users.py`, add one line to the `User` class, directly after `photo_url`:

```python
    photo_url: Mapped[str | None] = mapped_column(Text)
    business_name: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 1.4: Run test — confirm it passes**

```bash
cd backend && python -m pytest tests/unit/test_model_users_business_name.py -v
```

Expected: PASS.

- [ ] **Step 1.5: Generate the Alembic migration**

```bash
cd backend && alembic revision -m "add_business_name_to_users"
```

Open the generated file under `backend/alembic/versions/` and fill in `upgrade()`/`downgrade()`:

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("business_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "business_name")
```

- [ ] **Step 1.6: Apply the migration to both databases**

```bash
cd backend && alembic upgrade head
```

This applies to `tapas_dev` (the default `DATABASE_URL` in `.env`). `tapas_test` is rebuilt fresh by the test suite itself (Step 2's integration tests will apply it there automatically) — but running it against `tapas_dev` explicitly here is required per this repo's standing migration convention; skipping it leaves the dev DB silently out of sync.

- [ ] **Step 1.7: Commit**

```bash
git add backend/src/db/models/users.py backend/alembic/versions/ backend/tests/unit/test_model_users_business_name.py
git commit -m "feat(settings): add users.business_name column"
```

---

### Task 2: Backend API — `GET`/`PATCH /api/settings/profile`

**Files:**
- Create: `backend/src/api/settings.py`
- Modify: `backend/src/main.py` (register the new router)
- Test: `backend/tests/integration/test_settings.py`

**Interfaces:**
- Consumes: `HcClaimsDep`, `DbDep` (`backend/src/api/deps.py`); `User` model (`backend/src/db/models/users.py`, extended by Task 1)
- Produces: `SettingsProfileOut` (`business_name: str | None, display_name: str | None, photo_url: str | None, email: str`) — the shape Task 3's frontend Zod schema must match exactly

---

- [ ] **Step 2.1: Write the failing tests**

Create `backend/tests/integration/test_settings.py`:

```python
"""Integration tests for /api/settings/profile. Unit_006 PHASE-01."""
import pytest


@pytest.mark.asyncio
async def test_get_profile_returns_authenticated_hc(http_client, hc_user, hc_headers):
    r = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == hc_user.email
    assert body["business_name"] is None
    assert body["display_name"] is None
    assert body["photo_url"] is None


@pytest.mark.asyncio
async def test_patch_updates_business_name(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "Sunrise Wellness"}
    )
    assert r.status_code == 200
    assert r.json()["business_name"] == "Sunrise Wellness"

    r2 = await http_client.get("/api/settings/profile", headers=hc_headers)
    assert r2.json()["business_name"] == "Sunrise Wellness"


@pytest.mark.asyncio
async def test_patch_empty_string_normalizes_to_null(http_client, hc_headers):
    await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "Something"}
    )
    r = await http_client.patch("/api/settings/profile", headers=hc_headers, json={"business_name": ""})
    assert r.status_code == 200
    assert r.json()["business_name"] is None


@pytest.mark.asyncio
async def test_patch_exceeding_max_length_returns_422(http_client, hc_headers):
    r = await http_client.patch(
        "/api/settings/profile", headers=hc_headers, json={"business_name": "x" * 201}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_profile_unauthenticated_returns_401(http_client):
    r = await http_client.get("/api/settings/profile")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_client_role_forbidden(http_client, client_headers):
    r = await http_client.get("/api/settings/profile", headers=client_headers)
    assert r.status_code == 403
```

- [ ] **Step 2.2: Run tests — confirm they fail**

```bash
cd backend && python -m pytest tests/integration/test_settings.py -v
```

Expected: FAIL — `404 Not Found` on every request (route doesn't exist yet).

- [ ] **Step 2.3: Write the router**

Create `backend/src/api/settings.py`:

```python
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
```

`claims.sub` is used directly (not `TenantDep`/`current_tenant()`) because this endpoint reads/writes the authenticated user's own row, not a tenant-scoped domain resource — for an HC-role token `hc_id == sub` anyway (`backend/src/auth/router.py`, refresh-token issuance), but `sub` is the semantically correct field for "my own identity," matching the pattern `backend/src/api/me.py` uses for the client actor's own record.

`db.get(User, ...)` is not expected to return `None` here — `claims.sub` always resolves to an existing `users` row (`require_role` already validated the token against that row) — so there's no defensive `if user is None` branch, matching how `me.py`'s `_resolve_client` is the only place in this codebase that needs a 404 branch (because *that* lookup crosses tables, unlike this one).

> **Corrected during final review (see §3 Decisions, §4 Bugs fixed):** this justification was wrong. `require_role` only decodes the JWT and checks `claims.role` — it never queries the database, so it does not validate that the row exists. Both handlers now include `if user is None: raise HTTPException(401, "User not found")`, matching the precedent already in `backend/src/auth/router.py`. The code above is left as originally planned for historical record; it does not reflect what shipped.

- [ ] **Step 2.4: Register the router**

In `backend/src/main.py`, add the import alongside the existing ones (after `from src.api.sessions import router as sessions_router`):

```python
from src.api.settings import router as settings_router
```

And add the `include_router` call alongside the others:

```python
app.include_router(calendar_router)
app.include_router(settings_router)
```

- [ ] **Step 2.5: Run tests — confirm they pass**

```bash
cd backend && python -m pytest tests/integration/test_settings.py -v
```

Expected: PASS, all 6 tests.

- [ ] **Step 2.6: Run the full backend suite to confirm no regressions**

```bash
cd backend && python -m pytest -v
```

Expected: all tests pass (prior count + 7 — 1 unit test from Task 1, 6 integration tests here).

- [ ] **Step 2.7: Commit**

```bash
git add backend/src/api/settings.py backend/src/main.py backend/tests/integration/test_settings.py
git commit -m "feat(settings): add GET/PATCH /api/settings/profile"
```

---

### Task 3: Frontend — `/settings/profile` page

**Files:**
- Create: `frontend/src/lib/api/settings.ts`
- Create: `frontend/src/app/(app)/settings/profile/page.tsx`
- Modify: `frontend/src/app/(app)/layout.tsx` (add a nav entry)

**Interfaces:**
- Consumes: `SettingsProfileOut` shape from Task 2 (`business_name, display_name, photo_url, email`)
- Produces: `getProfile()`, `updateProfile(businessName: string | null)` — exported from `frontend/src/lib/api/settings.ts`, consumed by the new page

---

- [ ] **Step 3.1: Write the API client**

Create `frontend/src/lib/api/settings.ts`:

```typescript
import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

export const SettingsProfileSchema = z.object({
  business_name: z.string().nullable(),
  display_name: z.string().nullable(),
  photo_url: z.string().nullable(),
  email: z.string(),
});

export type SettingsProfile = z.infer<typeof SettingsProfileSchema>;

export async function getProfile(): Promise<SettingsProfile> {
  const res = await fetchWithAuth(`${API_URL}/api/settings/profile`);
  if (!res.ok) throw new Error(`Failed to fetch profile: ${res.status}`);
  return SettingsProfileSchema.parse(await res.json());
}

export async function updateProfile(businessName: string | null): Promise<SettingsProfile> {
  const res = await fetchWithAuth(`${API_URL}/api/settings/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ business_name: businessName }),
  });
  if (!res.ok) throw new Error(`Failed to update profile: ${res.status}`);
  return SettingsProfileSchema.parse(await res.json());
}
```

- [ ] **Step 3.2: Write the page**

Before writing App Router code, check `node_modules/next/dist/docs/` for anything in this file that touches routing/data-fetching APIs, per `frontend/AGENTS.md` — this Next.js version has documented breaking changes from the training-data version.

Create `frontend/src/app/(app)/settings/profile/page.tsx`, following the existing `frontend/src/app/(app)/settings/sessions/page.tsx` page-header/loading-state pattern:

```typescript
"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { getProfile, updateProfile, type SettingsProfile } from "@/lib/api/settings";

export default function SettingsProfilePage() {
  const [profile, setProfile] = useState<SettingsProfile | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [loadError, setLoadError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);

  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p);
        setBusinessName(p.business_name ?? "");
      })
      .catch(() => setLoadError(true));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaveError(false);
    try {
      const updated = await updateProfile(businessName.trim() === "" ? null : businessName);
      setProfile(updated);
      setBusinessName(updated.business_name ?? "");
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  }

  const loading = profile === null && !loadError;

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Account
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Profile
        </h1>
      </div>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : loadError ? (
        <p className="font-sans text-sm text-destructive">Could not load profile.</p>
      ) : (
        <>
          <div className="space-y-2">
            <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Business name
            </label>
            <Input
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder="Your practice name"
            />
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            {saveError && (
              <p className="font-sans text-xs text-destructive">Could not save. Try again.</p>
            )}
          </div>

          <Separator />

          <div className="space-y-1">
            <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Signed in as
            </p>
            <p className="font-sans text-sm text-foreground">
              {profile!.display_name ?? "—"} via Google, {profile!.email}
            </p>
          </div>
        </>
      )}
    </div>
  );
}
```

If `frontend/src/components/ui/input.tsx` does not already exist, check the existing shadcn/ui component set (`frontend/src/components/ui/`) for the project's standard text input component and use that instead — do not add a new UI primitive for this one field.

- [ ] **Step 3.3: Add the nav entry**

In `frontend/src/app/(app)/layout.tsx`, find `NAV_LINKS` and add one entry, immediately after the existing `/settings/sessions` entry:

```typescript
  { href: "/settings/sessions", label: "Settings" },
  { href: "/settings/profile", label: "Profile" },
```

- [ ] **Step 3.4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: zero new errors.

- [ ] **Step 3.5: Start the dev server and manually verify**

```bash
cd frontend && npm run dev
```

1. Sign in as an HC, navigate to `/settings/profile`.
2. Confirm the page loads with an empty "Business name" field and "Signed in as [name] via Google, [email]" below it.
3. Type a business name, click Save — confirm it persists (reload the page, field still shows the saved value).
4. Clear the field entirely, click Save — confirm it saves as empty (reload, field is empty again, no error).
5. Confirm the new "Profile" link appears in the nav next to "Settings".

- [ ] **Step 3.6: Commit**

```bash
git add frontend/src/lib/api/settings.ts "frontend/src/app/(app)/settings/profile/page.tsx" "frontend/src/app/(app)/layout.tsx"
git commit -m "feat(settings): add /settings/profile page"
```

---

### Self-review

**Spec coverage check** (against `Unit_006_PlatformFoundations/SPEC-0001-platform-foundations.md`, PHASE-01 section):

| Spec requirement | Covered by |
|---|---|
| New `users.business_name TEXT NULL` column, migration | Task 1 |
| `GET /api/settings/profile` returns `business_name, display_name, photo_url, email` | Task 2, `test_get_profile_returns_authenticated_hc` |
| `PATCH /api/settings/profile` updates `business_name` only | Task 2, `test_patch_updates_business_name` |
| Empty-string PATCH normalizes to `null` | Task 2, `test_patch_empty_string_normalizes_to_null` |
| Unauthenticated → 401 | Task 2, `test_get_profile_unauthenticated_returns_401` |
| Client-role JWT → 403/404 | Task 2, `test_client_role_forbidden` (403, via `require_role`) |
| `/settings/profile` page with editable field + read-only Google-identity block | Task 3 |
| `/api/settings/*` namespace, not `/api/me/*` | Task 2 router prefix choice, documented inline |
| Migration applied to `tapas_dev`, not just `tapas_test` | Task 1, Step 1.6 (per standing repo convention) |

**Deferred, deliberately** (per SPEC-0001 D-3, not gaps): profile-photo upload, HC-level timezone field, notification preference toggles — none has a task here, matching the spec's explicit deferral with stated reasons.

**Placeholder scan**: none found — every step has concrete, complete code.

**Type consistency check**: `SettingsProfileOut` (Python: `business_name, display_name, photo_url, email`) matches `SettingsProfileSchema` (TypeScript/Zod: same four fields, same nullability) exactly. `getProfile()`/`updateProfile()` names in Task 3 match what Task 3's own page imports — no cross-task naming drift since both live in Task 3.

**Branch check**: this plan now lives on `feature/unit-006-platform-foundations` (moved 2026-07-17, per the Changelog in `SPEC-0001-platform-foundations.md`). Task 1 may begin.

---

## Post-phase extension — 2026-08-21: `first_name`/`last_name` join this page

**Why:** `users.first_name`/`users.last_name` were added by `Unit_003_ClientDiscoveryPipeline` PHASE-01 as an explicitly-`# temporary` migration, owned by that unit only because this phase's original scope (SPEC-0001 D-3) was `business_name` only. Unit_003's own `SPEC-0001` flagged this as an open question from day one: *"Unit_006 PHASE-01 as a prerequisite... Unit_006 PHASE-01 as currently spec'd does not include these fields — it needs to be extended."* That extension never happened — instead, every HC who needed `first_name`/`last_name` set (to pass leadgen's profile-completeness gate) got it done manually via `backend/scripts/seed_hc_names.py`, a one-off script explicitly scoped to `tapas_dev` only. Production HCs have no such path today. Tasks 4-6 below close this gap for real: `first_name`/`last_name` become first-class, user-editable fields on this same page, and the seed script is retired.

**Decisions** (confirmed with SoJo before these tasks were written):
- Columns stay nullable at the DB level — no backfill migration. "Required" is enforced only at the API/UI layer (PATCH rejects empty/whitespace for these two fields specifically), matching the existing `business_name` validation pattern rather than inventing a DB constraint.
- "Required" means the Profile page form won't let you save them empty — no new app-wide onboarding gate. The existing leadgen-setup redirect (`/settings/onboarding` → `/settings/profile` if either is null) remains the only cross-flow enforcement, same as today, now self-serviceable instead of requiring an engineer to run a script.
- `business_name` is unaffected — stays optional, no validation change, and per SoJo's explicit instruction no future code should come to depend on it; it's kept purely because it's already there and does no harm.

### Task 4: Backend — `first_name`/`last_name` on `/api/settings/profile`

**Files:**
- Modify: `backend/src/db/models/users.py` — remove the `# temporary — see Unit_003 PHASE-01 Global Constraints` comments on `first_name`/`last_name` (the columns already exist, nullable `TEXT`, added by Unit_003's `fdec7eb` migration — no new migration needed here)
- Modify: `backend/src/api/settings.py` — add `first_name: str | None`, `last_name: str | None` to `SettingsProfileOut`; add both to `SettingsProfilePatch` as `Field(default=None, max_length=200)`, matching `business_name`'s existing field shape
- Modify: `backend/tests/integration/test_settings.py` — extend/add tests per below

**Behavior — read this carefully, it differs from `business_name` on purpose:**
- `GET /api/settings/profile` returns `first_name`, `last_name` alongside the existing three fields. Nullable — an HC who hasn't filled them in yet (including every existing account that predates this task) sees `null`, not an error.
- `PATCH /api/settings/profile`: omitting `first_name`/`last_name` from the body is still a no-op (reuse the exact `model_fields_set`-guard pattern `business_name` already uses — Task 2's bug history recorded a real silent-data-loss bug from getting this wrong once; do not repeat it for the new fields).
- **Unlike `business_name`**, which normalizes an empty/whitespace string to `null` (so it can be explicitly cleared), `first_name`/`last_name` must **reject** an empty or whitespace-only string with 422 when explicitly provided in the PATCH body — these are "required once set," not clearable back to null via this endpoint. Trim leading/trailing whitespace on any accepted value, same as `business_name`.
- Max length 200, same validation error shape as `business_name`'s existing max-length case.

**Tests to add/extend in `backend/tests/integration/test_settings.py`:**
- GET returns `first_name`/`last_name` when set, and `null` when not (use a fresh fixture user, not the worktree's existing dev-DB row)
- PATCH sets `first_name`/`last_name`; round-trips correctly on a subsequent GET
- PATCH with `first_name: ""` (and separately, whitespace-only `"   "`) → 422; existing value (if any) unchanged
- PATCH omitting `first_name` entirely (partial update) → no-op, existing value preserved — this is the specific regression class from Task 2's bug history; write it as a real round trip (set a value, PATCH `{}` or PATCH with only `last_name`, GET again, confirm `first_name` survived), not just an assertion that the request returns 200
- PATCH with `first_name` exceeding 200 chars → 422
- Extend `test_cross_hc_profile_isolation` (or confirm it already round-trips every field, not just `business_name`) so isolation coverage doesn't silently narrow as fields are added

### Task 5: Frontend — required First name / Last name fields on `/settings/profile`

**Files:**
- Modify: `frontend/src/lib/api/settings.ts` — extend `SettingsProfileSchema` with `first_name: z.string().nullable()`, `last_name: z.string().nullable()`; extend `updateProfile()`'s parameters and request body to send them alongside `business_name`
- Modify: `frontend/src/app/(app)/settings/(hub)/profile/page.tsx` — add "First name" and "Last name" inputs, visually marked required (check this codebase for an existing required-field visual convention — e.g. the intake page's required questions — and match it rather than inventing a new one); "Business name" stays exactly as it is today, unmarked, no validation change

**Behavior:**
- Save is blocked (or shows a clear inline error) when First name or Last name is empty/whitespace-only. Business name has no such restriction — it can be saved empty, exactly like today.
- On load, populate all three fields from `GET`. On save, PATCH all three together (existing pattern already does this for `business_name` alone — extend it, don't add a second save path).
- If the backend still returns a 422 (client-side check bypassed, or a length violation), surface it as a clear inline error — don't fail silently.

**Verification:** `npx tsc --noEmit` (0 new errors beyond this repo's documented pre-existing baseline — see PHASE-03's Task 7 report for the current baseline count if this doc's own §6 baseline is stale by then), `npm run build`. Check whether this page already has a dedicated frontend test file before deciding whether to add one — Task 3 originally shipped without one; if that's still true, note it rather than inventing a new test-setup convention for just this page.

### Task 6: Close the loop — resolve the open question, retire the seed script

**Files:**
- Modify: `docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` — mark the "Unit_006 PHASE-01 as a prerequisite" open question resolved (strikethrough style, matching how the M000 pre-population question was already resolved in the same §Open questions list), with a dated Changelog row
- Modify: `docs/specs/Unit_006_PlatformFoundations/SPEC-0001-platform-foundations.md` — add a Changelog row noting PHASE-01 was extended to cover `first_name`/`last_name`, referencing this section
- Modify: this file's `## 2. Deliverables shipped` — add the new fields/tests, once Tasks 4-5 are actually verified (not before — this section records what shipped, not what's planned)
- Delete: `backend/scripts/seed_hc_names.py` — its own docstring says "ahead of Unit_006"; that dependency has now landed, and every HC who needs `first_name`/`last_name` set can do it themselves via this page. Confirm nothing else in the codebase or its own tests references this script before deleting it.

This task is documentation and cleanup, not new application code — kept as its own task (rather than folded into Task 4 or 5's diffs) so the cross-unit doc trail gets its own reviewable commit.
