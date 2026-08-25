# Session log

Append-only. Latest at top. Claude writes a new entry at the end of each substantial session.

---

## 2026-08-25 — Unit_003: PHASE-03 shipped, Stages 3-8 redesigned, PHASE-04 shipped

**Branch**: `feature/unit-003-client-discovery-pipeline`

**Done**:
- **PHASE-03** (blood report upload + pre-consultation brief generation) implemented and shipped via `superpowers:subagent-driven-development` — `generate_lead_brief()` LLM orchestration, `GET`/`POST /api/upload/:token*` public token-gated endpoints, the Lead-facing upload page, HC brief-ready/brief-failed notification emails. Commit range `2c04d98..a426574` (2026-08-19). A post-ship review of this phase then found the HC notification email linked to a Lead Detail page (`/leads/:leadId`) that doesn't exist and had no plan to.
- That gap escalated, working through it directly with SoJo, into a full redesign of the pipeline's Stages 3-8 — not a patch. Landed as a rewrite of `SPEC-0001-client-discovery-pipeline.md` (commit `82e066b`, "Decisions log" D-1 through D-7): test recommendation moves from a rule-based keyword engine to an LLM reading the Lead's actual free-text answers (D-4), mandatory HC review-and-single-Send step before anything reaches the Lead (D-5), native Razorpay payment added — HC-owned account, Tapas never merchant of record (D-1/D-2, payment mechanism decided in a separate SoJo planning session and reconciled against `Unit_004_OneStopSpot` F4's existing pattern), payment and scheduling deliberately decoupled with no slot-hold (D-3, confirmed via research that Razorpay has no such primitive), blood-report upload link to get an OTP gate — email now, phone-ready later (D-6), and the AI brief split into two never-conflated artifacts, draft test recommendation vs. pre-consultation brief (D-7). Pipeline grew from six stages to eight.
- **PHASE-04** (Stage 3 of the redesign: AI-drafted test recommendation + HC review/send UI) planned (`3ca0886`) and implemented via the same SDD discipline — 7 tasks, each with a fresh implementer, a task-scoped review (spec + quality), and fix rounds on real findings. Commit range `3772f22..ef17ece`. Notable mid-phase catches: a cross-tenant prompt-poisoning path in `generate_lead_test_recommendation` (HC-user-id not reconciled against the Lead's own, fixed with a one-line check), a dedup regression + an unguarded `PendingRollbackError` on a public endpoint (fixed with rollback-then-retry, independently reproduced against real Postgres), a fabricated precedent citation in a docstring, and a self-scoped migration (`leads.draft_test_recommendation`, `1f2a6c9d4e17`) for a field SPEC-0001 required but no task had scoped.
- **PHASE-04 final whole-phase review** (opus, range `3ca0886..ef17ece`) came back "Ready to merge — With fixes": no Critical findings, but a genuine cross-task composition bug no single task review could see — `GET /api/leads/:id/test-recommendation` never returned the already-sent panel, so reopening the HC review screen after a successful Send re-seeded the editor from the raw AI draft, and a second Send could silently overwrite an already-curated, already-emailed panel. One fix round (commits `65011bc..cf512b7`) closed this plus a missing status guard and five minor issues; an independent scoped re-review confirmed all 7 findings addressed with no new breakage. Backend finished at 506/506 tests passing, frontend `tsc` clean under `src/`.
- Corrected documentation debt the final review surfaced: `docs/domain/glossary.md`'s "Condition-specific add-on" entry still described the retired keyword-matching mechanism (now fixed, plus a new "Draft test recommendation" entry added); `SPEC-0001` had asserted a fix to the Stage 6/7 brief-ready email's dead `/leads/:leadId` CTA that was never actually made in code — that false claim (introduced during the 2026-08-24 redesign) is retracted and the still-live bug is now tracked in Open questions with an owner (PHASE-06); a second real gap (a Lead becomes invisible if the Stage-3 HC review email fails to send, with no list UI or `/remind` endpoint to recover it) is also now tracked there, owner SoJo, decide before PHASE-05. `PHASE-04-*.md`'s own Status/Verification-date fields and post-implementation record (§6-§9) were filled in.
- Live-verified the AI drafting itself works, not just automated tests: submitted a real questionnaire through the actual intake UI (`/intake/nidhi-joshi-5asz8`) describing PCOS-suggestive symptoms and fatigue/cold-intolerance on a vegetarian diet; `leads.draft_test_recommendation` came back with genuinely condition-specific reasoning (LH/FSH/testosterone/fasting insulin for the PCOS-suggestive symptoms, ferritin/B12/Free T4 for the fatigue/vegetarian-diet pattern) — not hardcoded, not keyword-matched.

**Decided**:
- Dispatch-order reversal (Task 4 before Task 3) and other in-flight rulings are recorded in `.superpowers/sdd/PHASE-04-ai-test-recommendation-and-hc-review/progress.md` (workspace deleted after this session per the SDD skill's normal cleanup — the ledger's rulings are preserved here and in PHASE-04's own §6-§9 before deletion).
- Cross-task composition bugs survive individually-clean task reviews — the reopen-then-resend bug is the clearest evidence yet that the SDD skill's final whole-phase review step is load-bearing, not procedural overhead, even on a phase where every task review came back clean.

**Pending / next session**:
- **PHASE-05** (payment + scheduling handoff — native Razorpay, test mode) is the next planned phase per the redesign. Not yet started; needs its own phase-plan doc written first, per this repo's convention.
- Full authenticated live browser click-through of the HC review screen (open → edit → send → reopen → confirm "already sent" state) was not completed this session — no live HC OAuth session was established in Playwright. The reopen-after-send logic specifically was verified instead via real-Postgres-backed integration tests and two independent code reviews. Recommend as the first verification step whenever this flow is next touched.
- Two items now tracked in SPEC-0001's Open questions with owners but not yet actioned: the still-broken Stage 6/7 dead-link CTA (owner PHASE-06) and the Lead-invisible-on-failed-email gap (owner SoJo, decide before PHASE-05 — may argue for a Lead list/detail page before payment work).
- A test Lead ("Priya Verification-Test", `priya.verify@example.com`) exists in the local dev DB from this session's live verification — harmless dev data, left in place, safe to ignore or delete.

**Context the next session needs**:
- `SPEC-0001-client-discovery-pipeline.md` is the current authority for Stages 1-8; do not trust anything in git history before commit `82e066b` for Stage 3 onward, it's superseded.
- PHASE-05's design constraints (native Razorpay test-mode, HC-owned accounts, decoupled pay-then-schedule, no slot-hold) are all locked decisions (D-1/D-2/D-3) from this session, not open for re-litigation without a new SoJo conversation.

**Open questions for SoJo**:
- See `SPEC-0001-client-discovery-pipeline.md` §Open questions for the full list, particularly the two added this session (Stage 6/7 dead CTA owner/timing, Lead-visibility gap and whether it reorders PHASE-05).

---

## 2026-08-19 — Unit_003: committed the onboarding-hub reconciliation; PHASE-03 next

**Branch**: `feature/unit-003-client-discovery-pipeline`

**Done**:
- Found the working tree carrying uncommitted, unlogged work from an earlier (2026-08-13) session: `frontend/src/app/(app)/settings/leadgen/*` staged as a rename into `frontend/src/app/(app)/settings/(hub)/onboarding/`, plus matching unstaged edits to `Unit_003`'s `SPEC-0001` (new "Shared surfaces" section) and `PHASE-01` doc, and two reciprocal edits in `Unit_006_PlatformFoundations`'s `SPEC-0001`/`PHASE-01` docs. All four docs told a coherent, cross-referenced story: Unit_003's HC setup page, shipped unlinked from any nav under `/settings/leadgen` (PHASE-01's own final review had flagged this and left it unresolved), was moved into `Unit_006`'s Settings hub at `/settings/onboarding`, filling a placeholder `Unit_006` had reserved for exactly this. The docs were finished; the commit and session-log entry never happened.
- Verified the move before trusting it: grepped for lingering `settings/leadgen` references (none outside intentionally-historical doc text); ran `npm install` (found `date-fns` declared in `package.json` but missing from `node_modules` — pre-existing gap, unrelated to this change, from the 2026-08-12 merge not being followed by a reinstall) then a clean production build + TypeScript pass, confirming `/settings/onboarding` is a registered route and `/settings/leadgen` is gone; stood up Postgres (docker compose), the FastAPI backend, and the Next.js dev server locally, and did a real Playwright browser walkthrough — `/settings/leadgen` returns a clean Next.js 404, `/settings/onboarding` renders (unconfigured-state view), and clicking the sidebar "Onboarding" link from `/settings/profile` navigates correctly, zero console errors.
- Committed the move + all four doc edits together (`1896095`).

**Decided**:
- Full authenticated-session parity (real OAuth login, configured-leadgen-state render) was not verified live — the access token lives in frontend module memory by design (never `localStorage`, per ADR-0005 §5) and is only populated via a real Google OAuth round trip or the `HttpOnly` refresh cookie set by it; minting a raw refresh token server-side and driving Playwright with it is possible in principle but wasn't done this session, since the unconfigured-state render + real nav-click already gave strong evidence the move itself (file paths, imports, hub wiring) is sound. Flagging this so a future session doesn't assume the fully-configured view was pixel-checked.

**Pending / next session**:
- **PHASE-03 (blood report upload + brief generation)** is the actual next product work — plan is fully written (`PHASE-03-blood-report-upload-and-brief-generation.md`), zero code exists yet (confirmed `backend/src/api/upload.py`, `backend/src/lib/mime_sniff.py`, `backend/prompts/lead_brief.md` all absent). This is where the next session should start implementation, per `superpowers:subagent-driven-development` as the plan doc specifies.
- This branch is still unpushed beyond what was already on `origin` before this session (per the 2026-08-12 entry, 138 commits were local-only as of then) — push remains SoJo's call.
- `date-fns` was missing from `node_modules` despite being in `package.json` — now fixed locally via `npm install`, but worth a beat of attention if a fresh clone/CI run hits the same gap (may indicate `package-lock.json` and `node_modules` drifted, or just that nobody reinstalled after the last `main` merge pulled in the calendar feature).

**Context the next session needs**:
- PHASE-03's plan doc §5 "Source docs consulted" and its 8-task breakdown are ready to execute as-is; no re-planning needed.
- `SYNC_STATUS.md` showed this branch 0 commits behind `main` as of this session's start — no re-sync needed before starting PHASE-03.

---

## 2026-08-12 — Unit_003: main sync, merge conflict resolution, and cross-worktree tooling

**Branch**: `feature/unit-003-client-discovery-pipeline`

**Done**:
- Merged `main` into this branch (137 commits behind at the start of the session) and resolved all 7 conflicts by hand, one at a time, with SoJo: `users.py` (kept both `first_name`/`last_name` and `business_name` — verified dropping the temp columns would have broken `leadgen.py`'s profile-completeness gate, since main's `/settings/profile` has no field to satisfy it), `email.py` (two unrelated functions git had sliced into 4 alternating hunks — kept both whole), `main.py` (router registration, additive), `SESSION_LOG.md` (reordered chronologically, not just concatenated), this file's own `SPEC-0001` (WIP rewrite vs. the parivarthan→tapas rename — no real conflict), and the two `Unit_006_PlatformFoundations` spec files (a rename-detection artifact from an old misfiled `Unit_005_PlatformFoundations` dir — took main's version outright). Merge concluded as `ea7bbc0`.
- Found and fixed a real Alembic multi-head split (`5e8385088f08` vs. `b8cb150db2b2`) that the merge itself gave no error for — two migration chains had independently branched off `97ef9da99879` and were never reconciled. Fixed with an empty merge revision, `4bc4af4` (`77bada58d4b1`), generated via the real `alembic merge` command (not hand-authored) and verified with `alembic heads` before/after.
- Built cross-worktree tooling, live-tested end to end: a `post-merge` git hook (lives once in the shared common `.git/hooks/`, so it's active for all 5 `tapas_*` worktrees automatically) that (a) auto-fetches into every sibling worktree and writes `/mnt/hdd/.../Poshini/SYNC_STATUS.md` with commits-behind-`main` per branch, and (b) checks for Alembic multi-head splits after every merge and prints a loud terminal warning (with the exact heads, filenames, and a ready-to-run fix command) if found — silent otherwise. Neither auto-merges nor auto-fixes; both stay deliberate, attended steps. Added a scoped section to the global `~/.claude/CLAUDE.md` (not this repo's) telling every Claude session to check `SYNC_STATUS.md` at the start of substantive work in a `tapas_*` worktree.
- Mid-session, a peer Claude Code session working in `tapas_unit004` messaged this session directly (first real use of cross-session messaging in this workflow): flagged a real bug in the hook (staleness was compared against `origin/main` instead of local `main`, understating it in the window after a local merge before pushing) — verified and fixed on the spot — and asked about an unrelated uncommitted `docker-compose.yml` edit sitting in its own worktree, which was confirmed not to be from this session.
- Published an HTML field guide (artifact) walking through why each of the 7 conflicts happened and 5 general levers to have fewer of them (sync cadence, claim-before-touch, file splitting, one-table-one-owner, migration branching), plus a correction to an initial hexagonal-architecture proposal: it would not have prevented the `users.py` or Alembic conflicts, since those are data-ownership problems, not application-code-boundary problems.

**Decided**:
- Merge (not rebase) was the right call for syncing this branch — 33 commits were already pushed to origin, and rebasing would have forced a `--force-push` plus per-commit conflict resolution across 102 commits instead of once.
- `.env.example` conflict resolved by adopting main's generic-template convention (worktree-specific values belong in local, gitignored `.env`, which this worktree already had set correctly) rather than keeping unit-003-specific values committed to the template.
- The multi-worktree sync automation stays intentionally "detect + notify" only, never "auto-fix" or "auto-merge" — discussed explicitly with SoJo; an unattended merge risks clobbering uncommitted work or leaving a worktree mid-conflict with nobody there to resolve it.

**Bugs fixed mid-session**: see the Alembic multi-head split and the hook's `origin/main` vs. local `main` staleness bug above — both covered under Done, not repeated here.

**Pending / next session**:
- **Not yet pushed**: this branch is 138 commits ahead of `origin/feature/unit-003-client-discovery-pipeline`, all local. Push is SoJo's call, not done automatically this session.
- **The "claims" mechanism was designed and then deliberately deferred, not just left undone.** Plan: a shared file outside any single worktree (or a dedicated git ref) that every worktree's Claude session checks/writes before touching a shared resource. Two gaps surfaced once the design got specific: (1) a plain shared file is a best-effort convention, not a lock — two sessions could still race on the same check — and (2) any check that lives purely as a `CLAUDE.md` instruction depends on a Claude session actually reading and following it, which this very session demonstrated is not reliable (dropped the standing preflight-block requirement partway through, despite it being a "no exceptions" rule). A `pre-commit` hook that mechanically warns when staged changes touch a flagged shared path (not dependent on a session choosing to comply) was proposed as a partial fix for the second gap — explicitly declined for now. SoJo's call: handle coordination manually until this has actually caused a real collision, rather than build speculative infrastructure for a race that hasn't happened yet.
- **Alembic sync monitoring**: SoJo prefers a separate, periodic (cron-style) check that polls each worktree's actual running Postgres container's applied migration state (`alembic_version`) against the codebase — a different, complementary check to the `post-merge` hook's static file-based head count, and explicitly not something to build this session either. Noted for whenever it's actually wanted.
- **No ADR written yet** for the cross-worktree sync protocol, even though the `post-merge` hook's own header comment references one ("once it's written up as an ADR") — that reference is currently aspirational, not real. Should become `docs/decisions/000X-cross-worktree-sync-protocol.md` per CLAUDE.md §1 rule 14 before this convention is treated as fully locked in.
- The hook lives only in this machine's local `.git/hooks/` (not git-tracked) — won't survive a fresh clone. Fixable later via `core.hooksPath` + a tracked `.githooks/` dir; explicitly deferred this session to avoid scope creep beyond what was asked.
- PHASE-02 (public intake questionnaire + lab recommendation + email) is still the actual next feature work for this unit — untouched this session, which was entirely merge/infra, not product work.

**Context the next session needs**:
- This worktree's Postgres still runs on port 5436 per `.env` (`COMPOSE_PROJECT_NAME=tapas_unit003`) — unchanged by this session.
- `SYNC_STATUS.md` at `/mnt/hdd/yourProjects/OnGoing/Poshini/SYNC_STATUS.md` is the live source of truth for how stale any `tapas_*` branch is relative to `main` — check it before assuming this branch (or any sibling) is current.
- The full reasoning behind the sync-protocol design (why merge over rebase, why detect-only over auto-merge, the file-organization vs. shared-data-ownership distinction) lives in this session's conversation, not yet in a doc — see the ADR gap above.

**Open questions for SoJo**:
- When to build the claims-file mechanism, and which of the two designs (plain external file vs. dedicated git ref) to use.
- When to write the ADR formalizing this session's sync protocol.
- Whether/when to push this branch now that it's synced with main.

---

## 2026-08-04 — Unit_006 PHASE-01: Settings nav corrected to a hub + sidebar

**Done**:
- SoJo reviewed the PHASE-01 nav shipped the day before and flagged it as wrong: "Profile" had been added as a standalone top-level nav item next to "Settings," but business-name setup is a one-time thing an HC won't revisit often, and the top nav shouldn't grow one item per settings section (more are coming — Onboarding, and later PHASE-02/03's sections).
- Restructured to a single "Settings" top-nav entry opening a hub: new `frontend/src/app/(app)/settings/layout.tsx` renders a left sidebar (Profile, Onboarding placeholder, Sign out) with the selected section on the right.
- While discussing the sidebar's "Sign out" placement, traced `/settings/sessions` end-to-end at SoJo's prompting and confirmed it was non-functional as shipped: its "Sign out everywhere" button only revokes the current session (not "everywhere"), and its device-list/revoke UI calls backend endpoints (`GET /api/auth/sessions`, `DELETE /api/auth/sessions/{id}`) that were never implemented. Unlinked it from all nav (file kept for a possible real implementation later); the new sidebar's "Sign out" reuses the same working logout call, correctly labeled.
- Verified live in a browser (not just `tsc`): minted a real access token + refresh-token DB row for the actual dev HC user, drove the running dev server via Playwright — confirmed nav/sidebar active-states, Onboarding placeholder, and a real working sign-out (session revoked, redirected to `/sign-in`).
- Updated `PHASE-01-hc-settings-profile.md` (§2/§3/§7/§8), `SPEC-0001-platform-foundations.md` (Flow §1, Changelog), and `VERIFICATION.md` to record the correction.

**Decided** (link ADRs):
- No ADR changes. New convention recorded in PHASE-01 doc §8: future settings-adjacent phases (PHASE-02 deletion, PHASE-03 consent) get their own sidebar entry in `settings/layout.tsx`'s `SETTINGS_SECTIONS`, not a top-level nav item and not crammed into the Profile page.

**Bugs fixed mid-session**:
- None — this was a design/IA correction, not a bug fix. (The `/settings/sessions` non-functionality was discovered, not caused, this session — it predates PHASE-01.)

**Pending / next session**:
- Same as 2026-08-03's entry: PHASE-02 (account/data deletion) is next per SPEC-0001's fixed build order, needs its own brainstorming pass first. When it's designed, confirm sidebar placement with SoJo as part of that plan, not after building it (see PHASE-01 §7 lesson learned).
- `/settings/sessions` remains an orphaned, unlinked file — no decision yet on whether to build real session management later or delete the stub.

**Context the next session needs**:
- The Settings hub pattern (`frontend/src/app/(app)/settings/layout.tsx`) is the template for adding any future one-time-setup settings section — add to `SETTINGS_SECTIONS`, don't touch the top-level `NAV_LINKS` in `(app)/layout.tsx`.

**Open questions for SoJo**:
- None blocking.

---

## 2026-08-03 — Unit_006 PHASE-01: HC Settings & Profile

**Done**:
- Reformatted `docs/specs/Unit_006_PlatformFoundations/PHASE-01-hc-settings-profile.md` to the required 8-section `template-phase-plan.md` structure (it had been written as a raw implementation plan with no header block or numbered sections). All original Goal/Architecture/Task content preserved, nested under a new `## Implementation plan` section per CLAUDE.md §6's superpowers-output-path override.
- Implemented PHASE-01 via `superpowers:subagent-driven-development`: Task 1 (`users.business_name` nullable column + Alembic migration), Task 2 (`GET`/`PATCH /api/settings/profile`, `claims.sub`-scoped, not `TenantDep`), Task 3 (`/settings/profile` frontend page + nav entry).
- All 8 SPEC-0001 acceptance criteria verified and checked off. Migration confirmed applied to `tapas_dev` directly via `psql` (not just trusted from a migration-tool log).
- Full backend suite: 273 total, 235 passing, 38 pre-existing unrelated failures (missing `pgcrypto` extension on this worktree's `tapas_test`, affects only LLM/MOM-tracking tests — confirmed unrelated by diff/stash comparison, independent grep for `pgcrypto` usage, and re-confirmed by the final review).

**Decided** (link ADRs):
- No new ADRs. Confirmed ADR-0005's `/api/me/*` namespace belongs to the client actor; this phase's `/api/settings/*` is a deliberately separate namespace for the HC's own profile.
- `claims.sub` (not `TenantDep`/`current_tenant()`) is the correct lookup for any endpoint reading/writing the authenticated user's *own* row rather than a tenant-scoped domain resource — new convention recorded in the PHASE-01 doc's §8 Carry-over for PHASE-02 (deletion) and PHASE-03 (consent) to follow.

**Bugs fixed mid-session**:
- Pydantic v2 required-field gap: `SettingsProfilePatch.business_name: str | None = Field(max_length=200)` had no `default=None`, so an empty-body PATCH incorrectly 422'd. Fixed with `default=None`.
- Fixing the above exposed a more serious bug: the handler's unconditional `user.business_name = body.business_name` assignment silently wiped an already-set value to `null` on any partial PATCH omitting the field. Fixed by guarding on `"business_name" in body.model_fields_set`.
- Final whole-branch review caught a missing `if user is None: 401` guard on both handlers — the plan's justification for omitting it ("`require_role` already validated the row exists") was factually wrong; `require_role` only decodes the JWT and never touches the DB. Fixed to match the existing precedent in `backend/src/auth/router.py`.

**Pending / next session**:
- One Minor finding parked, not fixed: the frontend's "Saved" success indicator isn't cleared when the user edits the field again after a save — cosmetic only, no data-integrity/auth impact.
- PHASE-02 (account/data deletion) is next per SPEC-0001's fixed build order (D-2) — needs its own brainstorming pass before a PHASE plan is written. `users.deleted_at` already exists as a soft-delete column and needs tracing (dead schema, or used for something narrower than account deletion?) before that phase is designed (SPEC-0001 Open questions).
- The migration test-coverage gap identified during final review (this worktree's `tapas_test` schema is built via SQLAlchemy `create_all`, not `alembic upgrade` — so migrations are never actually exercised by the test suite, and the plan's claim that they are is wrong) is a unit-level follow-up, out of scope for PHASE-01 itself.

**Context the next session needs**:
- SDD workspace/ledger for this phase: `.superpowers/sdd/PHASE-01-hc-settings-profile/progress.md` — full record of all fix rounds and review verdicts.
- This worktree's Postgres runs on port 5435 (not 5432) — `TEST_DATABASE_URL`/`DATABASE_URL` in `.env` are already correct, but they must be `source`d (with `set -a`) into a fresh shell before running `pytest` directly, since `conftest.py`'s `db_url` fixture reads `os.environ` directly, not via pydantic-settings' dotenv loading.

**Open questions for SoJo**:
- None blocking. PHASE-02 needs a brainstorming session before implementation, per SPEC-0001's own stated process.

---

## 2026-08-02 — Unit_003 Client Discovery Pipeline: PHASE-01 (leadgen data layer & HC setup) shipped

**Branch**: `feature/unit-003-client-discovery-pipeline` (kept as-is per SoJo, not merged/pushed this session)

**Shipped (all 8 tasks, via superpowers:subagent-driven-development, one fresh implementer + reviewer per task):**
- Data layer: `leads`, `lead_questionnaire_responses`, `lead_upload_tokens`, `lead_files`, `hc_leadgen_config` tables (5 new tables, one migration chain, verified linear/single-head, verified schema-identical on both `tapas_dev` and `tapas_test`).
- Temporary `users.first_name`/`last_name` columns (conceptually owned by `Unit_006_PlatformFoundations`, not yet built) — explicitly flagged in the migration docstring and PHASE-01's Global Constraints as a cross-branch merge collision risk for whoever merges second.
- Three endpoints in `backend/src/api/leadgen.py`: `POST /api/leadgen/config/init` (slug generation, profile-incomplete/already-configured guards), `GET /api/leadgen/config`, `PATCH /api/leadgen/config` (fixed-question protection, tenant-scoped).
- `backend/scripts/seed_hc_names.py` — temporary manual backfill script, ahead of Unit_006's real settings UI. Run against a dummy pilot HC (`joshichi.nidhi@gmail.com` / Nidhi Joshi — explicitly confirmed dummy/test data) in this worktree's `tapas_dev`.
- Frontend `/settings/leadgen` page (Setup / Intake Form / Test Panel tabs), verified with a real in-browser Playwright walkthrough (not just typecheck/build) against live backend + Postgres, per this repo's UI-verification rule.

**Bugs found and fixed during execution (6 total, across per-task review + final whole-branch review):**
- Task 2: migration was applied to `tapas_dev` but silently never reached `tapas_test` (wrong env var — `alembic/env.py` only reads `DATABASE_URL`, not `TEST_DATABASE_URL` as its own var). Caught because `tests/integration/conftest.py` builds the test schema via `Base.metadata.create_all`, not Alembic, so pytest alone would have masked this drift indefinitely.
- Task 5: `POST /config/init`'s slug-collision retry loop misdiagnosed a concurrent `hc_user_id` race as a slug collision, returning a misleading 500 instead of 409 `already_configured`. SoJo approved the fix explicitly (plan-mandated code, flagged as a plan-vs-finding conflict rather than silently fixed).
- Task 7: `_validate_questionnaire_keeps_fixed_questions`'s `removable: true` rejection branch had zero test coverage (brief only specified the "missing key" test case).
- Final review (I-1): PATCH didn't enforce D-1's "no retyping a fixed question" rule — only checked key-presence/`removable`, not `type`/`required`/`text`.
- Final review (I-2): explicit `null` on NOT-NULL scalar PATCH fields caused a raw 500 instead of 422.
- Final review (I-3) + regression (N-1) caught in the fix wave's own re-review: `questionnaire` was untyped `list[dict]` server-side (malformed entries silently persisted, later breaking the frontend's stricter Zod parse with no error surfaced — `page.tsx` had no `.catch()`); the fix for I-3 combined with the *pre-existing* lack of a null-guard on `questionnaire`/`test_panel` (both NOT NULL JSONB columns) meant `PATCH {"questionnaire": null}` would silently corrupt a row — JSONB `null` satisfies a SQL `NOT NULL` constraint, so the write committed, then every later GET/PATCH on that row 500'd trying to serialize it back out, with no API-level recovery path. Closed with one more approved fix round (extended the same null-guard to both JSONB fields), verified via counterfactual + mutation-tested regression tests.

**Decided**:
- Confirmed with SoJo (see prior conversation turn): PHASE docs are written and executed one sprint at a time (design → implement → design next), not all upfront — matches this repo's own CLAUDE.md §6 convention and Unit_001's actual commit history.
- This worktree's `.env` JWT keys were placeholders (blocking any real login/JWT-issuance testing). Copied the real dev ES256 keypair from `tapas_unit004`'s `.env` (JWT signing keys aren't meant to be per-worktree) — `.env` confirmed gitignored, never committed.

**Pending / next session**:
- PHASE-02 (public intake questionnaire + lab recommendation + email) is next, per SPEC-0001's Stage 2-3 — not started.
- `/settings/leadgen` is not yet reachable from any in-app nav (`frontend/src/app/(app)/layout.tsx` has no settings sub-nav yet) — flagged by final review as a real but non-blocking gap.
- Minor deferred items (see final commit `d75d402` and the now-deleted SDD ledger, summarized): `seed_hc_names.py` doesn't dispose its DB engine on the user-not-found error path; no PATCH-specific cross-tenant isolation test (GET has one); `LeadgenConfigPatch` has no `extra="forbid"`; hardcoded `tapas.app` intake-link display string should eventually source from config (also: SPEC-0001 Stages 2-4 still say `parivarthan.app`, inconsistent with the Tapas rename — not touched this session).
- The Unit_006/cross-branch `users.first_name`/`last_name` collision risk (see PHASE-01 Global Constraints, now committed) still needs SoJo to actively coordinate at merge time — not resolvable from within this branch alone.

**Context the next session needs**:
- This worktree's Postgres runs on port 5436 (`docker-compose.yml` project `tapas_unit003`) — always run `scripts/db-check.sh` first. `tapas_test` needs `TEST_DATABASE_URL` exported explicitly before `pytest` (conftest.py reads `os.environ` directly; `.env` isn't auto-sourced into the shell).
- Full backend suite: 286 passed. Frontend: clean build, `/settings/leadgen` included.

**Open questions for SoJo**:
- None blocking. The Unit_006 merge-coordination risk above is the one item that needs your active attention, not Claude's — timing depends on Unit_006's own roadmap.
---

## 2026-07-14 — Platform rename: Parivarthan → Tapas (docs sweep)

**Done**:
- Platform renamed from Parivarthan to Tapas (2026-07-14) — see `docs/decisions/0008-platform-rename-parivarthan-to-tapas.md`. Renamed throughout `docs/` and `prompts/`, including historical session logs and handover docs, per SoJo's decision to favor consistency over preserving the old name in history.

---

## 2026-07-12 — Custom domain (app.tapas.fitness) via Cloudflare Worker

**Done**:
- Bought `tapas.fitness` at Porkbun, pointed nameservers at Cloudflare, DNS `CNAME app → hc-platform-frontend-296472807958.asia-south1.run.app` (proxied).
- Diagnosed `app.tapas.fitness` 404: Cloudflare proxies correctly but forwards the original `Host: app.tapas.fitness` header; Cloud Run's front door routes purely by Host header and doesn't recognize it.
- Ruled out (verified live, not assumed) both "native" fixes: Cloudflare Origin Rules Host-header override is Enterprise-plan only; Cloud Run's native Domain Mapping doesn't support `asia-south1`.
- Added `cloudflare/domain-proxy/` (`wrangler.toml` + `worker.js`) — a version-controlled Cloudflare Worker that reverse-proxies `app.tapas.fitness` to `hc-platform-frontend`, rewriting the Host header. Deployed via `npx wrangler deploy`. Verified stable (8/8 requests returning real Next.js content, not the Google 404).
- Confirmed 6 `redirect_uri` call sites in `backend/src/auth/router.py` (HC login, Calendar connect/callback, Client invite login) all build from the single `settings.api_base_url` — one secret change moves all of them.
- Google Cloud Console updated: `tapas.fitness` added to Authorized domains; all 3 new redirect URIs added; old `.run.app` URIs kept during transition.
- Rotated `API_BASE_URL`/`FRONTEND_URL` GCP secrets to `https://app.tapas.fitness`, forced new `hc-platform-backend` revision (`hc-platform-backend-00013-29l`). One real user was already signed in via the old `.run.app` URL at cutover time — assessed and confirmed unaffected (cookie already set on the old origin, normal usage doesn't depend on these secrets); full risk assessment + rollback commands documented in ADR-0009 "Cutover risk notes and rollback."
- Verified post-cutover: CORS allows `https://app.tapas.fitness`, `redirect_uri` correctly builds to the custom domain across all 3 OAuth flows, old `.run.app` frontend still serves 200 (existing session unaffected), scheduler endpoint (bypasses BFF/domain entirely) unaffected.
- SoJo confirmed full real-browser sign-in (Google OAuth end-to-end, session persists, mock data visible after reload) working on **Firefox and Chrome**. Safari still pending — SoJo to check later. Note: Firefox was the higher-priority browser here (Total Cookie Protection was the actual failure mode ADR-0005's BFF proxy exists to fix); Chrome largely masked the original bug even pre-migration.
- Non-issue investigated and closed: SoJo's desktop Chrome autocompleted `app.tapas.fitness` → bare `tapas.fitness` (Porkbun parking page) in the address bar. Confirmed server-side via curl this was not a redirect or routing bug (both hostnames return independent 200s, no server-side link between them); confirmed via Incognito window it was local Chrome address-bar history/autocomplete on that one profile, not an infra issue.

**Decided** (link ADRs):
- **ADR-0009 (new)**: Cloudflare Worker chosen over Cloudflare Origin Rules (Enterprise-only), Cloud Run native Domain Mapping (unsupported region), and a GCP Load Balancer + Serverless NEG (cost, ~$18+/mo not justified at pilot scale). Firebase Hosting (previously the documented plan in `PHASE-09-pilot-smoke-gate.md` §B.7) also considered and not chosen — superseded, corrective note added there.
- **ADR-0005 amended**: `API_BASE_URL`/`FRONTEND_URL` now `https://app.tapas.fitness` (was raw Cloud Run URL) — mechanism (BFF proxy, cookies, CORS) unchanged, only the hostname.
- `docs/diagrams/0001-system-architecture.md` updated (Cloudflare Worker layer added, line-151 WAF/rate-limiting placeholder resolved — still not configured, flagged as a real gap, not solved by this Worker).
- `docs/ops/deployment.md` and `docs/ops/secrets-management.md` corrected (both still described the retired Cloudflare Pages / Cloudflare Secrets model from before the Cloud Run migration; secrets-management.md full rewrite still flagged as an out-of-scope follow-up beyond the two rows touched here).

**Pending / next session**:
- Safari sign-in check — SoJo to do when convenient. Firefox + Chrome already confirmed working end-to-end.
- Old `.run.app` OAuth redirect URIs: keep during transition, remove only after Safari is also confirmed (and ideally a few days of stability).
- Found but not fixed: `.github/workflows/deploy.yml` deploys a differently-named, seemingly-orphaned Cloud Run service (`parivarthan-api`, not `hc-platform-backend`) — pushing to `main` does not reliably redeploy the real backend service. Flagged for a separate follow-up.

**Context the next session needs**:
- Worker deploy is manual (`cd cloudflare/domain-proxy && npx wrangler login && npx wrangler deploy`), not yet CI-automated.
- Cloudflare account already authenticated locally via `wrangler login` (OAuth token present) — no fresh login needed for future Worker redeploys on this machine.

**Open questions for SoJo**:
- None blocking. Cloudflare Workers' 100k req/day free-tier ceiling is a future trigger to revisit (ADR-0009 "Things to revisit"), not a current concern at pilot scale.

---

## 2026-07-06/07-10 — Unit_004 One Stop Spot: spec rebuild + PHASE-01/01c/01d shipped

**Branch**: `feature/unit-004-one-stop-spot` (reused fresh off `main` per phase, merged locally after each; not pushed to `origin`)

**Spec work:**
- `docs/specs/Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` fully re-brainstormed from scratch, grounded against actual code (not the original stale draft). Resolved a real architectural conflict: original draft assumed a never-expiring client URL-token model (D-5/D-7); codebase already had Google OAuth + client-JWT auth built (`ADR-0005 §8`, `backend/src/api/me.py`) — OAuth model confirmed as source of truth (D-14).
- F1 (client-facing send after session) redefined: client never sees the Session Review/MOM verbatim, only finalized action items + a short HC-composed message (D-10–D-13). Single-button Freeze→Send pattern, corrected mid-build after an unjustified two-button Save/Freeze split was caught (D-29).
- F8 (diet chart client view) added: snapshot-on-Send model, working chart stays mutable and private (D-16–D-19).
- F2/F3 restructured to 2-tab client detail (Summary, Chat) with three filtered views inside Chat (D-20 supersedes earlier 3-tab D-6); check-in storage extended not duplicated (D-21); notification model made cross-cutting (D-24): HC never proactively pinged, client always emailed on HC action.
- F6 (meeting link) locked in HC-side only, scoped XS, no third-party API — free-text `meeting_url` field.
- Diagrams: `docs/diagrams/0004-client-facing-flow.md` (flowchart + sequence + ER), documenting the auth-model resolution.
- Committed: `d82a8a7` "docs(unit-004): add PHASE-01 spec/plan and client-facing flow diagram."

**Shipped and merged to `main`:**
- **PHASE-01** — action items delivery. `moms.action_items_draft` JSONB, `POST /mom/freeze` (all-or-nothing validation), `POST /mom/send` repurposed to require `{"message": str}` + `reviewed` status, emails real `ActionItem` rows via new `backend/src/lib/email.py` (Resend). Frontend: structured action-items editor, single Save button gated by `window.confirm()`.
- **PHASE-01c** — diet chart send. New `DietChartSend` model + `POST /api/clients/{client_id}/diet-chart/send`, reuses existing chart helpers unchanged. Frontend: Send-to-client button + confirm dialog.
- **PHASE-01d** — meeting link (HC-side). `sessions.meeting_url` field, New-session form field, live-editable Join-call button on session detail.

**Bugs found and fixed during TDD execution (9 total, incl. 2 only visible at final whole-branch review):**
- Freeze endpoint could 500 on bad `action_items_draft` items — added all-or-nothing validation (user confirmed this should fail clean, not silently).
- Lost `disabled={!sessionReviewText.trim()}` guard on Save (regression from MomTab rewrite) — restored.
- Email subject line built from HTML-escaped names, corrupting real inbox display (e.g. `D&#x27;Souza`) — fixed to use raw values in the header.
- Migration for `diet_chart_sends` relied on import-order side effect instead of an explicit `postgresql` dialect import — fixed to match repo convention.
- Diet-chart-send success message could be hidden by a later failed send (shared conditional) — rendered independently.
- Meeting-link Cancel button had no in-flight-save guard, race could silently apply a "cancelled" edit — added `disabled={savingLink}`.
- **Whole-branch review only**: `draft_mom` had no status guard, allowing redraft-after-freeze to duplicate `ActionItem` rows and bypass the "no resend" guarantee — fixed with a 409 guard. No UI path existed to send an already-frozen-but-unsent review after a page reload — added conditional Send button.

**Open / carried forward:**
- Google Calendar/Meet API integration for F6 — discussed but **not resolved or documented yet**. Proposed direction: narrow date-scoped event picker tied to the session's `scheduled_at`, storing a direct Calendar-event reference (not a full calendar view/iframe). Awaiting confirmation this matches what was pictured.
- OQ-7 (client-facing route scheme) still open — blocks PHASE-02 (client portal + Chat tab).
- `main` is ahead of `origin/main` and has not been pushed (not requested).
- Preflight discipline lapsed twice this session (once mid-brainstorm, once after a long subagent-orchestration stretch) — both called out directly by SoJo; pattern and fix logged in memory (`feedback_always_preflight.md`).

---

## 2026-07-08 — Macro Calc Realm: Unit_005 created, agnostic macro calculator spec'd

**No code changes — brainstorm + spec only.** Done on `feature/unit-004-one-stop-spot` (pre-existing branch); this is Unit_005 work, not Unit_004 — flagged as an open item below.

**What happened:**
- Brainstormed a fully formula-agnostic macro calculator (protein/carbs/fat/fibre/kcal) as a deliberate niche differentiator — most competitor HC platforms hardcode a fixed formula dropdown (Mifflin-St Jeor, Katch-McArdle, etc.); this lets each HC define, name, and reuse their own method instead.
- Discovered mid-brainstorm the feature's real size: SoJo's intent is a 3-part pipeline — **Part A** Macro Calculator (this spec), **Part B** Recipe/Food Macro Library, **Part C** Wiring targets + library into the diet chart. Only Part A was designed this session; B and C are intentionally stubbed as future specs, not invented.
- Verified (not assumed) two things by reading actual code/specs before designing around them: (1) `clients.health_metrics` and `clients.demographics` are both freeform, unenforced shapes — not reliable formula inputs as-is; (2) Unit_003 (Client Discovery Pipeline), even fully built, never persists structured biometric data — everything lands as free-text questionnaire responses or a narrative LLM brief. Conclusion: neither is a workaround-until-Unit_003-ships problem — dedicated structured fields are the correct permanent architecture.
- Landed on extending the **existing gear-icon Demographics panel** (`clients/[clientId]/page.tsx` → `DemographicsForm`) with 7 new keys — `weight`, `target_weight`, `height`, `waist`, `hip`, `neck`, `activity_level` — reusing existing `dob`→age and `gender`. No migration needed (same `EncryptedJSON` `demographics` column).
- Locked: no branching/conditional formula logic, but formulas **can chain** (reference earlier-computed named values, e.g. BMR → TDEE → macros) — this is what makes real-world layered methods expressible without duplicating arithmetic four times.
- New Unit created: `Unit_005_MacroDrivenDietCharts`. Wrote `SPEC-0001-agnostic-macro-calculator.md` (Part A only, all 16 template sections, self-reviewed for placeholders/consistency — one inconsistency found and fixed: Actors table wrongly implied targets are HC-editable, corrected to read-only/recompute-only). Added 5 new terms to `docs/domain/glossary.md`.
- New data model (not yet migrated — spec only): `macro_formula_presets` (HC's reusable named formula sets), `client_macro_targets` (one current computed target per client, no history in v1).

**Open items / follow-ups:**
- This work happened on the `feature/unit-004-one-stop-spot` branch — consider a dedicated `feature/unit-005-*` branch before implementation starts.
- SoJo to review `Unit_005_MacroDrivenDietCharts/SPEC-0001-agnostic-macro-calculator.md` before it moves to a PHASE plan / implementation.
- Open questions logged in the spec itself: formula-authoring UI mechanism (expression bar vs. chip-builder), and whether `client_macro_targets` needs history/versioning post-pilot.
- Part B (Recipe/Food Macro Library — likely IFCT-anchored, licensing unverified) and Part C (Wiring) not yet brainstormed.

---

## 2026-06-30/07-01 — P11 amendment + merge; P12 scoping

**Branch**: `feature/unit-001-phase-12-google-calendar-dashboard` (created, empty)

**P11 amendment (4 commits on top of original P11):**
- `d820035` — Health Metrics card: `target` field added; 3-col table (Metric | Current | Target); fixed height, "▼ Show all N" overflow popover; Target input in edit mode
- `744d516` — Dashboard client cards: circles (`w-16 h-16`) to right of client name; current/target display; unit once in label below circle
- `e45c990` — Fix: null-safe `target` schema (`.nullish().transform`); `useCallback` for popover `onClose`; corrected overflow button label
- `aef02d2` — `--color-section-fill-03: #DFE3E6` added to `tokens.generated.css` (was missing — Goal card and Diet chart had no fill); sheet backdrop blur removed; slide-over polish (`bg-section-fill-03`, `px-5` inset, `space-y-2` fields, `bg-background/80` inputs); circles `bg-section-fill-03` fill

**P11 merged to main** — `72c5327`, 55/55 tests green, P11 branch deleted.

**P12 scoping discussed:**
- Scope: Google Calendar integration for HC + dashboard redesign to show HC's schedule
- Pilot HC confirmed to use Google Calendar and is looking forward to this feature
- Technical approach agreed: OAuth 2.0 → Calendar API (on-demand fetch for MVP) → dashboard "Today" strip with events matched to clients
- Open question before speccing: how does pilot HC name her calendar events (affects client-matching heuristic)
- No spec or implementation started — discussion only

**Open items carried forward:**
- Reseed mock data with P11 fields (`health_metrics`, `demographics`) — scripts at `backend/scripts/mock_p6/`
- `health_metrics` encryption deferred (ADR-0007 §Consequences)
- `a1b2c3d4e5f6` Alembic revision ID is hand-typed (minor hygiene, non-blocking)

---

## 2026-06-30 — Phase 10 fixes + Phase 11: Client Profile and Health Metrics

**Branch**: `feature/unit-001-phase-11-client-profile-and-health-metrics` (ready to merge to `main`)

**Phase 10 fixes landed in this session:**
- `bg-section-fill-01` applied to Sessions + Open Items cards (replaced incorrect white)
- Dashboard grid: `grid-cols-3` → `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` (responsive)
- Journey stage: editable `<select>` on client detail page + backend `PATCH /api/clients/{id}` for `journey_stage`
- Session Notes (tab): Save/Edit freeze pattern writing to `notes_internal`
- Session Review tab (was "MOM editor"): single textarea, AI generation, Save/Edit freeze, "Send to client" button removed, `draftMom` now reads from `notes_internal` not `session_notes`
- Three-colour card system: introduced `section_fill_03` token (`#DFE3E6`) for Goal + Diet chart cards; `section_fill_01` for Sessions/Open Items, `section_fill_02` for Supplements/Details

**Phase 11 built:**
- **Gear icon → demographics Sheet**: 8 optional demographic fields (DOB, gender, city, occupation, medical conditions, allergies, medications, emergency contact) in a slide-over. Only non-empty fields render in Details card.
- **Health Metrics card**: HC defines custom metrics (name/value/unit), max 3 flagged for roster display. Save/Edit freeze pattern. Sits at 70% alongside Goal card (30%).
- **Roster card**: up to 3 `display_on_card` metrics shown below stage badge on each client tile.
- **Backend**: `demographics TEXT` (encrypted) + `health_metrics JSONB NOT NULL DEFAULT '[]'` columns on `clients`; Alembic migration; `PatchClientInput` + `ClientOut` + `ClientCreate` updated; max-3 validator.
- **ADR-0007**: app-layer Fernet encryption for `demographics` column (DPDP / CLAUDE.md §9.5).

**Security:** `demographics` PII (medical conditions, allergies, medications) encrypted at rest via SQLAlchemy `EncryptedJSON` TypeDecorator (Fernet AES-128-CBC + HMAC). Column is `TEXT` at DB layer; Python/Pydantic layer sees `dict[str, str] | None` transparently. Key: `DEMOGRAPHICS_ENCRYPTION_KEY` env var.

**Commits on branch (9 total):**
- `2bf190e` spec, `90197e7` backend, `0c0ce3f` frontend API, `2b701f7` client detail page, `04a39ce` roster metrics, `61bf782` review fixes, `808cbbb` ADR-0007, `cb68a65` encryption, `e01f318` decrypt logging + Cancel state

**Open items / follow-ups:**
- Reseed mock data for P11 (mock scripts at `backend/scripts/mock_p6/` still target local Postgres `tapas_dev` — data is intact)
- `health_metrics` encryption deferred (ADR-0007 §Consequences — client-side filter would break if encrypted)
- KMS migration when platform crosses regulatory audit or 10k data principals
- `h` column (Alembic revision ID `a1b2c3d4e5f6` is hand-typed not auto-generated — minor hygiene, non-breaking)

---

## 2026-06-24/25 — P9 Part B: Cross-browser auth fix + production verification + mock data migration

**Done**:

- **Root cause: sign-in loop in Firefox and Safari** — `run.app` is in the Public Suffix List. Frontend (`hc-platform-frontend-*.run.app`) and backend (`hc-platform-backend-*.run.app`) are cross-site, not same-site. Firefox Total Cookie Protection (dFPI) and Safari ITP block third-party cookies. ADR-0005 §5 assumed same-eTLD+1 — assumption was silently violated when deployment moved from Cloudflare Pages+Workers to GCP Cloud Run.

- **Fix: BFF proxy** — `frontend/src/app/api/[...path]/route.ts` — Next.js 16 catch-all Route Handler proxies all `/api/*` browser requests server-to-server to the FastAPI backend. For OAuth callback (`302 + Set-Cookie`): intercepts the redirect, re-emits `Set-Cookie` on the frontend domain. All browser requests are now same-origin. Cookie is first-party in all browsers.

- **Supporting config changes**:
  - `frontend/src/lib/config.ts`: `API_URL = ""` — all browser fetches are relative (no cross-origin calls)
  - Secret Manager `API_BASE_URL` → frontend URL — backend now sends Google's `redirect_uri` to the frontend BFF, not directly to itself
  - Google OAuth Console: frontend URL added as authorized redirect URI
  - Backend redeployed to pick up new `API_BASE_URL`

- **Second bug: `new URL()` silent failure** — When `API_URL = ""`, `new URL("/api/sessions")` throws `TypeError: Invalid URL` (requires absolute URL). All four list-with-filters functions were silently failing: `listSessions`, `listClients`, `listActionItems`, `listClientCheckIns`. Error was swallowed by error boundaries → empty data. Fixed in all four files by replacing `new URL()` with `URLSearchParams` + string concat. Bug only visible in browser Console tab, not Cloud Run logs.

- **Mock data migration** — Local dev Postgres (Docker) had 3 clients, 17 sessions, 17 MOMs, 17 briefs, 28 action items, 10 diet charts, 16 HC style snippets, 4 content assignments, 1 client file. Supabase was schema-only. Migrated via `pg_dump --data-only --inserts`, UUID substitution (local HC `26e57b28` → Supabase HC `38ff56d2`), `SET session_replication_role = replica` for FK bypass, `psql` restore. All 150 rows landed cleanly.

- **Documentation updated**: `docs/decisions/0005-auth-strategy.md` (Amendment 2026-06-24 section), `docs/diagrams/0001-system-architecture.md` (BFF proxy layer, new request flow examples), `PHASE-09` §4 bugs + §7 lessons (v1.5 and v1.6).

**Current production state**:
- Frontend: `hc-platform-frontend-00006-h65` — BFF proxy live, all list endpoints fixed
- Backend: `hc-platform-backend-00007-sdb` — using frontend URL for `redirect_uri`
- Auth: working in Chrome; Firefox and Safari unverified in browser (logs confirm sign-in and dashboard load)
- Data: mock HC data (3 clients, 17 sessions, diet charts, etc.) live in Supabase
- Pending push: `fix(frontend): replace new URL() with URLSearchParams` — committed locally, not yet pushed (HTTPS remote requires credentials)

**Open items**:
- Verify sign-in in Firefox and Safari explicitly (browser test, not just logs)
- Push the `new URL` fix commit to trigger Cloud Build frontend redeploy
- `PKCE state store` (`_state_store: dict` in `router.py`) is in-memory — multi-instance unsafe on Cloud Run scale-to-zero. Low risk at pilot scale.
- `SameSite=None` → `SameSite=Lax` cleanup in backend cookie (all requests are now same-site via proxy; `Lax` is more secure — safe to change once Firefox/Safari confirmed)
- CSRF double-submit cookie (ADR-0005 §6) — still not implemented

**Next**: Feature building — begin P10 or new unit. Product focus: trust and robustness.

---

## 2026-06-23 — P9 Part A: Cloud Run deployment, CI/CD, secrets, infra debugging

**Done**:

- **Cloud Run deployment** — Service `hc-platform` live at `https://hc-platform-296472807958.asia-south1.run.app`, region `asia-south1`, project `t-replica-361407`. Ingress: all users. App handles its own auth (no Cloud Run IAM gate).

- **CI/CD via Cloud Build** — Auto-created trigger (from GCP "Connect to repo") originally used buildpacks which cannot build Python/uv projects. Fixed by adding `cloudbuild.yaml` at repo root with three steps: `docker build ./backend`, push to Artifact Registry, `gcloud run services update hc-platform` with all 15 `--update-secrets` flags. Trigger updated to use this file. Push to `main` now auto-deploys. GitHub Actions is NOT in use — `.github/workflows/deploy.yml` deploys to deleted service `tapas-api` and is dead code.

- **`/healthz` → `/health` rename** — Discovered `/healthz` is intercepted by GFE (Google Frontend) layer at the infrastructure level (Kubernetes reserved path) and never reaches the container. Renamed route to `/health` in `backend/src/main.py`. Confirmed: `/` and `/health` reach FastAPI; `/healthz` returns Google HTML 404 from GFE.

- **All 15 secrets mounted** — Secrets created in Secret Manager earlier; were not mounted on the service. Fixed via `gcloud run services update --update-secrets=...`. Also added all `--update-secrets` flags to `cloudbuild.yaml` deploy step so future CI deploys keep them.

- **Sentry startup crash fixed** — With real secrets mounted, `SENTRY_DSN` placeholder value (`XXXXXXX`) passed the `if not dsn: return` guard but failed Sentry SDK's `Dsn` parser (`BadDsn: Invalid project in DSN`), crashing the container lifespan. Fixed by wrapping `sentry_sdk.init()` in `try/except Exception: pass` in `backend/src/telemetry/sentry.py`. App now starts regardless of DSN value. **Sentry is still not reporting errors** — DSN needs a real value (see open items).

- **Technical rundown created** — `docs/technical-rundown.html` — dark-themed reference doc covering full tech stack, all API routes, auth flows, 6 HC usage scenarios, known infra traps, open items.

- **PHASE-09 updated to v1.1** — Part A as-built record documented, GitHub Actions approach superseded, bugs-fixed table filled in, lessons learned written, Task 1 checklist updated with done/blocked status.

**Infra traps discovered** (logged in PHASE-09 §7 and `docs/technical-rundown.html`):
- `/healthz` is GFE-reserved; `/health` is the correct path
- Cloud Build trigger region is always "global" (not a problem — outputs still go to asia-south1)
- `gcloud run services logs read` crashes the CLI (bug); workaround: `gcloud logging read`
- Buildpacks cannot build Python/uv projects — always need `cloudbuild.yaml` with Docker

**Current live state**:
- Revision: `hc-platform-00007-78m` (healthy, 100% traffic)
- Secrets: all 15 mounted
- CI/CD: working

**Open items before Part B (smoke gate) can run**:
1. **DB** — `DATABASE_URL` secret must point to a real Supabase instance; `alembic upgrade head` must be run
2. **Sentry** — need a real project DSN; update `SENTRY_DSN` secret
3. **`FRONTEND_URL`** — update once frontend is hosted
4. **`SENTRY_DSN`** — currently silently swallowed; errors invisible in prod

**Next**: DB provisioning (Supabase ap-south-1), then frontend hosting, then return to P9 Part B smoke gate.

---

## 2026-06-16 — P7 + P8: External Scheduler + Observability Live

**Done**:

- **P7 — External Scheduler** (4 commits): `POST /internal/scheduled-tasks` endpoint authenticated by `X-Scheduler-Token`; snippet retirement sweep using `COALESCE(last_used_at, created_at) < now() - 180 days`; idempotent (`retired_at IS NULL` guard); structured log `event=scheduled_task_run`; GitHub Actions cron (01:00 UTC daily, `workflow_dispatch` for manual trigger); `scheduler_secret` setting added to `Settings` + `.env.example`. 9 unit tests (TDD). AC4/AC5 (DB-level retirement) deferred to P9.

- **P8 — Observability Live** (2 commits): `request_id_middleware` enhanced to emit `request.start` (method, path, ip, ua) and `request.end` (status, ms) JSON log lines on every HTTP request; `sentry_sdk.set_tag("request_id", ...)` wired so Sentry errors correlate with Cloudflare log lines via UUID; 3 unit tests added (capsys stdout capture). Sentry alert rules documented in `docs/ops/incident-response.md`. AC4 (Sentry smoke test) and AC5 (5 SQL queries vs populated DB) deferred to P9 where production DSN and pilot data will be available.

- **Housekeeping**: `pyproject.toml` gained `pythonpath = ["."]` so `pytest tests/unit/` works without `PYTHONPATH` prefix.

**Test count**: 52 (P6 baseline) → 66 (P8 end): +2 config, +9 scheduler, +3 request logging.

**Next**: P9 — Pre-Pilot Smoke Gate. Covers: production Worker against real RDS Mumbai + OpenRouter + S3, Cloudflare platform config (rate limiting, WAF), Sentry smoke test (AC4), SQL queries vs pilot data (AC5), DPDP deletion test, pilot HC onboarding.

---

## 2026-05-12 — P6C: Diet Chart Feature (full implementation)

**Done**:

- **P6C spec written** (commit `02ab7d0`): PHASE-06-frontend.md Part C filled in — design decisions, data model (JSONB `parameters`, `content_assignments` link), 6 backend endpoints, LLM generation + fallback spec, 3 frontend surfaces, MOM integration, acceptance criteria, implementation plan (C.10).
- **Task 1** (commit `3de979a`): `backend/src/api/diet_charts.py` — 6 endpoints (template upload/list/delete + client chart get/generate/patch); `_parse_csv_bytes` CSV parser; 7 unit tests — TDD (red→green verified). Router registered in `main.py`.
- **Task 2** (commit `4902f11`): `backend/prompts/diet_chart_generate_v1.md` prompt; `backend/src/llm_service/schemas/diet_chart.py` (`DietChartGridSchema`); `backend/src/llm_service/diet_chart_generate.py` — full LLM generation following `generate_mom_draft` pattern, with structured fallback (warn log + Sentry + `generation_status: "fallback"`); 6 unit tests. MOM integration: `__init__.py` now appends "A diet chart has been prepared for this client." to `user_message` when an active chart exists.
- **Task 3** (commit `968b55e`): `frontend/src/lib/api/dietCharts.ts` API client (6 functions, Zod v4 schemas); `/settings/diet-chart-templates` page (upload + library list); `/clients/[clientId]/diet-chart` full editor (7-day grid, inline cell editing, add meal slot column, generate/regenerate, fallback amber banner, save); client detail page updated with diet chart 2-day preview section + "Edit chart →" / "Generate →" link.

**Test count**: backend 45 unit tests + 43 frontend Vitest tests, all green.

**Bug fixed in plan**: BOM test used `"\xef\xbb\xbf".encode()` (Python string escape → multi-byte UTF-8), not actual BOM bytes. Fixed to `b'\xef\xbb\xbf' + content.encode("utf-8")`.

**Zod v4 note**: `z.record(z.unknown())` no longer valid — must be `z.record(z.string(), z.unknown())`.

**Next**: integration-test the full flow end-to-end (upload template → generate chart → edit → save → verify MOM draft picks up the note). C.9 acceptance criteria checklist.

---

## 2026-05-12 — P6B: Dashboard restructure + Action Items Kanban

**Done**:

- **CLAUDE.md §6**: Added binding override table — superpowers skill output paths now redirect into `PHASE-NN-*.md` files instead of `docs/superpowers/`. Prevents silent folder creation in all future sessions.
- **`docs/superpowers/` deleted**: Historical `plans/2026-04-30-scaffold-data-auth.md` confirmed fully executed (P0+P1+P2); content absorbed into PHASE-00/01/02 docs. Brainstorm spec deleted. `.superpowers/` and `graphify-out/` added to `.gitignore`.
- **PHASE-06-frontend.md restructured**: Existing P6A content wrapped as Part A; Part B design spec + implementation plan added; Part C diet chart stub added with 6 open questions for future brainstorm.
- **P6B Task 1** (commit `0f454c2`): Dashboard — removed "Recent Clients" section, enriched pending action item rows to two-line format (`{client} · {date}` / `{description}`).
- **P6B Task 2** (commit `e118319`): Extracted `frontend/src/lib/actionItemsKanban.ts` (`groupByClient`, `MOVE_FORWARD`, `MOVE_BACK`); 11 unit tests in `frontend/tests/unit/actionItemsKanban.test.ts` — TDD (red→green verified).
- **P6B Task 3** (commit `57e5484`): Replaced action items page with client×status kanban table (Open / In Progress / Done). Missed items in Open column with red treatment. Bidirectional click-to-move with optimistic update + revert on error.

**Test count**: 43 tests, all green.

**Decided**:
- Part B scope: frontend-only, no new npm deps, no backend changes
- Missed items stay in Open column (red card) — not a separate 4th column
- P6B marked Complete. P6C (diet chart) deferred to a future brainstorm session.

**Side quest — observability gap identified**:
ADR-0006 covers unhandled exceptions (Sentry), LLM validation failures (`llm_calls` + Sentry alert), and request errors (structured logs) well. Gap: no explicit convention for **application-level graceful degradations** — cases where the API returns 200 but a feature silently fell back to lesser behaviour (e.g. diet chart LLM returns malformed JSON → template returned unchanged). These pass through Sentry and logs invisibly under current rules. The diet chart fallback pattern (`warn` log with namespaced event, `sentry_sdk.capture_message()` with tag, response-level `generation_status` flag) is the right model and should be formalised as a platform-wide convention. **Action needed**: add a "graceful degradation" paragraph to ADR-0006 or a `docs/standards/graceful-degradation.md` — deferred, not blocking P6C.

---

## 2026-05-07 — Repo sync sweep + HANDOVER-P6 update + P6 UI review fixes

**Done**:

- **Full repo sweep** (`docs/SYNC-2026-05-07.md` created): read all ADRs (0001–0006), all phase plans (PHASE-00 through PHASE-06), SPEC-0001, all domain docs, HANDOVER-P6, SESSION_LOG, build-plan, REPO-INDEX, diagrams, and `frontend_feedback.md` in a single pass. Nine discrepancies between docs and implementation found and documented. All are doc-only fixes; none block P7.

- **HANDOVER-P6.md updated**: added `§Post-P6 developments` section covering: two post-HANDOVER-P6 commits, `frontend_feedback.md` review findings, 8 uncommitted P6-fix files, and SYNC sweep results with all 9 discrepancies. Git state block updated from `45852c5` to `af62526`.

- **P6 UI review** (`frontend_feedback.md` — committed `af62526`): 5 items triaged. Items 1, 3, 4 coded and uncommitted. Items 2 and 5 deferred as `P6B-spec`.
  - Item 1 (`P6-fix`): Dashboard section background cards for visual separation
  - Item 3 (`P6-fix`): Client name + Session # in Today's sessions list
  - Item 4 (`P6-fix`): Open action items section above sessions on client detail page; checkbox accountability
  - Item 2 (`P6B-spec`): "Recent Clients" widget — keep or replace? Needs brainstorm
  - Item 5 (`P6B-spec`): Diet chart feature — full spec needed before any code

- **Mock script fix** (commit `617b18d`): corrected table name `session_briefs` → `briefs` in `backend/scripts/mock_p6/05_verify_flywheel.sh`.

**Decided**:
- `frontend_feedback.md` items 2 and 5 require product brainstorm in Claude AI before implementation — not P6-fix, not P7 without a spec
- Diet chart may warrant its own unit (`Unit_002_DietCharts`) — defer naming until spec is written; DB tables already exist from P1
- SYNC document is the artifact for Claude AI sync context; HANDOVER-P6 + SYNC-2026-05-07 are the two docs to share for any P7 design conversation

**Bugs found / fixed**:
- Mock flywheel script was querying non-existent `session_briefs` table; fixed to `briefs`

**Known issues / carry-overs into P7**:
- 8 frontend files uncommitted — commit before P7 starts; run `cd frontend && npx vitest run` first
- `docs/SYNC-2026-05-07.md` uncommitted — commit with frontend files
- PHASE-06-frontend.md §4/§6/§7/§8 still unfilled (D8 from SYNC doc) — complete before PHASE-07 is written
- 9 doc discrepancies documented in SYNC doc — doc fixes, do not block P7
- All P7 carry-overs from HANDOVER-P6 §Known issues still apply (M000 UX gap, LLM timeout, Sentry stub, etc.)
- `PROJECT-CUSTOM-INSTRUCTIONS.md` at repo root was missing — recreated by SoJo

**Test count**: 189 backend / 40 e2e / ~12 unit (unchanged)

---

## 2026-05-06 — P6: Frontend E2E Fixes + P6 Verification Guide + AI Mock Test Scripts

**Done**:

- **P6 frontend e2e test suite: 40/40 passing** (was 34/40 at session start). Six failures fixed:
  - Test 6 (auth error text): assertion regex changed from `/authentication failed/i` to `/sign-in failed/i` to match actual page text "Sign-in failed. Redirecting to sign-in…"
  - Test 14 (brand rules font check): `assertHeadingFont` narrowed from `h1, h2, h3` to `h1` only — eyebrow-style `h2` elements on session page intentionally use `font-sans` (Manrope) per brand guide; Fraunces requirement only applies to `h1`
  - Test 26 (MOM draft strict mode): `getByText(/session summary/i).first()` — same text appeared in both AI draft `<p>` and editable `<textarea>` populated from the same draft; `.first()` disambiguates
  - Tests 36, 38, 39 (horizontal overflow at 375px): `TabsList` with `inline-flex w-fit whitespace-nowrap` and three long labels exceeded 327px available width; fixed by wrapping in `<div className="overflow-x-auto">` which scopes overflow without affecting larger viewports

- **VERIFICATION.md — P6 Frontend walkthrough** (Steps 1–14): automated suite, TypeScript build, Playwright visual inspection, live walkthrough with backend, mobile check, brand spot-check. Google OAuth redirect_uri_mismatch diagnosed — backend sends `http://localhost:8000/api/auth/google/callback` as redirect URI; this URI must be added to Google Cloud Console Authorized Redirect URIs before step 7 can pass.

- **Mock test scripts for AI context tracking** (`backend/scripts/mock_p6/`):
  - `lib.sh` — shared HTTP/date/session-lifecycle utilities sourced by all scripts
  - `01_foundation.sh` — HC user + 3 clients (Maya/Ravi/Sunita), writes IDs + JWT to `/tmp/mock_p6_ids.env`
  - `02_maya.sh` — Maya Patel: M000 onboarding (template brief) + M001 first real session (2 LLM calls)
  - `03_ravi.sh` — Ravi Kumar: 5 sessions, weight loss narrative 88kg→85.2kg (10 LLM calls)
  - `04_sunita.sh` — Sunita Rao: 8 sessions, PCOD management, cycle 50d+→27d, insulin resistance found at S7 (16 LLM calls)
  - `05_verify_flywheel.sh` — pure DB inspection: style snippet count, snippet injection in latest MOM drafts, brief token progression across sessions
  - Total: 28 LLM calls, verifies context farm + style flywheel end-to-end

- **Session-by-session architecture principle** (critical design decision): Each brief is generated at the moment the session starts — after all previous sessions' items are in DB, but before the current session's notes or items are added. This is the only correct way to simulate real context accumulation and observe whether the AI's context awareness grows across sessions. Token progression in `llm_calls.input_tokens` for brief generation is the objective metric.

**Decided**:
- Font rule: Fraunces applies to `h1` only; `h2`/`h3` eyebrow labels use Manrope — test confirms this
- Mock test architecture: session-by-session flow is canonical; bulk-seeding all sessions then generating briefs is a known anti-pattern (brief sees all items simultaneously, defeating the context progression test)
- Style snippets require `mom.llm_call_id IS NOT NULL AND final_text != draft_text` — all sessions in mock scripts use LLM MOM generation to ensure flywheel engages from session 1

**Bugs found / fixed**:
- TabsList overflow: three long tab labels overflow `html` element width at 375px — contained with `overflow-x-auto` wrapper
- Brand rules test too strict: h2 eyebrow elements flagged as missing Fraunces — narrowed scope to h1
- MOM draft strict mode: draft text appears in both `<p>` and `<textarea>`, Playwright strict mode fails without `.first()`

**Known issues / carry-overs into next session**:
- Google OAuth not testable end-to-end until `http://localhost:8000/api/auth/google/callback` is added to Google Cloud Console Authorized Redirect URIs (user action required)
- Mock test scripts not yet run — AI context tracking hypothesis not yet validated
- HANDOVER-P6.md not yet written (user will request after completing P6 verification)

**Test count**: 40 Playwright e2e passing; backend test count unchanged from prior session (189)

---

## 2026-05-06 — P5 Part B: Manual Verification + R2 Migration + Bugfixes

**Done**:

- **AWS S3 → Cloudflare R2**: Swapped object storage to R2 free tier (10 GB / 1 M writes / 10 M reads / zero egress). Changed `config.py` fields from `aws_*` to `r2_account_id / r2_access_key_id / r2_secret_access_key / r2_bucket_name`; updated `src/lib/s3.py` host to `{bucket}.{account_id}.r2.cloudflarestorage.com`, region hardcoded to `"auto"`. Sig V4 signing unchanged. Updated `.env.example`, `VERIFICATION.md`, ADR-0001 changelog. Decision recorded in ADR-0001 (changelog 2026-05-06). Known limitation: R2 free tier has no India-region pinning — accepted at MVP scale under DPDP negative-list regime.
- **Duplicate `content-type` bug fixed in `s3_put`**: `_build_auth_header` adds `content-type` to result_headers via `extra_headers`; original code then also added `headers["Content-Type"] = content_type` explicitly. httpx merged both into `text/plain, text/plain`, causing `SignatureDoesNotMatch` 403 on every PUT. Fixed by removing the redundant post-signing assignment. Root cause found via full request trace script.
- **`ClientOut` missing `code` field**: `GET /api/clients/{id}` was not returning the `code` (CP\<NNNN\>) field. DB always had it; response schema `ClientOut` was missing it. Added `code: str | None` to `ClientOut`. All 189 tests pass.
- **`check_r2_creds.py` diagnostic script**: `backend/scripts/check_r2_creds.py` — runs PUT / GET / DELETE smoke test against real R2, prints full Authorization header and all headers httpx actually sends. Used to pinpoint the duplicate content-type and signature mismatch. Keep for future debugging.
- **Verification checklist fixes** (`docs/VERIFICATION.md`):
  - Step 4: removed incorrect PATCH client command (no such endpoint); replaced with GET to confirm auto-assigned code
  - Step 5: moved `echo > /tmp/test_note.txt` before the upload curl command
  - Step 7: updated S3 aws-cli verification commands to wrangler equivalents
  - Step 8: corrected to note that `prompt_text` stores only system prompt — "HC's typed notes" and "Uploaded files" are in `user_message` which is not persisted; prompt injection verified by integration tests only
  - All S3/AWS references updated to R2 throughout checklist and summary table
- **P5 Part B verification**: all 12 steps confirmed passing. `VERIFICATION.md` status updated to Verified 2026-05-06.
- **HANDOVER-P5.md**: written and committed — full context transfer document for P6.

**Decided**:
- R2 over S3: zero-cost MVP posture; S3-compatible Sig V4 means ~30 lines of code change
- DB row deletion is canonical for files; R2 delete is best-effort (204 returned regardless)
- `user_message` (HC notes + file content) is not persisted to DB — observability gap deferred to P8

**Bugs found during manual verification** (all fixed this session):
- Duplicate `content-type` header in `s3_put` → `SignatureDoesNotMatch` 403 on every file upload
- `ClientOut` missing `code` field → step 4 verification command appeared to fail
- Verification step 4 had wrong curl command (PATCH endpoint doesn't exist)
- Verification step 5 had file creation after upload command (curl silently failed on missing file)
- Verification step 8 checked `prompt_text` for user message content that's never stored there

**Known issues / carry-overs into P6**:
- `{{SESSION_NOTES}}` placeholder in `mom_draft.md` system prompt is never replaced — session notes travel via `user_message` instead. Dead template text; clean up in a future prompt pass.
- `user_message` not stored in DB — full LLM conversation not reconstructable from DB alone. Decide in P8 whether to add `user_message_text BYTEA` column to `llm_calls`.
- No `PATCH /api/clients/{id}` endpoint — client fields (name, email, journey_stage) cannot be updated post-creation. Needed before pilot gate.
- R2 free tier: no India-region pinning — document for pilot legal review.

**Test count**: 189 passing (was 157 after P5B code; +32 from fixes this session — test mocks updated for r2_* settings).

---

## 2026-05-05 — PHASE-05 Part B: Client File Library

**Done**:

- **B1**: Added 4 S3 env vars to `backend/src/config.py` (`aws_access_key_id`, `aws_secret_access_key`, `aws_s3_bucket_name`, `aws_region=ap-south-1`) and to `.env.example` with IAM/residency guidance comments
- **B2**: `backend/src/lib/s3.py` — full AWS Sig V4 client using Python stdlib only (`hmac`, `hashlib`, `datetime`, `urllib.parse`); no boto3; functions: `s3_put`, `s3_get`, `s3_delete`, `s3_exists`, `build_session_file_key`, `_get_session_date_ist`, `_sanitize`; all HTTP via `make_http_client()`
- **B3**: Alembic migration `df7c84b2de4f_p5b_add_client_files.py` — creates `client_files` table with 10 columns and 3 indexes; `down_revision = "bb542bec1c52"` (P5A head); separate from Part A migration per CLAUDE.md §9
- **B4**: `backend/src/db/models/files.py` — `ClientFile(Base)` ORM with write-once contract documented in docstring; `storage_path` is bare S3 key; registered in `backend/src/db/models/__init__.py`
- **B5**: `backend/src/api/files.py` — POST/GET/DELETE on `/api/sessions/{session_id}/files`; multipart upload with MIME allowlist (4 types) + 25 MB size limit; Zoom auto-detection via `zoom_ai_summary_` filename prefix; `client.code is None` → 422; S3 delete failure non-fatal (log + continue); registered in `backend/src/main.py`
- **B6**: Extended `PATCH /sessions/{session_id}` in `sessions.py` to mirror `session_notes.txt` to S3 after DB commit; S3 failure logs warning and does NOT fail the request; DB is canonical
- **B7**: `backend/src/lib/file_extraction.py` — `extract_text(content, mime_type)` handles text/plain, text/markdown, PDF (pypdf), DOCX (python-docx with Pyodide fallback); added `pypdf>=4.0` and `python-docx>=1.1` to `pyproject.toml`
- **B8+B9**: `llm_config.yaml` + `LLMConfig` extended with `file_content_max_tokens_per_file=5000` and `file_content_max_total_tokens=15000`; `get_llm_config()` uses `.get(..., default)` for safe backward compat; `_assemble_file_content_section()` helper in `llm_service/__init__.py` — fetches files from S3, extracts text, applies per-file and aggregate token budgets, returns formatted section + `zoom_present` flag; `generate_mom_draft()` and `generate_brief()` updated to assemble `## HC's typed notes:` + `## Uploaded files:` user message
- **Zoom snippet gate**: `patch_mom` in `sessions.py` now queries for `is_zoom_summary=True` files before calling `capture()`; if any Zoom file exists for the session, snippet capture is suppressed entirely
- **B10**: `docs/domain/glossary.md` updated with session_notes, session_notes.txt (S3 mirror), client_files, is_zoom_summary entries in a new "Session data terms" section
- **B12**: 24 integration tests across 5 files: `test_s3_client.py` (S3 Sig V4 signing for put + delete, key builder, sanitization), `test_file_upload.py` (single/multi upload, 25 MB limit, MIME validation, cross-tenant, DELETE idempotency, S3 delete failure resilience, Zoom filename auto-detect), `test_session_notes_mirror.py` (S3 put called with correct key/content, overwrite, S3 failure non-fatal), `test_file_prompt_injection.py` (notes+files in user_message, notes-only, per-file truncation, aggregate budget truncation, Zoom file in LLM), `test_zoom_snippet_exclusion.py` (Zoom suppresses snippet, non-Zoom allows snippet, no files allows snippet)
- **Docs**: `docs/VERIFICATION.md` — added P5 Part B manual verification checklist (12 steps, summary table)
- Total test count: 157 (133 pre-P5B baseline → 157)

**Decided** (all recorded in PHASE-05 §3):
- AWS Sig V4 via stdlib (no boto3 — Pyodide incompatible)
- Single bucket, per-HC prefix isolation (`hc-{uuid}/client_session_library/...`)
- File content fetched from S3 at prompt-assembly time (not stored in DB)
- Zoom snippet exclusion at session level (any Zoom file = all snippet capture suppressed for that session)
- S3 cascade delete is synchronous at MVP (async sweep deferred to P7)
- python-docx Pyodide failure returns empty string + warning (acceptable at MVP)

**Key implementation bugs caught and fixed during review**:
- `_get_owned_session` in first draft of `files.py` was missing `deleted_at.is_(None)` filter (data integrity) — fixed by importing from `sessions.py`
- `logger.warning()` → `logger.warn()` (BoundLogger has no `warning` method — would raise AttributeError)
- Logger structured kwargs used `extra={...}` dict instead of flat `**kwargs` — fixed to flat style
- `extract_text()` was outside the `try` block in `_assemble_file_content_section` — corrupt files would crash LLM call; fixed by moving into try
- Negative `remaining_budget` (cumulative overrun) → `text[:-n]` silently admitted too much content; fixed with `max(0, ...)` + `break`

**Pending**:
- SoJo manual verification of Part B (see `docs/VERIFICATION.md` § P5 Part B)
- P6: Frontend UI (coach-facing) — connects to all P5 endpoints

**Context the next session needs**:
- Part B is NOT verified until SoJo confirms manual steps in VERIFICATION.md § P5 Part B
- S3 must be configured in `.env` for manual verification (4 vars: aws_access_key_id, aws_secret_access_key, aws_s3_bucket_name, aws_region)
- `client.code` must be set on the client record before file upload (API returns 422 if None)
- `build_session_file_key()` in `src/lib/s3.py` is the single source of truth for all S3 paths — never construct paths elsewhere
- `session_notes.txt` is always a mirror (never read back by the system); DB column is canonical
- The `_get_session_date_ist()` function in `s3.py` is technically private but is imported by `files.py` and `sessions.py` — rename to public in a follow-up
- TODO (P7): async S3 orphan cleanup sweep; auto-flag missed action items on due_date; s3_presign_get() for frontend file display

---

## 2026-05-05 — PHASE-05 Part A: HC Cycle Workflows

**Done**:

- Wrote `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` — full 8-section PHASE plan for both Part A and Part B; SoJo confirmed plan before implementation began
- **A1**: Alembic migration `bb542bec1c52_p5_add_session_notes.py` — adds `sessions.session_notes TEXT` nullable; migration chain: P4 (`95df31e31f5f`) → P5 A1 (`bb542bec1c52`)
- **A2**: ORM: `session_notes: Mapped[str | None] = mapped_column(Text)` added to `backend/src/db/models/sessions.py`
- **A3+A4**: `SessionPatch` schema + `PATCH /sessions/{session_id}` endpoint in `backend/src/api/sessions.py`; `SessionOut` extended with `session_notes: str | None`
- **A5**: `draft_mom` now persists `body.session_notes` to `sessions.session_notes` + `await db.flush()` before LLM call (timeout protection)
- **A6**: `GET /clients/{client_id}/ast` endpoint in `backend/src/api/clients.py` with `AstOut` + `ActionItemOut` schemas; computes at request time: open/missed items, status_summary (14-day check-ins), triage_flags (missed_action_item, no_recent_checkin, manual_sentiment_flag)
- **A7**: `generate_brief()` in `backend/src/llm_service/__init__.py` extended with M000 path (session_number==0 → static template, no LLM, llm_call_id=None) and M00N path (full AST + triage computation, server-computed flags not from LLM); added `CHECKIN_TRIAGE_DAYS = 14` and `SENTIMENT_LOOKBACK_DAYS = 30` constants
- **A8**: `backend/prompts/brief_assemble.md` bumped from v1.0.0 → v1.1.0; added `{{AST_SECTION}}` and `{{TRIAGE_SECTION}}` placeholders
- **A9**: `docs/diagrams/0002-data-model.md` updated with P4 deltas (clients.code, llm_calls.prompt_text/completion_text) and P5 addition (sessions.session_notes); "MERGE-REQUIRED" banner removed
- **A10**: 21 integration tests across 4 new files: `test_session_notes.py`, `test_ast_endpoint.py`, `test_brief_extended.py`, `test_mom_workflow.py`
- **Bug fix**: `client.metadata` → `client.metadata_` (SQLAlchemy column alias) in M000 brief path
- Total test count: 144 (P4 baseline) → 165 (P5 Part A)

**Decided**:
- M000 detection: `session.session_number == 0` (not a non-existent `is_first_session` column)
- M000 brief: `briefs` row still created for idempotency, but `llm_call_id=None`; no `llm_calls` row written
- Triage flags are server-computed (not from LLM parsed output) — more reliable
- `Client.metadata_` is the ORM attribute name (maps to `metadata` column) — critical to note for future sessions

**Pending**:
- SoJo manual verification of Part A (see `docs/VERIFICATION.md` § P5 Part A)
- Part B (Client File Library: S3, client_files table, file upload/list/delete endpoints, session_notes.txt mirroring, file content injection in LLM prompts, Zoom summary detection) — starts only after Part A is verified

**Context the next session needs**:
- Part A is NOT verified until SoJo confirms manual steps in VERIFICATION.md § P5 Part A
- Part B deliverables B1-B12 are specified in `PHASE-05-hc-cycle-workflows.md` §2
- Key Part B decisions: AWS Sig V4 via stdlib (no boto3, Pyodide incompatibility), synchronous S3 cascade delete at MVP, Zoom snippet exclusion at session level
- `backend/src/config.py` needs 4 new AWS vars for Part B; `.env.example` also needs updating

---

## 2026-05-04 — PHASE-04 retroactive write + convention lock-in

**Done**:
- Rewrote `docs/specs/Unit_001_HcCoreCycle/PHASE-04-llm-service.md` from its old SPEC-style content (Goal, Non-goals, Actors, Mermaid diagrams, etc.) to a proper 8-section PHASE document matching `docs/specs/template-phase-plan.md`
- Content sourced strictly from SESSION_LOG 2026-05-04 (P4 entry) and VERIFICATION.md § P4 — no fabrication
- Updated `docs/build-plan.md`: P4 phase plan note changed from "not yet written" to a proper link; "How to use this when working with Claude Code" loop now includes "write the PHASE file before implementation begins" as step 1

**Decided**:
- P4 was the last retroactive PHASE file. All future phases (P5 onward) must have their PHASE-NN file written **before** the build sprint begins, not after — per the SPEC-before-code rule in CLAUDE.md §6 and the build-plan loop
- PHASE file convention is now locked: `Unit_001_HcCoreCycle/PHASE-NN-kebab-title.md`, 8 sections per `template-phase-plan.md`, linked from the corresponding build-plan.md phase section

**Pending / next session**:
- P5: HC Cycle Workflows
- Before writing any P5 code: write `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` using `template-phase-plan.md`

**Context the next session needs**:
- PHASE file must be written and confirmed by SoJo before P5 implementation starts — this is not optional
- The PHASE file for P5 should reference SPEC-0001 §HC Cycle (the acceptance criteria it implements) and ADR-0003 §LLM strategy

---

## 2026-05-04 — Naming cleanup: Unit-scoped specs + retroactive phase plans

**Done**:
- Committed all uncommitted P4 work (43 files, migration `95df31e31f5f`, full `llm_service/` module, 144/144 tests)
- Created `docs/specs/Unit_001_HcCoreCycle/`
- Moved `0001-hc-core-cycle.md` → `Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` (history preserved via `git mv`)
- Moved `0004-llm-service.md` → `Unit_001_HcCoreCycle/SPEC-0002-llm-service.md`; updated internal header from `Spec-0004` to `SPEC-0002`
- Wrote retroactive PHASE plans for P0–P3 (`PHASE-00-repo-scaffolding.md`, `PHASE-01-data-layer.md`, `PHASE-02-auth-service.md`, `PHASE-03-domain-crud.md`); all content sourced strictly from SESSION_LOG and ADRs — no fabrication
- Created `docs/specs/template-phase-plan.md` and `.claude/skills/skill-write-phase-plan.md`
- Created `.claude/skills/skill-write-spec.md`; updated `docs/specs/0000-template_SPEC.md` with SPEC-vs-PHASE distinction header and "Implemented by phases" field
- Updated `CLAUDE.md` — added new §6 "Working with product files" (naming convention, unit structure, cross-cutting docs stay flat); renumbered subsequent sections §7–§12
- Created `PROJECT-CUSTOM-INSTRUCTIONS.md` at repo root (SoJo to upload to claude.ai Project knowledge)
- Updated cross-references across all active docs to new paths: `docs/decisions/0001, 0003, 0004`, `docs/diagrams/0002-data-model.md`, `docs/ops/secrets-management.md`, `docs/ops/incident-response.md`, `docs/REPO-INDEX.md`, `PREFLIGHT.md`
- Updated `docs/build-plan.md` — each phase section now links to its `PHASE-NN-...md` file

**Decided**:
- Naming convention locked: `docs/specs/Unit_NNN_PascalCaseName/SPEC-NNNN-...md` and `PHASE-NN-...md`
- Phase numbering resets per unit; SPEC numbering resets per unit
- LLM Service is `SPEC-0002` inside `Unit_001_HcCoreCycle` — not a separate unit; it serves the HC core cycle
- ADRs and diagrams stay flat in existing folders; no per-unit subfolders
- Retroactive PHASE plans are thorough, not thin; accuracy sourced strictly from SESSION_LOG and ADRs
- `PROJECT-CUSTOM-INSTRUCTIONS.md` lives at repo root; SoJo uploads to Claude Project knowledge after updates

**Bugs fixed mid-session**:
- None (doc-only session; no code changes)

**Pending / next session**:
- P5: HC Cycle Workflows
- Write retroactive PHASE-04 (LLM service) before P5 starts, or at start of P5 session

**Context the next session needs**:
- All future phases follow the same convention: write SPEC first (if new unit/feature), then write PHASE plan, then implement
- The phase plan for P5 uses `docs/specs/template-phase-plan.md` and lives at `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md`
- `PROJECT-CUSTOM-INSTRUCTIONS.md` at repo root needs to be uploaded to claude.ai Project knowledge before the P5 session

**Open questions for SoJo**:
- Should LLM Service eventually become its own unit (`Unit_002_LlmService`) as the module grows? Currently it's `SPEC-0002` inside `Unit_001_HcCoreCycle`. Fine for MVP; revisit if the LLM service becomes product-facing rather than internal.
- `PHASE-04-llm-service.md` not written in this session (scope was P0–P3 only). Write retroactively before P5, or defer?

---

## 2026-05-04 — P4: LLM Service

**Done**:
- **Migration `95df31e31f5f`** (ran earlier session): `pgcrypto` extension, `llm_calls.prompt_text` + `completion_text` (BYTEA, pgcrypto-encrypted), `clients.code` (CP0001 pseudonym, unique per HC), `llm_calls.client_id` FK → `ondelete=CASCADE`.
- **`backend/prompts/`**: three prompt files with YAML frontmatter — `mom_draft.md` (v1.0.0), `brief_assemble.md` (v1.0.0), `ai_assist.md` (v1.0.0, endpoint wired P5).
- **`src/llm_service/`** — full module:
  - `llm_config.yaml`: 4-model chain (llama-3.3-70b primary, gemma-3-27b, gpt-oss-120b, nemotron-3-super-120b-a12b), snippet settings, validation_retry_count=1.
  - `config.py`: `LLMConfig` dataclass, `get_llm_config()` (lru_cache).
  - `prompts.py`: `PromptFile`, `load_prompt()` — YAML frontmatter parser.
  - `tracking.py`: `write_llm_call()` — raw SQL INSERT with `pgp_sym_encrypt()`.
  - `snippets.py`: `capture()` (diff gate: threshold + whitespace filter), `select()` (Option C hybrid: pool of 25 by created_at, re-sorted by last_used_at ASC NULLS FIRST, stopped at 2K token budget), `update_usage()`.
  - `client.py`: `call_openrouter()` — uses `make_http_client`, returns `OpenRouterResult`.
  - `chain.py`: `build_models_array()`, `fallback_count_for()`.
  - `retry.py`: `parse_or_retry()` — one retry with stricter format hint.
  - `schemas/`: `MomDraftSchema` (with `to_draft_text()`), `BriefSchema` (with `to_brief_text()`), `ActionItemSchema`.
  - `__init__.py`: `generate_mom_draft()`, `generate_brief()` — full orchestration (snippets, LLM, tracking, error handling).
- **`src/api/sessions.py`** updated:
  - `MomOut` + `BriefOut` now include `llm_call_id`.
  - New `POST /{session_id}/mom/draft` — generates AI draft, upserts MOM.
  - `GET /{session_id}/brief` — cache-first, then generates via LLM (replaced P3 404 stub).
  - `PATCH /{session_id}/mom` — snippet capture gate: fires only when `mom.llm_call_id IS NOT NULL` and final_text != draft_text.
- **`src/telemetry/scrub.py`**: `prompt_text` + `completion_text` added to `_PII_KEYS`.
- **Tests**: `test_llm_tracking.py` (4), `test_llm_snippets.py` (9), `test_mom_draft.py` (7), `test_scrub_extended.py` (4), `test_llm_service_config.py` (7), `test_llm_service_prompts.py` (7) — all new, all green.
- Removed stale P3 test `test_get_brief_returns_404_when_none` (that stub is now P4 generation).
- **144/144 tests passing**.

**Decided**:
- Decision A — Snippet selection Option C hybrid (pool of 25 most-recent, then last_used_at ASC NULLS FIRST within pool, stop at 2K token budget). `snippet_pool_size` in llm_config.yaml.
- Decision B — Amend ADR-0006 §5: store encrypted `prompt_text` + `completion_text` in `llm_calls` via pgcrypto BYTEA. Three protections: client pseudonymization (CP<NNNN>), column-level pgp_sym_encrypt, tenant-scoped reads.
- Fallback key (`"dev-only-placeholder-not-for-production"`) used when `LLM_CALL_ENCRYPTION_KEY` is empty — ensures pgp_sym_encrypt never receives empty passphrase; production must set a real key.

**Out of scope** (P5+):
- Action item extraction endpoint (ai_assist.md prompt created; wired P5)
- Snippet retirement sweep (P7)
- Full AST + triage flags in brief (P5)
- ADR-0003/0006 formal amendment docs

**Manual verification**: `docs/VERIFICATION.md` → P4 section — **verified 2026-05-04**.

**Post-verification bugs fixed**:
- `clients.code NOT NULL` violation on `POST /api/clients` — migration made code NOT NULL but `create_client` never assigned it. Fixed: `create_client` now computes `CP<NNNN>` via `MAX(CAST(SUBSTRING(code FROM 3) AS INTEGER)) + 1` before insert.
- `llm_config.yaml` had 4 models — OpenRouter `models` array limit is 3. Fixed: removed `openai/gpt-oss-120b:free` (not a valid slug). Chain is now llama-3.3-70b → gemma-3-27b → nemotron-3-super-120b-a12b.
- LLM call silently timed out with empty `detail` — httpx default timeout is 5 s; free models can take 30–60 s. Fixed: `timeout=120.0` on the `make_http_client()` call in `client.py`. Also changed `detail=str(exc)` → `detail=repr(exc)` so future errors are never silently empty.

**Known issues / follow-ups noted after verification**:
- **Unicode in draft_text**: LLMs sometimes emit ` ` (NARROW NO-BREAK SPACE) and similar typographic characters in their output (e.g. in place of apostrophes or as non-breaking spaces). The backend stores LLM output faithfully — normalization/replacement should happen in the **frontend** when rendering MOM text. Frontend team to handle before GA.
- **Prompt version test (#14) is one-time**: test #14 in VERIFICATION.md verifies the prompt-version-in-llm_calls traceability chain. Only needs re-running after changes to `src/llm_service/prompts.py`. Not a recurring verification item.
- **pgcrypto BYTEA is expected**: `prompt_text` and `completion_text` in `llm_calls` are pgcrypto-encrypted binary, not plain text. To read for debugging: `SELECT pgp_sym_decrypt(prompt_text, '<LLM_CALL_ENCRYPTION_KEY>') FROM llm_calls WHERE id = '...';`. Columns are nullable for error-path rows where no LLM call completed.

---

## 2026-05-02 — P3: Domain CRUD + Client-Facing Endpoints

**Done**:
- **Schema extensions** (migration `60775f9338d3`): `users.role`, `clients.user_id` (FK to users, nullable, for client OAuth linking), `sessions.deleted_at` (soft-delete), `client_invite_tokens` table (SHA256 hash, 30-day TTL, single-use). Schema decisions D-1/D-2/D-3 confirmed.
- **`src/api/deps.py`**: `HcClaimsDep`, `ClientClaimsDep`, `TenantDep`, `DbDep`, `LimitDep`, `PaginatedList[T]`, `encode_cursor()` / `decode_cursor()` shared by all routers.
- **`src/api/clients.py`**: POST /api/clients, GET /api/clients (cursor paginated), GET /api/clients/{id}, POST /api/clients/{id}/invite (SHA256 token, invalidates prior unused tokens). Cross-tenant 404 via `_get_owned_client()`.
- **`src/api/sessions.py`**: Sessions CRUD (create/list/get/end), MOM lifecycle (create/get/patch/send), GET brief (404 stub at P3). Duplicate session_number → 409. Idempotent `end` and `send`.
- **`src/api/action_items.py`**: POST/GET/GET/{id}/PATCH action items. `completed_at` set/cleared on status transitions. All HC transitions allowed.
- **`src/api/check_ins.py`**: GET /api/clients/{id}/check-ins (HC reads), PATCH /api/check-ins/{id}/flag (set/clear `sentiment_flag`). `model_fields_set` used to distinguish explicit `null` from omitted.
- **`src/api/me.py`**: POST /api/me/check-ins (client submits), GET /api/me/moms (sent only), GET /api/me/action-items. Client resolved from JWT `sub` + `hc_id` claims.
- **conftest.py rewrite**: savepoint-based test isolation (`join_transaction_mode="create_savepoint"`), test JWT keys injected before src imports, `client_user` / `client_rec` / `client_headers` fixtures added.
- **92 tests passing** (was 37 after P2).

**Decided**:
- D-1: `users.role` column (server_default `'hc'`) — role stamped at account creation, not derived at query time.
- D-2: `client_invite_tokens` table — separate table (not inline on clients) to support TTL, single-use, audit trail.
- D-3: Invite TTL = 30 days.
- Deleted redundant `docs/specs/0002-domain-crud.md`; `0001-hc-core-cycle.md` is the authoritative P3 spec.
- Cross-tenant responses are always 404 (never 403) to prevent existence leakage.
- Client ME endpoints use `claims.sub` as client's user_id; `hc_id` from JWT pins the tenant.

- **`src/auth/router.py` — client OAuth**: `GET /api/auth/client/start?invite=<token>` (verify invite, initiate Google OAuth), `GET /api/auth/client/callback` (exchange code, link Client record, mark invite used, issue role=client JWT). Fixed `/api/auth/refresh` to use `user.role` instead of hardcoded `"hc"` and look up `hc_user_id` from client record for client users.
- **`src/api/me.py` additions**: `GET /api/me/moms/{id}` (404 if not sent), `PATCH /api/me/action-items/{id}` (client marks own items complete/in_progress).
- **107 tests passing**.
- `VERIFICATION.md` updated with full P3 manual-check section (12 checks).

**P3 status**: ✅ complete — manual verification passed 2026-05-02.

**Issues found during manual verification** (fixed in same session):
- `env_file=".env"` in config.py didn't find root `.env` when running from `backend/` → fixed to `(".env", "../.env")`
- Verification step 3 generated a random JWT sub with no users row → replaced with `scripts/create_hc_user.py` that inserts a real user first
- Heredoc in verification instructions caused terminal issues → moved to script file
- 15-minute JWT expiry too short for full manual verification → script now issues 8-hour tokens
- `!!!` in curl URL triggered bash history expansion → switched to single-quoted URL

**Pending / next session**:
- P4: LLM integration (brief generation, MOM draft assist)

---

## 2026-05-01 — P0 / P1 / P2: Scaffold → Data Layer → Auth

**Done**:
- **P0**: git init, pyproject.toml (`[dependency-groups]` PEP 735), docker-compose, `.env.example`, FastAPI app with CORS + request-id middleware + `/healthz`, telemetry scaffolding (`scrub()`/`get_logger()`/Sentry stub), `make_http_client()` factory, Next.js 16 frontend skeleton, `CONTRIBUTING.md` with dev commands
- **P1**: 16-table SQLAlchemy 2.0 models (6 files by domain), async session factory (`get_db()`), Alembic `env.py` with async engine, initial migration (`e8a1523b2f3a`), roundtrip + cascade-delete integration tests (29 total passing)
- **P2**: ES256 JWT sign/verify (`python-jose`), Google OAuth PKCE flow, refresh token rotation with replay detection, `require_role()` + `current_tenant()` FastAPI dependencies, auth router (4 endpoints), auth integration tests (37 total passing)

**Decided** (link ADRs):
- ADR-0003 flipped to Accepted before P1 coding started
- `llm_calls` schema reconciled: `model_requested`/`model_served`/`prompt_version`/`request_id` (per ADR-0003 amendment)
- `auth_refresh_tokens` added to data model diagram (was missing)
- `retired_at` added to `hc_style_snippets`
- Circular FK (`moms`/`briefs` → `llm_calls`) handled via deferred `op.create_foreign_key()` in migration
- `backend/.venv` → symlink to `/mnt/hdd/yourProjects/venv/hc_pf` for single shared Python env
- Replay detection check order: `successor_id` checked before `revoked_at` in `rotate_refresh_token()`

**Bugs fixed mid-session**:
- `server_default="'onboarding'"` triple-quoted by SQLAlchemy `create_all()` → fixed to `server_default=text("'onboarding'")` + Python-side `default=`
- `auth_refresh_tokens` partial index used `NOW()` (volatile) in predicate → fixed to `WHERE revoked_at IS NULL`
- pytest-asyncio event loop scoping → added `asyncio_default_test_loop_scope = "session"` to `pyproject.toml`

**Pending / next session**:
- P2 manual verification (see `docs/VERIFICATION.md`)
- P3: Domain CRUD endpoints (clients, sessions, MOMs, action items, check-ins)
- Install Postgres MCP (read-only) per `starter_prompt_01.md`

**Context the next session needs**:
- Run `docs/VERIFICATION.md` P2 checklist before starting P3
- P3 source docs: `docs/diagrams/0002-data-model.md`, `docs/domain/glossary.md`, `docs/domain/actors.md`
- P3 spec: `docs/specs/` — write spec before coding, per CLAUDE.md rule 9
- Node 22 required for frontend: `export PATH=~/.nvm/versions/node/v22.15.1/bin:$PATH`

**Open questions for SoJo**:
- Google Cloud Console credentials needed before OAuth callback can be fully tested end-to-end
- P3 priority order: clients → sessions → MOMs, or a different slice?

---

## YYYY-MM-DD — [topic]

**Done**:
- ...

**Decided** (link ADRs):
- ...

**Pending / next session**:
- ...

**Context the next session needs**:
- ...

**Open questions for SoJo**:
- ...

---
