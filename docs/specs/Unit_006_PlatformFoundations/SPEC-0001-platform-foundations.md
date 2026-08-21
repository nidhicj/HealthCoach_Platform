# SPEC-0001: Platform Foundations

**Status**: Draft — PHASE-01 shipped and verified 2026-08-03 (all 8 acceptance criteria met). PHASE-02–07 are scoped (what/why/order) but not yet individually brainstormed — each needs its own design pass before it gets a PHASE plan.
**Date**: 2026-07-14
**Owner**: SoJo
**Relates to**: `CLAUDE.md` §9 (architectural principles — multi-actor data model, consent as first-class entity, real deletion), `decisions/0005-auth-strategy.md` (client-actor `/me/*` namespace this spec's PHASE-01 must not collide with), `decisions/0007-demographics-pii-encryption.md`, `domain/compliance-india.md` (DPDP), `domain/actors.md` (Operator/SoJo role, `is_operator` flag, `audit_log` requirement), `domain/glossary.md`, `Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` (D-24 notification model — relevant to PHASE-06; the storage-backend mismatch noted in D-6 below concerns that spec's F3)
**Implemented by phases**: PHASE-01-hc-settings-profile.md

---

## 0. Decisions log

Decisions made during brainstorming (2026-07-14) that this spec encodes:

