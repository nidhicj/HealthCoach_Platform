We are continuing the build. Scope of this session: **PHASE-06 — Frontend (HC Console) + Brand Identity Adoption**, per `docs/build-plan.md`. P6 has two manual verification gates: a motion-lab gate (early — SoJo signs off on motion feel before any real screens are built) and a full P6 gate (at the end). Stop at the end of P6 — do not start P7.

P0–P5 are complete and manually verified. Latest state: 189/189 tests passing (per `HANDOVER-P5.md`). Five Alembic migrations applied; head is `df7c84b2de4f`. The PHASE-06 plan has already been drafted in claude.ai and committed to the repo at `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md` — it is the contract for this phase. Treat it as authoritative.

# Mandatory preparation (before writing any code)

1. Read `CLAUDE.md` (root) and `PREFLIGHT.md` in full. The anthem and the preflight block are non-negotiable for every substantive response in this session.
2. Read `HANDOVER-P5.md` (root) — it is the complete current-state context transfer. Endpoint surface, conventions, env vars, R2 client, file-upload behaviour, snippet-capture exclusions for Zoom files, all of it. Trust HANDOVER-P5 as authoritative for backend state.
3. Read `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md` in full. **This is the contract for this phase.** Every deliverable, decision, and acceptance criterion in P6 traces to this file. If it is missing from the repo, stop — SoJo needs to commit it before you can begin.
4. Read `docs/build-plan.md` Phase 6 section in full, plus the "How to use this when working with Claude Code" loop and the "Traceability matrix" rows for P6.
5. Read every primary source doc the matrix marks for P6:
   - `docs/decisions/0001-stack-selection.md` — frontend stack lock (Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui), Cloudflare Pages hosting, the `User-Agent` requirement (workers-py #68) which does not apply to the frontend but is worth knowing for context
   - `docs/decisions/0004-repo-structure.md` — `frontend/` layout, `.claude/` conventions, `prompts/` separation
   - `docs/decisions/0005-auth-strategy.md` — JWT in memory + HTTP-only refresh cookie pattern that the frontend must honour. ADR-0005 is non-negotiable: never store the access token in `localStorage` or `sessionStorage`.
   - `docs/domain/glossary.md` — UI terminology (HC, client, session, MOM, AST, brief, snippet, M00N, check-in, action item, triage flag, coach-reviewed gate). Read this before writing any user-facing copy or label.
   - `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` §Stages 2–6 — the user journey each screen expresses. Stage 2 is the M000 first-session edge case; Stage 6 is the coach-reviewed gate UX (briefs are HC-internal; sent MOMs are visible to clients via the future client UI; client UI itself is OUT of P6 scope).
   - `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` — what P5 just shipped, the patterns established, the §Patterns section. The frontend consumes those endpoints; do not re-litigate the API surface.
6. Read the brand source: **`Poshini_Brand_Colour_Guide.docx`** in the repo (or wherever SoJo has placed it — confirm the path). The four colours, their usage rules, the typography system, and the threat-prevention rules are all design constraints. You will encode them into `.claude/skills/parivarthan-frontend.md` as part of P6 deliverables; the source-of-truth for the rules is the brand guide itself, not your interpretation of it.
7. Read `docs/specs/template-phase-plan.md` — for reference only. PHASE-06-frontend.md is already drafted; you do not write a new one.
8. Inspect the existing `frontend/` directory in the repo. Per HANDOVER-P5 it was scaffolded in P0 with `package.json` and a Next.js skeleton but is otherwise empty. Confirm what's there and what isn't before adding files.

If any referenced document is missing, contradicts another, or contradicts HANDOVER-P5, **stop and produce a `## Context missing` block** per anthem rule 7. Do not guess. Do not pick a winner silently.

# Source-doc consistency check (do this before writing any code)

After reading the source docs, produce a short report:
- "Source docs consistent: [yes / no]"
- If no: list each contradiction. SoJo will resolve before you proceed.
- Specifically confirm:
  - (a) `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md` exists and has Status: Draft (or Approved if SoJo has signed off in-repo)
  - (b) Every API endpoint listed in PHASE-06 §2.3 (auth, clients, sessions, files, action-items, check-ins, me) exists in the backend per HANDOVER-P5 — list any that don't
  - (c) Brand color hex values in PHASE-06 §2.1 (`#F7F4EE`, `#5C6652`, `#2C2C1E`, `#E8C547`) match the brand guide exactly
  - (d) `frontend/package.json` from P0 already declares Next.js 15 and the package manager is `npm` (per HANDOVER-P5 stack table)
  - (e) ADR-0005 access-token-in-memory rule is reflected in PHASE-06 §2.3 (must say "memory only, never localStorage/sessionStorage")
  - (f) Backend CORS configuration: check `backend/src/main.py` (or wherever CORS middleware is configured) for the allowed origins. P6 will need `http://localhost:3000` in dev. **If the dev origin is not allowed, flag this back to SoJo before proceeding** — adding a CORS origin is a backend change, and P6 is frontend-only. Do not silently edit backend code.

# Confirm tooling reachable (before writing any code)

1. **Node 22 + npm**: `node --version` and `npm --version`. Per HANDOVER-P5, Node 22 is required for Next.js 15.
2. **Playwright MCP**: this is new in P6. After installing per PHASE-06 §2.9, confirm the MCP is reachable from the agent (`@playwright/mcp` package). If it doesn't install or doesn't load, stop and produce a `## Context missing` block — do not proceed without visual verification, since "no botched UI/UX" is non-negotiable for this phase.
3. **Postgres MCP** (read-only, from prior phases): still useful in P6 for the round-trip acceptance check (after MOM send → query `hc_style_snippets` to confirm a row was written). Confirm reachable.
4. **Backend running locally**: this phase needs the FastAPI backend running at `http://localhost:8000` for end-to-end testing. Per HANDOVER-P5, the backend runs via `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate && cd backend && uv run uvicorn src.main:app --reload`. Confirm SoJo has it running before any e2e test work begins; otherwise stop and ask.

# Operating rules for this session

- Run a preflight block (per `PREFLIGHT.md`) before every substantive response. Compressed (3 lines) is fine for tight follow-ups; full preflight before each new sub-task (token layer, shadcn setup, auth, API client, motion-lab, each screen, tests).
- **PHASE plan is already written.** Anthem rule 9 has already been honoured — `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md` is the contract. Do NOT redraft it. If you find a meaningful gap during implementation, stop and surface it to SoJo as a context-missing block; SoJo decides whether to amend the PHASE plan or defer the gap.
- **Verify before claiming done.** "It should work" is banned (rule 14). Run `npm run lint`, `npm run build`, `npm run test` (Vitest), and the Playwright e2e suite on both Chromium AND Firefox. The Playwright MCP is available — use it for visual verification at every screen completion; never as a fallback to skip writing tests.
- **Brand-rules linter is a per-screen gate.** Before claiming any screen complete, run the brand-rules Playwright spec against that route in both browsers. A screen with two Marigold elements, or a `bg-white` somewhere, is not done — it's broken in a way that violates the design contract.
- **Performance budget is a per-merge gate.** Lighthouse on the dashboard route after each meaningful change: LCP < 2.0s, CLS < 0.05, INP < 200ms, JS bundle < 200KB gz, CSS bundle < 50KB gz. Regressions must be addressed in the same session, not deferred.
- **Both browsers.** Playwright tests run against Chromium AND Firefox. A test passing only on Chromium is a partial pass; do not move on. Lighthouse measurement is Chromium-only (acknowledged measurement asymmetry per PHASE-06 §2.11) — Firefox runtime correctness is verified via Playwright's `page.evaluate(() => performance.getEntriesByType("navigation"))`.
- Commit per `CONTRIBUTING.md`. Conventional commits, one logical change per commit. Don't squash "tokens + shadcn + auth + API client + motion-lab + screens + tests" into one commit. Reasonable atomic shape: one commit per stage in §Implementation order below.
- No secrets in code. New env vars added by P6 (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEV_ROUTES`) go into `.env.example` with placeholder values; real values stay in `.env` (gitignored).
- Maintain `docs/SESSION_LOG.md` as you go (see "Living docs" section below). `VERIFICATION.md` § P6 gets written ONCE during Stage 6, not incrementally.

# Implementation order (build in this sequence)

The PHASE plan lists deliverables but does not order them. The dependency graph dictates the order below; do not deviate without surfacing a reason.

## Stage 0 — Repo prep (no UI yet)

1. `frontend/theme.yaml` per PHASE-06 §2.1
2. `scripts/build-theme.mjs` — the compile script
3. Wire `predev` and `prebuild` npm scripts to run the build script
4. `frontend/src/styles/tokens.generated.css` and `frontend/src/styles/tailwind.theme.generated.ts` produced by the script
5. `frontend/tailwind.config.ts` extending from generated theme; `frontend/src/app/globals.css` with `next/font` for Fraunces and Manrope, body defaults, Parchment background
6. shadcn install with brand-mapped tokens (per PHASE-06 §2.2). Components from the list in §2.2 only — do not over-install.
7. `.claude/skills/parivarthan-frontend.md` written per PHASE-06 §2.8 — the skill encodes brand rules, motion rules, banned list, per-screen checklist
8. `.claude/mcp_servers.json` updated to add Playwright MCP per PHASE-06 §2.9; both Chromium and Firefox in the browsers config
9. Smoke test: change a colour in `theme.yaml`, run the build script, confirm it propagates to both generated files; revert.

Commit boundary: "feat(p6): theme tokens, shadcn brand mapping, frontend skill + Playwright MCP".

## Stage 1 — Motion-lab and motion gate

1. `/dev/motion-lab` route per PHASE-06 §2.7 — every primitive demonstrated, type scale shown, palette swatches shown, brand-rules checker live on the page
2. Gate the route on `process.env.NEXT_PUBLIC_DEV_ROUTES === "true"`; production build returns 404
3. Confirm motion runs cleanly in both browsers (open `/dev/motion-lab` in `npm run dev`, then `npx playwright test --browser firefox` for the same)
4. **STOP here. Produce the `## P6 motion-lab ready` summary** (see §Two-stage completion below). Wait for SoJo to open the lab, judge motion, optionally edit `theme.yaml` motion tokens, and sign off before proceeding.

## Stage 2 — Auth, API client, and shell

1. `frontend/src/lib/auth/` per PHASE-06 §2.3 — in-memory access token, `fetchWithAuth`, redirect helpers
2. `frontend/src/lib/api/` per PHASE-06 §2.3 — typed wrappers for every backend endpoint with Zod schemas
3. `frontend/src/lib/config.ts` reading `NEXT_PUBLIC_API_URL`
4. App router shells: `(public)/layout.tsx`, `(app)/layout.tsx` (with `/api/me` fetch + redirect), `/sign-in/page.tsx` (the only public protected screen)
5. Vitest unit tests for the auth flow and API client schema parsing

Commit boundary: "feat(p6): auth, API client, app router shells".

## Stage 3 — Dashboard, client list, client detail

Per PHASE-06 §2.5. Each screen, in order:
1. Build the screen
2. Run brand-rules linter against the route in both browsers
3. Run Lighthouse on dashboard once; log the numbers
4. Commit

## Stage 4 — Session view (the hardest screen)

Per PHASE-06 §2.5 — three tabs (brief, notes, MOM editor). The MOM editor is the only screen with a Marigold accent (the "Send to client" button) — verify the brand-rules linter sees exactly one Marigold here, zero on the other tabs.

Commit boundary: "feat(p6): session view (brief / notes / MOM)".

## Stage 5 — Action items, settings/sessions

Per PHASE-06 §2.5. Less complex than Stage 4. No Marigold on either of these screens.

## Stage 6 — Tests, perf, and full P6 gate

1. Complete Playwright e2e suite per PHASE-06 §2.10 running in both browsers — `auth.spec.ts`, `core-cycle.spec.ts`, `mobile-375.spec.ts`, `brand-rules.spec.ts`
2. Final Lighthouse run on dashboard at mobile 4G simulation — record numbers in PHASE-06 §6.2
3. Verify production build strips `/dev/motion-lab`
4. Verify CORS works against the running backend
5. `docs/VERIFICATION.md` § P6 written with concrete check commands, expected outputs, checkboxes
6. **STOP here. Produce the `## P6 verification summary`** (see §Two-stage completion below). Wait for SoJo's manual verification.

## Stage 7 — Handover (only after manual verification passes)

1. `docs/HANDOVER-P6.md` written, mirroring HANDOVER-P5 shape — stack delta, repo layout delta, new conventions, all routes added, all tests added, env vars added, known issues, current git state
2. `docs/SESSION_LOG.md` updated with the P6 completion entry
3. `docs/REPO-INDEX.md` updated if layout changed
4. Final commit: "docs(p6): handover and session log".

These docs are written ONLY after SoJo confirms manual verification has passed. Do not write them on Claude Code's self-check.

# Patterns and rules to inherit (frontend-flavoured, P6 adds ★)

The backend non-negotiables from HANDOVER-P5 §Patterns still apply where relevant (absolute imports, `get_settings()` not `settings`, `text()` for string server defaults, etc. — but these are backend rules; do not edit backend code in P6). The frontend equivalents:

1. **Absolute imports** — `import { Button } from '@/components/ui/button'`, never `../../../components/ui/button`. Configure TypeScript path aliases.
2. **All API calls through `frontend/src/lib/api/`** — never `fetch()` directly in components. Components import typed wrappers.
3. **All auth state through `frontend/src/lib/auth/`** — never read tokens or refresh state from anywhere else.
4. ★ **Access token in memory only** — never `localStorage`, never `sessionStorage`, never cookies (refresh token cookie is set by the backend, not by JS). Per ADR-0005.
5. ★ **Tokens come from `theme.yaml`** — never hand-edit `tailwind.config.ts` colours, never put hex values in components. If a token is missing, add it to `theme.yaml` and rerun the build script.
6. ★ **No `bg-white` / `#FFFFFF` / `hsl(0 0% 100%)` anywhere** — Parchment is the base. The brand-rules linter will catch this; do not let it land in a commit.
7. ★ **Marigold is rare** — at most one element per screen, reserved for the keystone action of the user's current state. Default `<Button>` is Moss Shadow; Marigold is `variant="accent"` only.
8. ★ **shadcn components are extended or wrapped, never hand-edited** — if a component needs a different look, wrap it in `frontend/src/components/wrapped/` or extend via Tailwind classes. Editing the file under `components/ui/` directly breaks shadcn upgrade paths.
9. ★ **Motion is on `transform` and `opacity` only** — never `width`, `height`, `top`, `left`, `padding`, `margin`, `border-width`, `filter`. The skill encodes this; the brand-rules linter does not catch it (yet); manual review and self-discipline.
10. ★ **No animations longer than 400ms** — feels laggy by definition. The skill encodes the four primitives and their durations.
11. ★ **No Framer Motion, no GIF, no Lottie** — `tw-animate-css` (already with shadcn) plus the keyframes in `motion.css` cover MVP needs.
12. ★ **Both browsers** — every screen verified on Chromium AND Firefox. Add to local Playwright config: `projects: [{ name: 'chromium', ... }, { name: 'firefox', ... }]`.
13. ★ **`next/font` only for Google Fonts** — never `<link rel="stylesheet">` to `fonts.googleapis.com`. `next/font` self-hosts and prevents CLS.
14. **Conventional commits** — same as P0–P5.
15. **Test isolation** — Playwright tests use a seeded test HC. Confirm with SoJo whether a fresh seed script is needed or whether `backend/scripts/create_hc_user.py` (per HANDOVER-P5) is sufficient.

# Living docs — maintain as you go

SoJo will not be reading every commit. They WILL read `SESSION_LOG.md` and `VERIFICATION.md` between sessions. Keep both current.

## `docs/SESSION_LOG.md` (append-only, latest at top)

After Stage 1 (motion-lab ready) — append a brief entry:

```markdown
## YYYY-MM-DD — P6 Stage 1: Motion-lab ready for review

**Done**:
- Theme tokens layer + shadcn brand mapping
- `.claude/skills/parivarthan-frontend.md`
- `.claude/mcp_servers.json` with Playwright MCP
- `/dev/motion-lab` route implementing all four motion primitives

**Decided** (link PHASE-06 §3 entries):
- [any decision that emerged mid-session, e.g., a tweak to motion timing]

**Bugs fixed mid-session**:
- [any]

**Stage 1 status**: ⏳ awaiting motion-lab review by SoJo

**Pending / next**:
- After sign-off: Stages 2–6 (auth, screens, tests, perf, brand-rules)

**Open questions for SoJo**:
- [any, e.g., a brand-rule translation that proved ambiguous in practice]
```

After Stage 6 (full P6 ready for verification) — append the full P6 entry. Same shape, but Stage 6 status: ⏳ awaiting manual verification, with the full done/decided/bugs lists.

After Stage 7 (handover): mark Stage 6 status: ✅ verified YYYY-MM-DD, and the handover docs are committed.

## `docs/VERIFICATION.md` (manual checklist for SoJo)

Append a section:

```markdown
## P6 — Frontend (HC Console) + Brand Identity Adoption

### Stage 1 — Motion-lab review

**Status**: ⏳ awaiting review (or ✅ reviewed YYYY-MM-DD)

[concrete steps: open http://localhost:3000/dev/motion-lab, click each section, judge feel, optionally tweak theme.yaml motion tokens]

### Stage 6 — Full P6 verification

**Status**: ⏳ awaiting verification (or ✅ verified YYYY-MM-DD)

[checks per PHASE-06 §6.1 and §6.2 — concrete commands, expected outputs, checkboxes per criterion]
```

Each check has:
- The exact command to run (curl, npm, npx playwright, Lighthouse CLI, or "open URL in browser")
- The expected output or observable outcome
- A checkbox

# Two-stage completion: Motion-lab gate, then full P6 gate

P6 has two completion gates. Both must pass before P6 is considered done.

## Stage 1 — Claude Code declares "motion-lab ready"

When the motion-lab is built, runs cleanly in both browsers, and the brand-rules checker on the lab page itself reports clean, produce `## P6 motion-lab ready`. End with — verbatim:

> **P6 motion-lab is ready for SoJo's review. Open http://localhost:3000/dev/motion-lab in both Chromium and Firefox. Tweak `frontend/theme.yaml` motion tokens if anything feels off (run `npm run dev` again to see changes). Stages 2–6 will not begin until SoJo confirms the lab is signed off.**

Then STOP. Do not start Stage 2. Wait.

## Stage 2 — SoJo reviews the motion-lab

Three outcomes:
- **Pass** → SoJo says "motion-lab signed off, proceed to Stage 2." Begin Stage 2.
- **Tweak** → SoJo asks for specific timing or easing changes. Edit `theme.yaml`, regenerate, confirm in both browsers, re-issue the ready message.
- **Spec gap** → SoJo wants a primitive added or removed. Update PHASE-06-frontend.md (record in §3 of that file as a decision made during the phase), update the lab, re-issue.

## Stage 3 — Claude Code declares "P6 ready for manual verification"

When all Stages 2–6 deliverables are implemented, all automated tests pass on both Chromium and Firefox, perf budget targets are met on the dashboard, brand-rules linter passes on every route, and `SESSION_LOG.md` + `VERIFICATION.md` § P6 Stage 6 are updated, produce `## P6 verification summary`. End with — verbatim:

> **P6 is ready for SoJo's manual verification. Not complete until manual verification passes. Awaiting confirmation before HANDOVER-P6 is written and before any P7 work begins.**

Then STOP. Do not write the handover docs. Do not start P7 anything. Wait.

## Stage 4 — SoJo runs manual verification

Three outcomes:
- **Pass** → SoJo says "P6 verified, proceed to handover." Then write Stage 7 (HANDOVER-P6.md, SESSION_LOG.md update, REPO-INDEX.md update), commit, done.
- **Fail** → SoJo lists failures. Fix in this session: write a failing test (Vitest or Playwright) that reproduces each issue, fix the code, confirm green, update VERIFICATION.md § P6 Stage 6, re-issue the verification-ready message.
- **Spec gap** → discuss with SoJo. Decide whether to fix in P6 or defer. Update PHASE-06 §3 (decisions made during the phase) with the call.

# Phase verification format (your closing summaries)

## When motion-lab is ready (end of Stage 1):

```
## P6 motion-lab ready

- Theme tokens layer: <how I verified — built and changed a colour, watched it propagate>
- Motion primitives: <names and timings, browsers verified>
- Brand-rules checker on lab: <output: clean / dirty>
- Browsers verified: Chromium <version>, Firefox <version>
- Notes / open items for SoJo: <any>
```

Then the verbatim handoff line above.

## When P6 is ready for full verification (end of Stage 6):

For each acceptance criterion in PHASE-06 §6.1 and §6.2:

- [✓] `<criterion>`: <how I verified — command run, output observed, both browsers if applicable>
- [✗] `<criterion>`: <what's blocking>
- [-] `<criterion>`: <why skipped, with rationale>

Then the verbatim handoff line above. Then STOP.

# Definition of done for P6 (Stage 1 — code level, before SoJo verifies)

- `frontend/theme.yaml` exists and is the only source of design tokens
- `scripts/build-theme.mjs` working; predev/prebuild hooks wired
- `frontend/src/styles/tokens.generated.css` and `tailwind.theme.generated.ts` produced
- shadcn components installed with brand-mapped tokens
- `.claude/skills/parivarthan-frontend.md` written, content matches PHASE-06 §2.8
- `.claude/mcp_servers.json` updated with Playwright MCP, both browsers configured
- All routes from PHASE-06 §2.4 implemented
- Auth + API client per PHASE-06 §2.3, access token in memory only
- `/dev/motion-lab` working in both browsers, gated on env var, returning 404 in production build
- All Playwright e2e tests passing on Chromium AND Firefox
- All Vitest unit tests passing
- `brand-rules.spec.ts` passes on every route in both browsers
- Lighthouse on dashboard: LCP < 2.0s, CLS < 0.05, INP < 200ms; bundles < 200KB JS / 50KB CSS gz
- `frontend/.env.example` documents `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEV_ROUTES`
- `docs/SESSION_LOG.md` Stage 1 entry written before motion-lab gate; Stage 6 entry written before full gate
- `docs/VERIFICATION.md` § P6 written before full gate
- Conventional commits, atomic per stage
- No `localStorage` or `sessionStorage` references for tokens
- No `bg-white` / `#FFFFFF` anywhere in the frontend
- No `httpx` or backend-only patterns leaking into frontend code (this is a frontend-only phase)
- No backend code edited (if a backend change is needed, surface to SoJo as a context-missing block — do not silently edit)

# Definition of done for P6 (Stage 2 — after manual verification passes)

- All Stage 1 conditions still hold
- SoJo has signed off both gates (motion-lab + full P6)
- `docs/HANDOVER-P6.md` written, mirroring HANDOVER-P5 shape
- `docs/SESSION_LOG.md` updated with P6 verified status
- `docs/REPO-INDEX.md` updated if layout changed
- PHASE-06-frontend.md status updated to `Verified` with verification date filled in
- Final atomic commit: "docs(p6): handover and session log"

# Start

Begin with a preflight block covering this whole session. Then:

1. Read the prep documents listed above (in order)
2. Produce the source-doc consistency report
3. Confirm tooling reachable (Node, Playwright MCP, Postgres MCP, backend running locally)
4. Begin Stage 0: theme tokens, shadcn brand mapping, frontend skill, MCP config
5. Move to Stage 1: motion-lab — declare ready and STOP for SoJo's motion-lab review
6. After motion-lab signed off: Stages 2–6 — declare ready and STOP for full P6 verification
7. After full P6 verified: Stage 7 — handover docs, session log update, final commit