| # | Decision | Context |
|---|---|---|
| D-1 | **This is a new, standalone Unit** (`Unit_006_PlatformFoundations`), not folded into Units 001–004. | The seven items below are cross-cutting "is this actually a complete, real product" gaps — none belongs to a single feature area, and none of the existing units own "is the platform legally and operationally complete" as a concern. Identified by auditing the actual repo (grep across `frontend/src/app` and `backend/src`), not by assumption — see each item's verification note. |
| D-2 | **Build order is fixed**, chosen by SoJo: PHASE-01 settings/profile → PHASE-02 account/data lifecycle (deletion) → PHASE-03 legal/consent → PHASE-04 admin visibility → PHASE-05 error/empty states → PHASE-06 monetization → PHASE-07 pilot-readiness re-verification. | Each phase gives the next one something to build on (e.g. PHASE-01's settings page becomes the natural home for PHASE-02's deletion control and PHASE-03's consent toggle). PHASE-07 is deliberately last — a final confirmation pass once the basics exist, not a blocker to starting this work. |
| D-3 | **PHASE-01 scope = "expose + one new field," not a rebuild.** New: `users.business_name` column (nullable), editable via a new settings page. Reused as-is, read-only for now: `users.display_name` and `users.photo_url` (already populated from Google OAuth — confirmed by reading `backend/src/db/models/users.py`, not assumed). Explicitly deferred, each with a stated reason: profile-photo upload (no upload pipeline needed yet — the Google-sourced photo is enough for a pilot), an HC-level timezone field (no current consumer of it — `clients.timezone` already exists per-client, and Google Calendar events already carry their own timezone; this would be a field nothing reads), notification preferences (nothing real to toggle yet — Unit_004 D-24 already means the HC gets almost no emails). | SoJo's explicit instruction: basic and real, not intricate, but built so later phases can extend it without rework — nullable columns and an additive PATCH endpoint satisfy that without any speculative structure today. |
| D-4 | **New endpoint namespace: `/api/settings/*`, not `/api/me/*`.** | `/api/me/*` is already the client-actor namespace (`ADR-0005 §8`, `backend/src/api/me.py`), and the frontend just locked `/me/*` as the client-facing route prefix (`Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` D-31). Reusing it for the HC's own profile would collide with an actor boundary that's already load-bearing elsewhere. `/api/settings/*` also mirrors the existing frontend `/settings/*` route group (`diet-chart-templates`, `sessions`). |
| D-5 | **Flag, not fix, for PHASE-02**: `users.deleted_at` already exists as a soft-delete column (confirmed in `backend/src/db/models/users.py`). | CLAUDE.md's own architectural principle #8 states deletion must be real, "not soft-deleted with a flag." Whether `deleted_at` today is dead schema, used for something narrower than account deletion, or needs reconciling with a real-delete path is PHASE-02's question to answer — recorded here so it isn't lost before that phase is brainstormed. |
| D-6 | **Flag, not fix, for Unit_004**: `Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` states F3's meal-photo storage is "Supabase Storage (already in stack)," but the only storage client actually wired into the backend is Cloudflare R2 (`backend/src/lib/s3.py`) — confirmed by grepping for both. | Not this spec's problem to fix, and not touched by any PHASE-01–07 work here. Recorded so it doesn't silently ship wrong when Unit_004/F3 is built. |

---

## Goal

Close the gap between "the coach-facing feature set works" and "this is a complete, real product" — the set of things every production platform needs regardless of which features it ships, that got deprioritized while the HC's core workflow was being built. This spec covers seven such gaps: the HC's own account/profile completeness, real account and data deletion (a DPDP obligation, not a convenience), consent capture (schema already exists, nothing uses it), operator/admin visibility, baseline error handling, how Tapas itself gets paid, and a final re-confirmation that the pilot deployment is actually in a known-good state. None of these are user-facing "features" in the product-pitch sense — they're the difference between a demo and something a real HC and their real clients can trust with their data.

---

## Non-goals

- **Any feature already covered by Units 001–004.** This spec does not touch session/MOM workflows, supplement recommendations, the lead-intake pipeline, or client-facing engagement features (action items, diet chart send, chat, meals, calendar).
- **A marketing/landing site.** Terms of Service and Privacy Policy (PHASE-03) are in-app legal pages, not a public marketing presence.
- **A general-purpose RBAC/permissions system.** PHASE-04's admin visibility uses the existing binary `is_operator` flag (`domain/actors.md`) — not a new roles-and-permissions framework.
- **Multi-currency or international billing.** PHASE-06 is scoped to what an India-first, single-currency (INR) product needs.
- **Full design/build of PHASE-02 through PHASE-07.** Only PHASE-01 is designed to implementation-ready detail in this version of the spec. The others are scoped (what, why, order) so the roadmap is visible, but each needs its own brainstorming pass — see Open Questions.

---

## Actors and roles

Cross-reference `domain/actors.md`.

| Actor | Role | What they can do (this spec) |
|---|---|---|
| Health Coach (HC) | Platform's paying user | PHASE-01: view and edit their own business name; view (read-only) their Google-linked identity and email. Later phases: manage their own account deletion (PHASE-02), grant/revoke consent on file (PHASE-03), see billing/subscription status (PHASE-06). |
| Operator (SoJo) | Platform builder, `is_operator` flag on `users` | Not touched by PHASE-01. PHASE-04 gives this actor a real admin surface — today they have DB-only access per `domain/actors.md`. |
| Client | End user being coached | Not touched by PHASE-01. PHASE-03's consent capture and PHASE-02's deletion path both apply to client data as well as HC data, per CLAUDE.md's multi-actor principle — to be detailed when those phases are brainstormed. |

---

## Domain terms

Cross-reference `domain/glossary.md`. New term introduced here (also added to the glossary — see Changelog there):

| Term | Definition |
|---|---|
| **Business name** | The HC's practice/business identity as shown to their clients — distinct from `users.display_name`, which is the HC's personal name as returned by Google OAuth. New in PHASE-01. |

Existing terms this spec relies on without redefining: **Operator / SoJo**, **`is_operator`**, **`audit_log`** (all `domain/actors.md`); **Consent** (schema exists in `backend/src/db/models/compliance.py` as the `consents` table, not yet formally in the glossary — PHASE-03 should add it when that phase is designed).

---

## User stories

- As an HC, I want to set a business name distinct from my personal Google account name, so that my clients and my own settings pages reflect how I actually present my practice.
- As an HC, I want to see which Google account and email I'm signed in with, so that I can confirm my own identity without guessing.
- *(Deferred to later phases, listed for roadmap visibility — not designed yet):* As an HC, I want to delete my account and have my data actually erased (PHASE-02). As an HC, I want to know what my clients have consented to (PHASE-03). As SoJo, I want to see registered HCs and deactivate one if needed (PHASE-04). As an HC, I want a clear error page instead of a broken one (PHASE-05). As an HC, I want to know what I'm paying Tapas and why (PHASE-06).

---

## Flow (PHASE-01 only)

1. HC clicks the single "Settings" item in the top nav, landing on `/settings/profile` inside a Settings hub — a left sidebar (Profile, Onboarding placeholder, Sign out) with the selected section on the right. (Originally shipped as a standalone top-level "Profile" nav item; corrected 2026-08-04 — see PHASE-01 doc §3 for why. `diet-chart-templates` remains a separate top-level page; `sessions` is no longer linked from any nav.)
2. Page loads via `GET /api/settings/profile`: shows an editable **Business name** field (empty if never set), and a read-only block — "Signed in as `[display_name]` via Google, `[email]`."
3. HC edits business name, saves → `PATCH /api/settings/profile` with `{business_name: str | null}`.
4. On success: field re-renders with the saved value; empty string is normalized to `null` server-side (no distinction between "cleared" and "never set").
5. No other write paths in this phase.

---

## Data

| Entity | Read | Write | New fields? |
|---|---|---|---|
| `users` | Y | Y | `business_name: TEXT NULL` — new column, new Alembic migration |

No new tables. `display_name`, `photo_url`, `email` are read-only in this phase (already exist, populated at Google OAuth).

---

## API surface

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/settings/profile` | HC (`require_role('hc')` + `current_tenant()`) | Returns `{business_name, display_name, photo_url, email}` for the authenticated HC. |
| PATCH | `/api/settings/profile` | HC (`require_role('hc')` + `current_tenant()`) | Updates `business_name` only. Empty string normalized to `null`. |

---

## LLM involvement (if any)

None.

---

## Coach-reviewed gate (if applicable)

Not applicable — no AI-generated content in this spec.

---

## Edge cases and failure modes

| Case | Behavior |
|---|---|
| PATCH with `business_name: ""` | Normalized to `null` server-side — no distinction between "explicitly cleared" and "never set." |
| PATCH with `business_name` exceeding a reasonable length (e.g. 200 chars) | 422 — basic length validation, same pattern as other free-text fields in this codebase. |
| Unauthenticated request to either endpoint | 401. |
| Client-role JWT (`role: client`) hits `/api/settings/profile` | 403 or 404 (role mismatch) — never a client can read/write an HC's profile. |
| HC has no `business_name` set yet | `GET` returns `business_name: null`; frontend shows an empty field, not a placeholder default. |

---

## Acceptance criteria

- [x] Alembic migration adds `users.business_name TEXT NULL`; existing rows unaffected (nullable, no default needed)
- [x] `GET /api/settings/profile` returns `business_name`, `display_name`, `photo_url`, `email` for the authenticated HC
- [x] `PATCH /api/settings/profile` updates `business_name`; round-trips correctly on a subsequent GET
- [x] Empty-string PATCH normalizes to `null` in the DB
- [x] Unauthenticated request to either endpoint → 401
- [x] Client-role JWT hitting either endpoint → 403 or 404 (not 200)
- [x] `frontend/src/app/(app)/settings/profile/page.tsx` renders the editable business-name field and the read-only Google-identity block
- [x] Integration tests hit real Postgres per this repo's existing test convention (no DB mocking)

---

## Open questions

- **PHASE-02 through PHASE-07 each need their own brainstorming pass** before a PHASE plan can be written for them — this spec only fixes their order and one-line scope (§0 Decisions log), not their design. — owner: SoJo — by: before each phase's implementation begins, in order.
- **`users.deleted_at`'s current behavior** (D-5) needs to be traced before PHASE-02 is designed — is it read anywhere today, or genuinely dead? — owner: whoever brainstorms PHASE-02 — by: start of that phase's design session.

---

## Out of scope (for this spec, may be future)

- Profile photo upload (PHASE-01 reuses the Google-sourced photo, read-only)
- HC-level timezone setting (no current consumer; revisit if one appears)
- Notification preference toggles (nothing real to configure until later phases add HC-facing emails)
- Full design of PHASE-02–07 (see Open questions)

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-07-14 | Initial draft. PHASE-01 (settings/profile) designed in full; PHASE-02–07 scoped at roadmap level only. | Platform-basics brainstorm with SoJo — closing the gap between "features work" and "this is a complete product," starting from an audited (not assumed) list of what's actually missing. |
| 2026-07-17 | Renumbered from `Unit_005_PlatformFoundations` to `Unit_006_PlatformFoundations`, and moved to its own dedicated branch/worktree (`feature/unit-006-platform-foundations` / `tapas_unit006`). | Discovered `Unit_005` was already claimed by a separate, unrelated Unit (the agnostic macro calculator, `Unit_005_MacroDrivenDietCharts`) that had been created independently. This spec's own numbering had also accidentally leaked, unrenamed, onto three other feature branches via an unrelated rename-task commit — cleaned up as part of this move. |
| 2026-08-03 | PHASE-01 shipped and verified. All 8 acceptance criteria checked off. Implementation went through 3 fix rounds across per-task and final whole-branch review (Pydantic required-field bug, a silent partial-update data-loss bug it exposed, and a missing 401 guard whose justification was factually wrong — see `PHASE-01-hc-settings-profile.md` §3/§4). One Minor finding (stale "Saved" UI indicator) parked, not fixed. | Full implementation cycle via `superpowers:subagent-driven-development`; see `docs/VERIFICATION.md` § Unit_006 PHASE-01 for the verification record. |
| 2026-08-04 | SoJo reviewed the shipped nav and corrected the IA: "Profile" as a standalone top-level nav item (next to "Settings") was wrong — it's a one-time setup screen, and the top nav shouldn't grow one item per settings section. Replaced with a single "Settings" top-nav entry opening a hub (left sidebar: Profile, Onboarding placeholder, Sign out; selected section on the right). Also determined `/settings/sessions` was non-functional as shipped (its "sign out everywhere" only ever revoked the current session, and its device list called backend endpoints that don't exist) — unlinked from all nav, file kept for a possible future real implementation. Flow §1 updated accordingly. | User review of the shipped feature caught a UX/IA miscommunication before it reached real usage — see PHASE-01 doc §3/§7 for the full account. |
| 2026-08-13 | The sidebar's "Onboarding" placeholder is no longer empty: `Unit_003_ClientDiscoveryPipeline` (built independently, on its own branch) had already shipped an equivalent HC one-time-setup page under the unrelated route `/settings/leadgen`, unlinked from any nav — a gap that unit's own PHASE-01 review had flagged but left open. Once both units' branches shared a `main`, SoJo identified the two as the same feature under different names. Unit_003 moved its page into this hub at `/settings/onboarding`, filling this placeholder. No change to this unit's own code — recorded here so this doc doesn't read as if "Onboarding" is still unimplemented. See `Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` §Shared surfaces for the full account. | Cross-unit reconciliation after independent branches converged; keeping this spec truthful about a slot it reserved but didn't itself fill. |
| 2026-08-21 | PHASE-01 (settings/profile) extended, post-ship, to add `first_name`/`last_name` as required, user-editable fields on `SettingsProfileOut`/`SettingsProfilePatch` and the `/settings/profile` form — closing `Unit_003_ClientDiscoveryPipeline`'s "Unit_006 PHASE-01 as a prerequisite" open question and retiring the temporary `backend/scripts/seed_hc_names.py` backfill script. See `PHASE-01-hc-settings-profile.md` § "Post-phase extension" (Tasks 4-6). | `Unit_003_ClientDiscoveryPipeline` Stage 1 depended on these fields being self-service; the interim manual-backfill workaround had no production path. |
