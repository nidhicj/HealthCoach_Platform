# PHASE-06: Frontend (HC Console) — Parts A, B, C

**Unit**: Unit_001_HcCoreCycle

| Part | Label                                       | Scope                                                                                                                                                   | Status                                       |
| ---- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| A    | HC Console + Brand Identity                 | All screens P6 built: dashboard, clients, sessions, action items, settings. Brand tokens, motion system, Playwright tests.                              | Complete                                     |
| B    | Dashboard Restructure + Action Items Kanban | Remove "Recent Clients", restructure pending items rows, replace action items page with client×status kanban table. Frontend-only, no backend changes. | Complete                                     |
| C    | Diet Chart Feature                          | AI-suggested diet chart per client: backend CRUD endpoints, LLM generation, frontend preview + editable 7-day table. DB tables already exist from P1.   | Complete                                     |

---

# Part A — HC Console + Brand Identity

**Status**: Complete
**Verification date**: TBD — see `docs/VERIFICATION.md` § P6 (to be created during build)
**Implements**: `SPEC-0001-hc-core-cycle.md` §Stage 2 (M000 first session screens), §Stage 3 (between-sessions HC view), §Stage 4 (M00N session screens), §Stage 5 (triage flag surfaces), §Stage 6 (coach-reviewed gate UX) — all expressed as HC-facing screens. Plus brand identity adoption decisions captured here in §3 (no prior SPEC; may become SPEC-0002 if the pattern recurs for future surfaces).
**ADRs implemented**: ADR-0001 (frontend stack — Next.js 15 App Router, Tailwind, shadcn/ui), ADR-0004 (`frontend/` layout), ADR-0005 (auth — JWT in memory + HTTP-only refresh cookie pattern honoured by client). ADR-0003 (LLM strategy) is consumed via existing backend endpoints; no LLM changes in P6.

---

## 1. Scope

P6 builds the HC console — every screen the pilot HC needs to run the full core cycle through a browser, against the existing backend API surface from P0–P5. **No backend changes in this phase.**

The phase also adopts the **Poshini Agasthya brand identity** as Parivarthan's MVP design language (decision §3.1 below). Per-HC theming is explicitly deferred until paying customers — for the pilot, the brand is hardcoded into the design tokens layer.

Three things ship alongside the screens to make UI/UX rigour observable rather than aspirational:

- **`frontend/theme.yaml`** — single source of truth for design tokens (colours, font weights, spacing scale, motion durations and easings). A small build script compiles it to `tailwind.config.ts` and `globals.css` CSS variables, so runtime convention stays standard.
- **`/dev/motion-lab`** — dev-only route demonstrating every motion primitive on the actual brand. SoJo opens it locally before any real screen is built and signs off on the motion feel. Stripped from production builds via `NEXT_PUBLIC_DEV_ROUTES` env gate.
- **`.claude/skills/parivarthan-frontend.md`** — repo-scoped skill encoding the brand guide rules, motion system, banned patterns, and screen-level checklist. Claude Code reads this every time it touches a frontend file. The skill is the "no botched UI/UX" mechanism: the rules are versioned, reviewable by SoJo, and self-applied by the agent before any screen is claimed done.

**Not in scope**: client-facing screens (clients have `/api/me` and auth in P5 but no UI; deferred to a later phase), per-HC theming system (deferred until User #2 onboarding milestone from ADR-0001), backend changes of any kind, mobile-native app (responsive web only per build-plan), illustrations or photography (typography-led per brand guide), dark mode (deferred — Parchment is the base, no dark variant in MVP), real-time updates / websockets (deferred — polling on demand is fine at pilot scale).

---

## 2. Deliverables

### 2.1 Repo scaffolding (frontend already exists from P0; this extends it)

- `frontend/theme.yaml` — design token source. Structure:
  ```yaml
  palette:
    parchment:   "#F7F4EE"   # base — never swap for white
    moss_shadow: "#5C6652"   # voice — bounded blocks only
    dark_ink:    "#2C2C1E"   # body text + one architectural element per screen
    marigold:    "#E8C547"   # 0 or 1 element per screen, primary CTA in current state only
    functional:
      success: "#3F7D4B"     # Moss-family green, used only for success states
      warning: "#B8722C"     # warm warning, used only for warnings
      error:   "#A23E2E"     # used only for errors
  fonts:
    headline: { family: "Fraunces", weights: [700, 900], italic: true }
    body:     { family: "Manrope",  weights: [400, 700, 800], italic: false }
  motion:
    state_change: { duration_ms: 150, easing: "ease-out" }
    reveal:       { duration_ms: 200, easing: "ease-out" }
    sheet_enter:  { duration_ms: 250, easing: "ease-out" }
    sheet_exit:   { duration_ms: 200, easing: "ease-in" }
    page_transition: { duration_ms: 300, easing: "ease-in-out" }
  spacing:
    # 4-point scale, named tokens for the most-used values
    tight: 4   loose: 8   regular: 16   section: 32   page: 64
  radii:
    sm: 4   md: 8   lg: 12
  ```
- `scripts/build-theme.mjs` — Node script (~30 lines) that reads `theme.yaml` and emits:
  - `frontend/src/styles/tailwind.theme.generated.ts` — Tailwind theme extension
  - `frontend/src/styles/tokens.generated.css` — `:root` CSS variables
  - Hooked into `predev` and `prebuild` npm scripts; runs automatically.
- `frontend/src/styles/tokens.ts` — typed exports for use in TS code (motion durations, etc.); imports from `tailwind.theme.generated.ts`.
- `frontend/tailwind.config.ts` — extends from generated theme; nothing hand-edited beyond the import.
- `frontend/src/app/globals.css` — imports `tokens.generated.css`, sets `body { background: var(--parchment); color: var(--dark-ink); font-family: var(--font-manrope); }`, configures `next/font` for Fraunces (700, 900, italic) and Manrope (400, 700, 800) with `display: swap`.

### 2.2 shadcn/ui setup with brand-mapped tokens

Components installed via shadcn CLI (`npx shadcn@latest add <name>`):

- `button`, `card`, `dialog`, `sheet`, `dropdown-menu`, `input`, `textarea`, `label`, `tabs`, `toast`, `tooltip`, `command`, `separator`, `skeleton`, `badge`, `avatar`, `alert`, `form`

Token remapping in `components.json` and `globals.css`:

- `--background` → Parchment (`#F7F4EE`)
- `--foreground` → Dark Ink (`#2C2C1E`)
- `--primary` → Moss Shadow (`#5C6652`)
- `--primary-foreground` → Parchment
- `--accent` → Marigold (`#E8C547`)
- `--accent-foreground` → Dark Ink (Marigold + Dark Ink contrast verified ≥ 4.5:1)
- `--muted`, `--card`, `--popover` → Parchment-derived warm neutrals (slight Moss tint at 5–10% blend)
- `--destructive` → functional error
- `--border` → Moss Shadow at 20% opacity

Default `<Button>` uses Moss Shadow. Marigold lives only on `<Button variant="accent">`, used at most once per screen (linted — see §2.7).

### 2.3 Auth & API client

- `frontend/src/lib/auth/`:
  - `tokens.ts` — access token stored in memory (module-level closure), never `localStorage`/`sessionStorage` (XSS hardening, ADR-0005)
  - `client.ts` — `fetchWithAuth(input, init)` wrapper that injects `Authorization: Bearer <access>`, on 401 calls refresh once silently, on second 401 redirects to `/sign-in`
  - `redirect.ts` — `redirectToGoogle()` initiates OAuth; callback handler at `/api/auth/google/callback` is on the **backend** (already shipped P2) — frontend just consumes the response
- `frontend/src/lib/api/`:
  - Typed wrappers per endpoint, organised by resource: `clients.ts`, `sessions.ts`, `files.ts`, `actionItems.ts`, `checkIns.ts`, `me.ts`, `auth.ts`
  - Every function has a Zod schema for the response (parse-validate at the boundary; type-safety the rest of the way down)
  - Endpoint coverage (every endpoint from HANDOVER-P5):
    - `GET /api/me`, `GET /api/auth/sessions`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `DELETE /api/auth/sessions/{id}`
    - `POST /api/clients`, `GET /api/clients`, `GET /api/clients/{id}`, `GET /api/clients/{id}/ast`, `POST /api/clients/{id}/invite`
    - `POST /api/sessions`, `GET /api/sessions/{id}`, `PATCH /api/sessions/{id}` (session_notes), `POST /api/sessions/{id}/mom/draft`, `PATCH /api/sessions/{id}/mom` (review/edit/send)
    - `POST /api/sessions/{id}/files` (multipart), `GET /api/sessions/{id}/files`, `DELETE /api/sessions/{id}/files/{file_id}`
    - `POST /api/action-items`, `GET /api/action-items`, `PATCH /api/action-items/{id}`
    - `POST /api/check-ins`, `GET /api/check-ins`
- `frontend/src/lib/config.ts` — reads `NEXT_PUBLIC_API_URL` (set per env: `http://localhost:8000` dev, Cloudflare Pages env var prod)
- **CORS verification step**: confirm backend allows the frontend origin in dev and prod. If the existing backend CORS config (added in P2 or P3) does not allow the configured frontend origin, **flag back to SoJo before proceeding** — this is a backend change and does not happen silently in P6.

### 2.4 App router structure

```
frontend/src/app/
├── layout.tsx                              # root layout, fonts, providers
├── globals.css
├── (public)/
│   ├── layout.tsx                          # public shell
│   └── sign-in/page.tsx                    # Google OAuth start button
├── (app)/
│   ├── layout.tsx                          # protected shell — fetches /api/me, redirects to /sign-in if 401
│   ├── dashboard/page.tsx                  # today's sessions, recent clients, pending action items
│   ├── clients/
│   │   ├── page.tsx                        # client list
│   │   ├── new/page.tsx                    # new-client form (POST /clients → invite flow)
│   │   └── [clientId]/
│   │       ├── page.tsx                    # client detail (history, AST)
│   │       └── sessions/
│   │           ├── new/page.tsx            # start new session (POST /sessions)
│   │           └── [sessionId]/page.tsx    # session view (brief + notes + files + MOM editor)
│   ├── action-items/page.tsx               # cross-client action items
│   └── settings/sessions/page.tsx          # auth sessions list, revoke buttons
└── (dev)/
    └── motion-lab/page.tsx                 # demonstrates every motion primitive (gated)
```

Route group `(dev)` is rendered only when `process.env.NEXT_PUBLIC_DEV_ROUTES === "true"`. In production builds the route returns 404. This keeps the lab available locally without polluting the pilot deployment.

### 2.5 Screens — what each one shows

- **Sign-in (`/sign-in`)**: Centered card. Fraunces 900 wordmark "Parivarthan" (the only Marigold accent on this screen — under the wordmark). Manrope 400 tagline. One Moss Shadow button: "Continue with Google". Hits `/api/auth/google/start`.
- **Dashboard (`/dashboard`)**: Three sections, prose-led, no charts. **Today** (today's sessions; click → session view), **Recent clients** (last 5 with status), **Pending action items** (across clients, with overdue surfaced first). Empty states use Fraunces statement copy ("No sessions today. Quiet morning.") rather than illustrations. The Marigold goes on the primary empty-state CTA (e.g., "New session" when `Today` is empty), once per screen.
- **Client list (`/clients`)**: Table-style list with Manrope 700 column headers (eyebrow style, all-caps, letter-spaced) and Fraunces 700 client names. One Moss Shadow "New client" button in the header. No Marigold here — Marigold reserved for empty state.
- **Client detail (`/clients/[clientId]`)**: Two-column on desktop, stacked on mobile. Left: client meta (Manrope), session history list (Fraunces names + dates). Right: AST card (open items / missed items / status summary / triage flags). One Marigold accent line under the client's name (per brand guide rule "divider lines beneath the headline").
- **Session view (`/clients/[clientId]/sessions/[sessionId]`)** — the most complex screen, three tabs:
  1. **Pre-session brief** tab: Fraunces 900 headline ("Pre-session brief — M002, Friday, 09 May"). Body: Manrope 400 prose summary, with snippet count, AST condensed, recent check-ins. "Generate" button (Moss) if no brief exists; "Regenerate" if exists.
  2. **In-session notes** tab: Single full-width Manrope 400 textarea, autosave on blur via `PATCH /sessions/{id}`. File upload zone below — drag-drop or click — supports `.txt`, `.md`, `.pdf`, `.docx` (matches HANDOVER-P5 §File upload endpoints), 25 MB cap, list of uploaded files with delete buttons. Marigold not used here — too much editing for an accent.
  3. **MOM editor** tab: Two-pane on desktop (draft on left, edited on right) or stacked on mobile. "Generate draft" button (Moss) calls `POST /sessions/{id}/mom/draft`. Once draft exists, right pane becomes editable. **The single Marigold on this screen** is the "Send to client" button — it's the keystone action of the entire core cycle.
- **Action items (`/action-items`)**: Three filtered lists — Open, In progress, Missed. Manual transitions via dropdown (P5 ships manual; P7 will auto-flag missed). No Marigold (no single keystone here).
- **Settings → sessions (`/settings/sessions`)**: Active auth sessions table. Each row has user-agent, last-used timestamp, "Revoke" button (Moss). "Sign out everywhere" button at top (Moss outline variant). No Marigold.

### 2.6 Motion system

- `frontend/src/styles/motion.css` — keyframes for the four primitives:
  - `state_change`: hover/focus/click feedback. Tailwind utilities (`transition-transform`, `transition-opacity`, `duration-150`, `ease-out`). Animates `transform` and `opacity` only.
  - `reveal`: dropdowns, tooltips, popovers. Uses `tw-animate-css` defaults that ship with shadcn — already GPU-friendly.
  - `sheet_enter` / `sheet_exit`: 250ms / 200ms slide + fade for Sheet and Dialog.
  - `page_transition`: View Transitions API where supported, CSS cross-fade fallback otherwise. Feature detection via `if ('startViewTransition' in document)` — Firefox 130+ has it for same-document; older browsers get the fallback. The Marigold-marked CTA on each screen carries a stable `view-transition-name` so it animates as a single element across route changes — this is the brand-faithful version of "Marigold marks the eye."
- `frontend/src/lib/motion.ts` — token-driven constants (durations and easings) imported from generated tokens. Used wherever JS-driven motion is unavoidable (rare).
- **Banned at code level** (also in skill — see §2.7):
  - Animating `width`, `height`, `top`, `left`, `padding`, `margin`, `border-width`
  - `backdrop-filter` outside the one global app-bar (heavy on mobile Firefox)
  - Synchronous `<link>` Google Fonts loading — must use `next/font`
  - Scroll-triggered animations on more than one element per screen
  - Animations longer than 400ms
  - GIF or Lottie assets — CSS or SVG only
  - Framer Motion or any motion library beyond `tw-animate-css` (deferred until a real need shows up)

### 2.7 `/dev/motion-lab` — the judge surface

Single-page route showing every primitive with controls SoJo can interact with. Layout:

- **Section 1 — Palette swatches** (sanity check that theme.yaml compiled correctly): four large blocks with hex values and a contrast checker against the body text.
- **Section 2 — Type scale**: every Fraunces and Manrope weight from theme.yaml at the documented sizes from the brand guide §Type scale. Both Chromium and Firefox should render these identically — visual diff is a manual check.
- **Section 3 — State change demo**: a row of 6 buttons (Moss, Moss outline, Marigold accent, ghost, destructive, disabled) so SoJo can hover, focus, click each and feel the 150ms response.
- **Section 4 — Reveal demo**: dropdown, tooltip, popover with the 200ms timing.
- **Section 5 — Sheet/dialog demo**: open/close buttons for a Sheet (right-edge slide) and Dialog (centred fade-scale).
- **Section 6 — Page transition demo**: two linked routes within `/dev/motion-lab/` so SoJo can navigate and see the cross-fade + Marigold-element morph. Browser support badge shows whether the View Transitions API is in use or fallback.
- **Section 7 — Brand-rules checker**: live DOM scan of the current page reporting Marigold count, Dark Ink fill count, white-background offenders, font usage. Useful both on the lab itself and (in the standing test version) on every other screen.

This page is the *artifact* SoJo opens to judge motion. Sign-off on the lab gates progression to real screen builds.

### 2.8 `.claude/skills/parivarthan-frontend.md` — the brand-rules skill

Repo-scoped skill that Claude Code reads before touching any frontend file. Content shape:

- **§1 Palette rules**: the four colours and their precise usage rules from the brand guide, restated in implementation terms. Includes the linter assertions (max 1 Marigold, no white background, max 1 Dark Ink fill).
- **§2 Typography rules**: Fraunces for headlines, Manrope for body, weights to use per surface, minimum 13px body on screen.
- **§3 Motion rules**: the four primitives, the banned list (§2.6 above), the duration ceiling.
- **§4 shadcn token mapping**: explicit map from shadcn token names to brand colours; instruction to never hand-edit a shadcn component file (always extend or wrap).
- **§5 Per-screen checklist**: before claiming a screen done, Claude Code self-runs:
  - [ ] Manrope on body, Fraunces on headlines
  - [ ] At most one Marigold element
  - [ ] At most one Dark Ink fill (body text doesn't count)
  - [ ] No `bg-white` / `bg-[#FFFFFF]` anywhere
  - [ ] All transitions ≤ 400ms, on transform/opacity only
  - [ ] Mobile (375px) and desktop (1280px) both rendered correctly via Playwright
  - [ ] No Lighthouse perf budget regression
- **§6 When in doubt**: reach for Moss Shadow, not Dark Ink. Reach for paragraph, not heading. Reach for plain text, not graphic.

This skill is drafted as part of P6 deliverables (Claude Code writes the file based on this section as the brief) — SoJo reviews the rules before they bind any code.

### 2.9 `.claude/mcp_servers.json` — Playwright MCP

Add Playwright MCP to the repo-scoped MCP config. Browser configuration:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--browser", "chromium,firefox"],
      "env": {}
    }
  }
}
```

(Exact arg shape verified at install time; this is the intent — both browsers, headless by default, headful when SoJo wants to watch.)

### 2.10 Tests

- **`frontend/tests/e2e/`** — Playwright tests run against both Chromium and Firefox:
  - `auth.spec.ts` — sign-in redirect, callback handling, sign-out
  - `core-cycle.spec.ts` — the full happy-path acceptance from build-plan.md (sign in → dashboard → session → MOM → send → snippet appears in DB)
  - `mobile-375.spec.ts` — every screen at 375px, asserts no horizontal scroll, no clipped text
  - `brand-rules.spec.ts` — the standing linter, runs against every route in `routes.fixture.ts`. Asserts on each route, in each browser:
    - Count of elements with computed `background-color: rgb(232, 197, 71)` (Marigold) ∈ {0, 1}
    - No element has computed `background-color: rgb(255, 255, 255)` (white)
    - Count of elements with computed `background-color: rgb(44, 44, 30)` (Dark Ink) ≤ 1
    - `<h1>`, `<h2>`, `<h3>` computed `font-family` includes "Fraunces"
    - `<body>` computed `font-family` includes "Manrope"
- **`frontend/tests/unit/`** — Vitest:
  - API client schema parsing (Zod) — for each endpoint, golden-input → parses; bad-input → rejects with helpful error
  - Auth flow — `fetchWithAuth` refresh-once-then-redirect behaviour
  - Theme build script — `theme.yaml` → expected outputs (snapshot test on the generated files)

### 2.11 Performance budget

Manual verification via Lighthouse (Chromium, mobile 4G simulation), repeated for the dashboard route after first deploy:

- LCP < 2.0s
- CLS < 0.05
- INP < 200ms
- Initial JS bundle < 200KB gzipped
- Initial CSS bundle < 50KB gzipped (after theme + Tailwind tree-shake)

Firefox runtime correctness verified separately via Playwright (`page.evaluate(() => performance.getEntriesByType("navigation"))`) — same numerical targets, measurement asymmetry acknowledged. If Firefox numbers are dramatically worse than Chromium, that's a flag for investigation, not an automatic fail.

CI integration (Lighthouse CI on PRs) is **deferred to P8** when observability lands; manual perf check is sufficient at P6.

### 2.12 Handoff (gated behind SoJo's manual verification sign-off)

Once SoJo has walked the §6 verification checklist and signed off, Claude Code performs:

- Write `docs/HANDOVER-P6.md` — same shape as HANDOVER-P5.md: stack delta, repo layout delta, new conventions and patterns, all routes added, all tests added, env vars added (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEV_ROUTES`), known issues / carry-overs, current git state
- Append to `docs/SESSION_LOG.md` — a P6 completion entry: phases complete (P0–P6), test count delta, key decisions made (the ones in §3 below), notable bugs fixed, what P7 inherits
- Update `docs/REPO-INDEX.md` if the layout has changed in a way the index needs to reflect

**These handoffs do not happen on Claude Code's self-verification.** SoJo verifies first; only then does Claude Code write the handover docs.

---

## 3. Decisions made during this phase

(Resolved in the planning conversation, not pre-decided in any prior ADR. Recording here so they're auditable.)

**3.1 Brand-as-design-language for MVP** — Poshini Agasthya's brand identity (Parchment, Moss Shadow, Dark Ink, Marigold; Fraunces, Manrope) is hardcoded as Parivarthan's design language for the pilot. No theme provider, no per-HC theming. Re-evaluate at the User #2 onboarding milestone from ADR-0001.

**3.2 `theme.yaml` as token source of truth** — single editable YAML drives the design tokens, compiled to Tailwind theme + CSS variables via a build script. Justification: matches the repo's existing `llm_config.yaml` precedent for tweakable runtime config; runtime files stay standard Tailwind/CSS; one source of truth.

**3.3 Brand rule translations to UI patterns** — three brand-guide rules written for slides/posters/social translate to UI as:

- "Marigold appears exactly once per design" → at most one Marigold element per *screen*, reserved for the single keystone action of the user's current state (Send MOM, primary empty-state CTA, sign-in wordmark accent). The overall app has many CTAs; only one per screen at a time may be Marigold.
- "Dark Ink is used once per slide" → Dark Ink remains the body-text colour everywhere (the brand-guide-allowed "maximum contrast" use case); but at most one *architectural fill* per screen uses Dark Ink as a background or block.
- "Moss Shadow is a voice, not a wallpaper" → Moss Shadow lives in bounded blocks (cards, header bars, sidebars, accent lines). No full-bleed Moss Shadow surfaces.

These translations are made by Claude with SoJo's standing approval; they may be revised after the motion-lab review or after the first screens are built.

**3.4 shadcn token mapping** — `background=Parchment`, `foreground=Dark Ink`, `primary=Moss Shadow`, `accent=Marigold`. Default `<Button>` is Moss Shadow; Marigold lives only on `variant="accent"`.

**3.5 Motion library policy** — Tailwind transitions + `tw-animate-css` (already used by shadcn) + a small set of custom CSS keyframes. **No Framer Motion at MVP** — it is a 50KB+ dependency commonly misused into layout-thrashing patterns; not needed until orchestrated sequences become necessary.

**3.6 View Transitions API with CSS fallback** — used for page transitions where supported (Firefox 130+, Chromium 111+); CSS cross-fade fallback elsewhere. Feature-detected at runtime; never assumed.

**3.7 Strict-first interpretation of brand rules; loosen only with evidence** — when a brand rule is ambiguous in UI context, the strict interpretation wins until pilot use shows a specific friction. Loosening is a deliberate decision logged here, not a silent drift.

**3.8 Browser support: Chromium + Firefox in scope; Safari best-effort** — Playwright tests run in both Chromium and Firefox; WebKit/Safari is verified manually if SoJo or the pilot HC uses it but is not in the standing test matrix.

**3.9 Handover docs gated on manual verification** — `HANDOVER-P6.md` and `SESSION_LOG.md` updates are written by Claude Code only after SoJo has manually verified the acceptance criteria, not on Claude Code's self-check.

---

## 4. Bugs fixed mid-phase

*To be filled during build.*

---

## 5. Source docs consulted

- `docs/HANDOVER-P5.md` — current backend state, all endpoint surfaces, conventions locked in P0–P5, env vars
- `docs/build-plan.md` §Phase 6 — deliverables and acceptance criteria the screens must satisfy
- `docs/decisions/0001-stack-selection.md` — frontend stack lock (Next.js 15 / Tailwind / shadcn/ui), Cloudflare Pages hosting
- `docs/decisions/0004-repo-structure.md` — `frontend/` layout, `.claude/` conventions, `prompts/` separation
- `docs/decisions/0005-auth-strategy.md` — JWT in memory + refresh in HTTP-only cookie pattern frontend must honour
- `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` §Stages 2–6 — the user journey each screen expresses
- `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` — the API surface and conventions P5 just locked
- `docs/domain/glossary.md` — UI terminology (HC, client, session, MOM, AST, brief, snippet, M00N) — Claude Code reads this before writing any user-facing copy
- `Poshini_Brand_Colour_Guide_fina_.docx` — the design system source
- `docs/specs/template-phase-plan.md` — this file's structure

---

## 6. Verification

**Manual verification is performed by SoJo before any handover docs are written.** The criteria below are the contract; each one ticked on a real run, not asserted from logs.

### 6.1 From build-plan.md §Phase 6 (existing acceptance criteria)

- [ ] HC signs in → lands on dashboard
- [ ] Click into a session → see brief → run a mock session → MOM draft appears
- [ ] Edit MOM → click Send → MOM status updates to `sent`
- [ ] After send, query DB: a new row in `hc_style_snippets` reflects the edit (round-trip Phase 4 acceptance)
- [ ] Click into a client → see their AST, history
- [ ] Sign out → redirected to sign-in; refresh cookie cleared
- [ ] Mobile viewport (Chrome DevTools at 375px wide) is usable, not broken

### 6.2 New for P6 (added by this phase)

- [ ] All seven build-plan criteria above pass on **Firefox** as well as Chromium
- [ ] Performance budget on dashboard route: LCP < 2.0s, CLS < 0.05, INP < 200ms (Chromium / Lighthouse, mobile 4G sim)
- [ ] Initial JS bundle < 200KB gzipped, CSS bundle < 50KB gzipped on dashboard route
- [ ] Brand-rules linter (`brand-rules.spec.ts`) passes on every route in both browsers
- [ ] Motion-lab review: SoJo opens `/dev/motion-lab` and confirms each section feels right; logs any tweaks to `theme.yaml` motion tokens before sign-off
- [ ] Visual review of every screen at 375px and 1280px in both browsers — no clipping, no horizontal scroll, no missing fonts
- [ ] CORS verified between deployed frontend (Cloudflare Pages preview) and backend
- [ ] `theme.yaml` change → run build script → tokens flow through correctly to a rendered screen (smoke check)
- [ ] All Playwright tests passing in both browsers
- [ ] All Vitest unit tests passing
- [ ] `.claude/skills/parivarthan-frontend.md` written, content matches §2.8 above
- [ ] `.claude/mcp_servers.json` written, Playwright MCP configured
- [ ] `frontend/.env.example` documents `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEV_ROUTES`
- [ ] In a production build, `/dev/motion-lab` returns 404

### 6.3 Handover gates

After 6.1 and 6.2 are signed off:

- [ ] `docs/HANDOVER-P6.md` written matching HANDOVER-P5 shape
- [ ] `docs/SESSION_LOG.md` updated with P6 completion entry
- [ ] `docs/REPO-INDEX.md` updated if layout changed
- [ ] Test count and migration count recorded in HANDOVER-P6 §Current git state

---

## 7. Lessons learned

*To be filled at completion.*

---

## 8. Carry-over to subsequent phases

Known carry-overs that downstream phases inherit:

- **`frontend/theme.yaml` + build script** — the pattern is reusable for any future styling needs. Future phases adding screens should add tokens to `theme.yaml`, never hand-edit Tailwind config or globals.
- **`.claude/skills/parivarthan-frontend.md`** — every future frontend phase reads this. P7+ frontend work that violates the skill's rules without an explicit decision logged here is a rule-1 (laziness) failure.
- **`.claude/mcp_servers.json` Playwright entry** — P8 (observability) and P9 (smoke gate) can reuse this MCP for production-config visual checks against staging.
- **API client structure (`frontend/src/lib/api/*`)** — every new endpoint added in P7+ extends this layer; never call `fetch` directly from a component.
- **Auth pattern (`fetchWithAuth`, in-memory access token, silent refresh)** — locked in. P7+ uses this; the pattern is not relitigated unless ADR-0005 is updated.
- **Performance budget** — once established, P7+ must not regress LCP, CLS, INP, or bundle size on the dashboard route. P8 will add CI enforcement.
- **Handover-doc-after-manual-verification convention** — applies to P7, P8, P9.

*Additional carry-overs to be filled at completion as the build surfaces them.*

---

# Part B — Dashboard Restructure + Action Items Kanban

**Status**: Complete
**Session**: Brainstormed and designed 2026-05-12
**Implements**: `frontend_feedback.md` Items 2 and 6
**Backend changes**: None — all existing APIs
**New dependencies**: None

---

## B.1 Scope

Two frontend-only changes to `dashboard/page.tsx` and `action-items/page.tsx`. No migrations, no backend endpoints, no new npm packages.

---

## B.2 Item 2 — Dashboard Restructure

**File**: `frontend/src/app/(app)/dashboard/page.tsx`

### What changes

Remove the "Recent Clients" section entirely. Dashboard retains two sections only:

1. **Today** — unchanged
2. **Pending Action Items** — rows restructured

### Pending Action Items row layout

Each item renders two lines:

```
Ravi Kumar  ·  12/05/2026        ← client full_name + created_at (en-IN locale, DD/MM/YYYY)
Protein tracking log              ← description
```

### Data sources — no new fetches

- `clientMap: Map<string, ClientOut>` — already built from the existing `listClients` call (kept because Today section still needs it for client names on session rows)
- `item.created_at` — present on `ActionItemOut`
- `item.description` — present on `ActionItemOut`
- `item.client_id` — key for `clientMap` lookup

### Definition of done

- "Recent Clients" section and `clients` / `setClients` state removed
- `setClients(c.items.slice(0, 5))` line removed from `useEffect .then()`; `listClients` fetch stays
- Each pending item row: `{full_name} · {created_at formatted}` line 1, `{description}` line 2
- Overdue items retain existing red date treatment

---

## B.3 Item 6 — Action Items Kanban

**File**: `frontend/src/app/(app)/action-items/page.tsx`

### What changes

Replace the three-section vertical list (Open / In Progress / Missed) with a single client×status table.

### Table structure

| Client     | Open         | In Progress  | Done         |
| ---------- | ------------ | ------------ | ------------ |
| Ravi Kumar | item cards… | item cards… | item cards… |
| Sunita Rao | item cards… | item cards… | —           |

- **Rows**: one per client (grouped by `client_id`); clients with zero items across all columns are hidden
- **Columns**: Open · In Progress · Done — 3 fixed columns
- **Missed/overdue items** live in Open column — red card border + "Overdue" label; no 4th column
- **Empty cells** render a muted `—`
- Table is `overflow-x-auto` for narrow viewports

### Item card anatomy

```
┌──────────────────────────────┐
│ Protein tracking log         │  ← description
│ 08 May 2026        Overdue   │  ← created_at + overdue label if applicable
│ Move to In Progress →        │  ← forward action
│ ← Back to Open               │  ← backward action (In Progress and Done only)
└──────────────────────────────┘
```

### Click-to-move actions by column

| Column      | Forward                  | Backward          |
| ----------- | ------------------------ | ----------------- |
| Open        | "Move to In Progress →" | —                |
| In Progress | "Mark Done →"           | "← Back to Open" |
| Done        | —                       | "← Reopen"       |

Each button calls `patchActionItem(item.id, { status: targetStatus })` with optimistic local state update; reverts on error.

### Status transition map

```ts
const MOVE_FORWARD: Record<string, string> = {
  open:        "in_progress",
  missed:      "in_progress",  // missed items can advance
  in_progress: "completed",
}
const MOVE_BACK: Record<string, string> = {
  in_progress: "open",
  completed:   "in_progress",
}
```

### Data fetching

```ts
Promise.all([
  listActionItems({ status: "open",        limit: 100 }),
  listActionItems({ status: "in_progress", limit: 100 }),
  listActionItems({ status: "missed",      limit: 100 }),
  listActionItems({ status: "completed",   limit: 100 }),
  listClients({ limit: 100 }),  // for display names + row grouping
])
```

`missed` items are merged into the `open` bucket for display (red card treatment).

### Grouping logic

```ts
clientRows = clients
  .map(client => ({
    client,
    open:        items.filter(i => i.client_id === client.id && (i.status === "open" || i.status === "missed")),
    in_progress: items.filter(i => i.client_id === client.id && i.status === "in_progress"),
    done:        items.filter(i => i.client_id === client.id && i.status === "completed"),
  }))
  .filter(row => row.open.length + row.in_progress.length + row.done.length > 0)
```

### Definition of done

- Table renders one row per client with ≥1 item (any status)
- Items group correctly; missed items appear in Open column with red treatment
- All click-to-move buttons PATCH the correct status and update state optimistically
- Optimistic revert on error
- Empty cells show `—`
- Table scrolls horizontally on narrow screens
- No new npm dependencies

---

## B.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the dashboard (remove Recent Clients, enrich pending item rows) and replace the action items page with a client×status kanban table.

**Architecture:** Three tasks, three commits. Task 1 is a pure template edit to `dashboard/page.tsx`. Tasks 2–3 build the kanban: grouping logic is extracted to `lib/actionItemsKanban.ts` (tested in isolation before the page is touched), then the page is replaced. Zero backend changes. Zero new dependencies.

**Tech Stack:** Next.js 16.2.4, React, Tailwind v4, shadcn/ui, Vitest (unit tests), Playwright (e2e)

---

### Task 1: Dashboard restructure

**Files:**

- Modify: `frontend/src/app/(app)/dashboard/page.tsx`

No new unit tests — this is a template-only change. Existing Playwright `core-cycle.spec.ts` covers the dashboard render path.

- [ ] **Step 1: Replace `dashboard/page.tsx` with the following**

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listSessions, type SessionOut } from "@/lib/api/sessions";
import { listClients, type ClientOut } from "@/lib/api/clients";
import { listActionItems, type ActionItemOut } from "@/lib/api/actionItems";

function isToday(iso: string): boolean {
  return new Date(iso).toDateString() === new Date().toDateString();
}

function isOverdue(dateStr: string | null): boolean {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date(new Date().toDateString());
}

export default function DashboardPage() {
  const [todaySessions, setTodaySessions] = useState<SessionOut[] | null>(null);
  const [clientMap, setClientMap] = useState<Map<string, ClientOut>>(new Map());
  const [actionItems, setActionItems] = useState<ActionItemOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    Promise.all([
      listSessions({ limit: 50 }),
      listClients({ limit: 100 }),
      listActionItems({ status: "open", limit: 20 }),
    ])
      .then(([s, c, a]) => {
        setTodaySessions(s.items.filter((x) => isToday(x.scheduled_at)));
        setClientMap(new Map(c.items.map((cl) => [cl.id, cl])));
        const sorted = [...a.items].sort((x, y) => {
          return (isOverdue(x.due_date) ? 0 : 1) - (isOverdue(y.due_date) ? 0 : 1);
        });
        setActionItems(sorted);
      })
      .catch(() => setLoadError(true));
  }, []);

  const loading = !loadError && todaySessions === null;
  const todayEmpty = !loading && !loadError && todaySessions?.length === 0;
  const showMarigold = todayEmpty;

  return (
    <div className="space-y-10">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          {new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Dashboard
        </h1>
      </div>

      {/* Section 1 — Today */}
      <section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
        <h2 className="font-heading text-xl font-bold text-foreground">Today</h2>
        <Separator />
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : loadError ? (
          <p className="font-sans text-sm text-destructive">Could not load sessions.</p>
        ) : todaySessions!.length === 0 ? (
          <div className="flex flex-col items-start gap-5 py-4">
            <p className="font-heading text-2xl font-black text-muted-foreground">
              No sessions today. <em>Quiet morning.</em>
            </p>
            <Link
              href="/clients"
              className={cn(buttonVariants({ variant: showMarigold ? "accent" : "default" }))}
            >
              New session
            </Link>
          </div>
        ) : (
          <ul className="space-y-2">
            {todaySessions!.map((sess) => (
              <li key={sess.id}>
                <Link
                  href={`/clients/${sess.client_id}/sessions/${sess.id}`}
                  className="flex items-center justify-between rounded-lg border border-border px-4 py-3 transition-colors duration-150 hover:bg-muted"
                >
                  <div>
                    <p className="font-heading text-base font-bold text-foreground">
                      {clientMap.get(sess.client_id)?.full_name ?? "—"} · Session {sess.session_number}
                    </p>
                    <p className="font-sans text-sm text-muted-foreground">
                      {new Date(sess.scheduled_at).toLocaleTimeString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  {sess.ended_at ? (
                    <Badge variant="secondary">Ended</Badge>
                  ) : sess.started_at ? (
                    <Badge>In progress</Badge>
                  ) : (
                    <Badge variant="outline">Scheduled</Badge>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Section 2 — Pending action items */}
      <section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
        <h2 className="font-heading text-xl font-bold text-foreground">
          Pending action items
        </h2>
        <Separator />
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : actionItems?.length === 0 ? (
          <p className="py-2 font-heading text-xl font-black text-muted-foreground">
            All clear. <em>Nothing pending.</em>
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {actionItems?.map((item) => (
              <li key={item.id} className="py-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 space-y-0.5">
                    <p className="font-sans text-xs font-bold text-muted-foreground">
                      {clientMap.get(item.client_id)?.full_name ?? "—"}
                      {" · "}
                      {new Date(item.created_at).toLocaleDateString("en-IN")}
                    </p>
                    <p className="font-sans text-sm text-foreground">{item.description}</p>
                    {item.due_date && (
                      <p
                        className={cn(
                          "font-sans text-xs",
                          isOverdue(item.due_date)
                            ? "font-bold text-destructive"
                            : "text-muted-foreground",
                        )}
                      >
                        Due {new Date(item.due_date).toLocaleDateString("en-IN")}
                        {isOverdue(item.due_date) && " · Overdue"}
                      </p>
                    )}
                  </div>
                  <Link href={`/clients/${item.client_id}`}>
                    <Badge variant="outline" className="shrink-0">View client</Badge>
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Run Vitest — confirm no regressions**

```bash
cd frontend && npx vitest run
```

Expected: all existing tests pass (count unchanged — no new tests for this task).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/(app)/dashboard/page.tsx
git commit -m "feat(frontend): restructure dashboard — remove Recent Clients, enrich pending items rows"
```

---

### Task 2: Extract and test kanban grouping logic

**Files:**

- Create: `frontend/src/lib/actionItemsKanban.ts`
- Create: `frontend/tests/unit/actionItemsKanban.test.ts`

- [ ] **Step 1: Write the failing unit test**

Create `frontend/tests/unit/actionItemsKanban.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { groupByClient, MOVE_FORWARD, MOVE_BACK } from "@/lib/actionItemsKanban";
import type { ClientOut } from "@/lib/api/clients";
import type { ActionItemOut } from "@/lib/api/actionItems";

const NOW = new Date().toISOString();

function makeClient(id: string): ClientOut {
  return {
    id,
    hc_user_id: "hc-1",
    full_name: `Client ${id}`,
    code: null,
    email: null,
    phone: null,
    timezone: null,
    journey_stage: "active",
    course_start_date: null,
    course_end_date: null,
    course_goal: null,
    created_at: NOW,
    updated_at: NOW,
  };
}

function makeItem(id: string, clientId: string, status: string): ActionItemOut {
  return {
    id,
    client_id: clientId,
    session_id: null,
    hc_user_id: "hc-1",
    description: `Item ${id}`,
    due_date: null,
    status,
    completed_at: null,
    created_at: NOW,
  };
}

describe("groupByClient", () => {
  it("routes open/in_progress/completed items to correct columns", () => {
    const clients = [makeClient("c1"), makeClient("c2")];
    const items = [
      makeItem("i1", "c1", "open"),
      makeItem("i2", "c1", "in_progress"),
      makeItem("i3", "c1", "completed"),
      makeItem("i4", "c2", "missed"),
    ];
    const rows = groupByClient(clients, items);

    expect(rows).toHaveLength(2);
    const c1 = rows.find((r) => r.client.id === "c1")!;
    expect(c1.open.map((i) => i.id)).toEqual(["i1"]);
    expect(c1.in_progress.map((i) => i.id)).toEqual(["i2"]);
    expect(c1.done.map((i) => i.id)).toEqual(["i3"]);

    const c2 = rows.find((r) => r.client.id === "c2")!;
    expect(c2.open.map((i) => i.id)).toEqual(["i4"]);
    expect(c2.in_progress).toHaveLength(0);
    expect(c2.done).toHaveLength(0);
  });

  it("places missed items in the open column", () => {
    const rows = groupByClient(
      [makeClient("c1")],
      [makeItem("i1", "c1", "missed")],
    );
    expect(rows[0].open).toHaveLength(1);
    expect(rows[0].open[0].status).toBe("missed");
  });

  it("omits clients with zero items across all columns", () => {
    const rows = groupByClient(
      [makeClient("c1"), makeClient("c2")],
      [makeItem("i1", "c1", "open")],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].client.id).toBe("c1");
  });

  it("returns empty array when items list is empty", () => {
    expect(groupByClient([makeClient("c1")], [])).toHaveLength(0);
  });
});

describe("MOVE_FORWARD", () => {
  it("open → in_progress", () => expect(MOVE_FORWARD["open"]).toBe("in_progress"));
  it("missed → in_progress", () => expect(MOVE_FORWARD["missed"]).toBe("in_progress"));
  it("in_progress → completed", () => expect(MOVE_FORWARD["in_progress"]).toBe("completed"));
  it("completed has no forward target", () => expect(MOVE_FORWARD["completed"]).toBeUndefined());
});

describe("MOVE_BACK", () => {
  it("in_progress → open", () => expect(MOVE_BACK["in_progress"]).toBe("open"));
  it("completed → in_progress", () => expect(MOVE_BACK["completed"]).toBe("in_progress"));
  it("open has no back target", () => expect(MOVE_BACK["open"]).toBeUndefined());
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd frontend && npx vitest run tests/unit/actionItemsKanban.test.ts
```

Expected: FAIL — `Cannot find module '@/lib/actionItemsKanban'`

- [ ] **Step 3: Create the utility file**

Create `frontend/src/lib/actionItemsKanban.ts`:

```ts
import type { ClientOut } from "@/lib/api/clients";
import type { ActionItemOut } from "@/lib/api/actionItems";

export const MOVE_FORWARD: Record<string, string> = {
  open:        "in_progress",
  missed:      "in_progress",
  in_progress: "completed",
};

export const MOVE_BACK: Record<string, string> = {
  in_progress: "open",
  completed:   "in_progress",
};

export type ClientRow = {
  client: ClientOut;
  open: ActionItemOut[];
  in_progress: ActionItemOut[];
  done: ActionItemOut[];
};

export function groupByClient(
  clients: ClientOut[],
  items: ActionItemOut[],
): ClientRow[] {
  return clients
    .map((client) => ({
      client,
      open: items.filter(
        (i) => i.client_id === client.id && (i.status === "open" || i.status === "missed"),
      ),
      in_progress: items.filter(
        (i) => i.client_id === client.id && i.status === "in_progress",
      ),
      done: items.filter(
        (i) => i.client_id === client.id && i.status === "completed",
      ),
    }))
    .filter((row) => row.open.length + row.in_progress.length + row.done.length > 0);
}
```

- [ ] **Step 4: Run tests — confirm all pass**

```bash
cd frontend && npx vitest run tests/unit/actionItemsKanban.test.ts
```

Expected: 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/actionItemsKanban.ts frontend/tests/unit/actionItemsKanban.test.ts
git commit -m "feat(frontend): add groupByClient + kanban transition maps with unit tests"
```

---

### Task 3: Implement the action items kanban page

**Files:**

- Modify: `frontend/src/app/(app)/action-items/page.tsx`

- [ ] **Step 1: Replace `action-items/page.tsx` with the following**

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { listActionItems, patchActionItem, type ActionItemOut } from "@/lib/api/actionItems";
import { listClients, type ClientOut } from "@/lib/api/clients";
import {
  groupByClient,
  MOVE_FORWARD,
  MOVE_BACK,
  type ClientRow,
} from "@/lib/actionItemsKanban";

function isOverdue(item: ActionItemOut): boolean {
  if (item.status === "missed") return true;
  if (!item.due_date) return false;
  return new Date(item.due_date) < new Date(new Date().toDateString());
}

function ItemCard({
  item,
  onMove,
}: {
  item: ActionItemOut;
  onMove: (id: string, newStatus: string) => void;
}) {
  const [transitioning, setTransitioning] = useState(false);
  const overdue = isOverdue(item);
  const forward = MOVE_FORWARD[item.status];
  const back = MOVE_BACK[item.status];

  async function handleMove(targetStatus: string) {
    const originalStatus = item.status;
    onMove(item.id, targetStatus); // optimistic
    setTransitioning(true);
    try {
      await patchActionItem(item.id, { status: targetStatus });
    } catch {
      onMove(item.id, originalStatus); // revert on error
    } finally {
      setTransitioning(false);
    }
  }

  return (
    <div
      className={cn(
        "rounded-lg border p-3 space-y-1.5 text-sm",
        overdue ? "border-destructive/40 bg-destructive/5" : "border-border bg-background",
      )}
    >
      <p
        className={cn(
          "font-sans font-medium leading-snug",
          item.status === "completed"
            ? "line-through text-muted-foreground"
            : "text-foreground",
        )}
      >
        {item.description}
      </p>
      <p
        className={cn(
          "font-sans text-xs",
          overdue ? "font-bold text-destructive" : "text-muted-foreground",
        )}
      >
        {new Date(item.created_at).toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
          year: "numeric",
        })}
        {overdue && " · Overdue"}
      </p>
      {transitioning ? (
        <p className="font-sans text-xs text-muted-foreground">Moving…</p>
      ) : (
        <div className="flex flex-wrap gap-3 pt-0.5">
          {back && (
            <button
              onClick={() => handleMove(back)}
              className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
            >
              {back === "open" ? "← Back to Open" : "← Reopen"}
            </button>
          )}
          {forward && (
            <button
              onClick={() => handleMove(forward)}
              className="font-sans text-xs text-primary underline-offset-4 hover:underline"
            >
              {forward === "in_progress" ? "Move to In Progress →" : "Mark Done →"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Cell({
  items,
  onMove,
}: {
  items: ActionItemOut[];
  onMove: (id: string, newStatus: string) => void;
}) {
  if (items.length === 0)
    return <span className="font-sans text-sm text-muted-foreground">—</span>;
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <ItemCard key={item.id} item={item} onMove={onMove} />
      ))}
    </div>
  );
}

export default function ActionItemsPage() {
  const [allItems, setAllItems] = useState<ActionItemOut[] | null>(null);
  const [clients, setClients] = useState<ClientOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    Promise.all([
      listActionItems({ status: "open",        limit: 100 }),
      listActionItems({ status: "in_progress", limit: 100 }),
      listActionItems({ status: "missed",      limit: 100 }),
      listActionItems({ status: "completed",   limit: 100 }),
      listClients({ limit: 100 }),
    ])
      .then(([open, inProgress, missed, done, clientsResult]) => {
        setAllItems([
          ...open.items,
          ...inProgress.items,
          ...missed.items,
          ...done.items,
        ]);
        setClients(clientsResult.items);
      })
      .catch(() => setLoadError(true));
  }, []);

  const handleMove = useCallback((id: string, newStatus: string) => {
    setAllItems((prev) =>
      prev ? prev.map((i) => (i.id === id ? { ...i, status: newStatus } : i)) : prev,
    );
  }, []);

  const loading = allItems === null && clients === null && !loadError;
  const rows: ClientRow[] =
    allItems && clients ? groupByClient(clients, allItems) : [];

  return (
    <div className="space-y-10">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Accountability
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Action items
        </h1>
      </div>

      {loadError && (
        <p className="font-sans text-sm text-destructive">
          Could not load action items.
        </p>
      )}

      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      )}

      {!loading && !loadError && rows.length === 0 && (
        <p className="py-2 font-heading text-xl font-black text-muted-foreground">
          All clear. <em>No active items.</em>
        </p>
      )}

      {!loading && !loadError && rows.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted">
                <th className="w-36 p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                  Client
                </th>
                <th className="p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground border-l border-border">
                  Open
                </th>
                <th className="p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground border-l border-border">
                  In Progress
                </th>
                <th className="p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground border-l border-border">
                  Done
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.client.id}
                  className="border-b border-border last:border-0 align-top"
                >
                  <td className="p-4">
                    <Link
                      href={`/clients/${row.client.id}`}
                      className="font-heading text-sm font-bold text-foreground underline-offset-4 hover:underline"
                    >
                      {row.client.full_name}
                    </Link>
                  </td>
                  <td className="p-4 border-l border-border">
                    <Cell items={row.open} onMove={handleMove} />
                  </td>
                  <td className="p-4 border-l border-border">
                    <Cell items={row.in_progress} onMove={handleMove} />
                  </td>
                  <td className="p-4 border-l border-border">
                    <Cell items={row.done} onMove={handleMove} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run all Vitest unit tests**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass (11 from Task 2 + all pre-existing tests).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/(app)/action-items/page.tsx
git commit -m "feat(frontend): replace action items list with client×status kanban table"
```

---

## B.4 Verification

- [ ] Dashboard shows exactly two sections: Today and Pending Action Items
- [ ] Each pending item row shows `{client_name} · {date}` on line 1 and `{description}` on line 2
- [ ] Overdue pending items still show red date text
- [ ] Action items page renders as a table with correct client rows
- [ ] Items appear in correct columns; missed items appear in Open with red styling
- [ ] Moving Open → In Progress via button updates the card to In Progress column
- [ ] Moving In Progress → Done via button updates the card to Done column
- [ ] Moving backwards (← Reopen, ← Back to Open) works correctly
- [ ] Optimistic update reverts if the PATCH fails
- [ ] All existing Playwright e2e tests still pass

---

# Part C — Diet Chart Feature

**Status**: Complete
**Phase label**: P6C
**Implements**: `frontend_feedback.md` Item 5
**Brainstorm date**: 2026-05-12

---

## C.1 Scope

A diet chart feature for the HC, per client. Stays in Unit 001 (HC-facing only). Full 3-layer build: backend CRUD + LLM generation + frontend. **Zero new migrations** — all four tables (`diet_charts`, `diet_chart_recipes`, `prep_recipes`, `content_assignments`) were created in P1.

`diet_chart_recipes` and `prep_recipes` are not used in P6C. They exist for a future recipe-library concept; P6C stores the entire chart grid in the `parameters` JSONB field on `diet_charts`. YAGNI.

---

## C.2 Design decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Per-client or per-session? | **Per-client, one active chart updated in place.** The day × meal-slot skeleton stays; only cell content changes over time. Provision for adding/removing meal slot columns. |
| 2 | What does AI draw from? | **Selected HC template + client session notes.** HC maintains a template library (uploaded as CSV). When generating for a client, HC picks the best-fit template; AI personalises it using the client's M000 intake notes and session 1 summary. Basic library lookup now; RAG-over-charts is a future enhancement. |
| 3 | HC approval flow? | **Edit-first, then save.** AI generates the chart directly into an inline-editable table. HC edits cells freely, then clicks "Save chart." No separate confirm step. |
| 4 | Editable table mechanics? | **Inline cell editing.** Each cell is editable in place — no edit-mode toggle needed. |
| 5 | Client-facing? | **Internal HC tooling in P6C.** Client-visible chart is Unit_002 scope. |
| 6 | MOM reference? | **One appended line.** If the client has an active diet chart, the MOM generation prompt appends: `"Note: A diet chart has been prepared for this client."` |

---

## C.3 Data model

### Templates and client charts — same table, distinguished by flag

Both live in `diet_charts`. The `parameters` JSONB field carries the full structure:

**Template record** (`parameters.is_template: true`):
```json
{
  "is_template": true,
  "template_key": "high-protein-low-carb",
  "meal_slots": ["Breakfast", "Morning Snack", "Lunch", "Evening Snack", "Dinner"],
  "grid": {
    "Monday":    { "Breakfast": { "food": "3-egg omelette", "timing": "7:30 AM" }, "Lunch": { "food": "Grilled chicken + salad", "timing": "1:00 PM" } },
    "Tuesday":   { ... },
    "Wednesday": { ... },
    "Thursday":  { ... },
    "Friday":    { ... },
    "Saturday":  { ... },
    "Sunday":    { ... }
  }
}
```

**Client chart record** (`parameters.is_template: false`):
```json
{
  "is_template": false,
  "template_ref": "<template diet_chart.id used for generation>",
  "generation_status": "ok | fallback",
  "meal_slots": ["Breakfast", "Morning Snack", "Lunch", "Dinner"],
  "grid": { ... }
}
```

### Linking chart to client

`content_assignments` row created when a chart is saved for a client:

```
content_type = 'diet_chart'
content_id   = <diet_chart.id>
client_id    = <client.id>
hc_user_id   = <hc.id>
session_id   = <session.id if triggered from a session, else null>
```

**One active chart per client** — enforced in application code: when a new chart is generated, the previous `diet_chart` record for that client (found via `content_assignments`) has its `archived_at` set before the new one is inserted. No DB constraint needed.

### CSV upload format

Row 1 = header: `Day, <MealSlot1>, <MealSlot2>, ...`
Rows 2–8 = days: `Monday` through `Sunday`
Cells = `"food · timing"` (space-middot-space separator; if only food, timing is empty string)
Meal slot names are taken directly from the header row — HC controls them. Parser treats whatever headers are present as the `meal_slots` array.

---

## C.4 Backend

**New file**: `backend/src/api/diet_charts.py`
**Register in**: `backend/src/main.py`

### Endpoints

| Method | Path | Body / Params | Returns |
|--------|------|---------------|---------|
| `GET` | `/api/diet-chart-templates` | — | `PaginatedList[DietChartTemplateOut]` |
| `POST` | `/api/diet-chart-templates` | multipart: `file` (CSV) | `DietChartTemplateOut` |
| `DELETE` | `/api/diet-chart-templates/{id}` | — | 204 |
| `POST` | `/api/clients/{client_id}/diet-chart/generate` | `{"template_id": "<uuid>"}` | `DietChartOut` |
| `GET` | `/api/clients/{client_id}/diet-chart` | — | `DietChartOut` \| 404 |
| `PATCH` | `/api/clients/{client_id}/diet-chart` | `{"parameters": {...}}` | `DietChartOut` |

All endpoints scoped to `hc_user_id` from JWT (`TenantDep`). Ownership verified before any read/write.

### Schema classes

```python
class DietChartTemplateOut(BaseModel):
    id: UUID
    name: str
    template_key: str
    meal_slots: list[str]
    created_at: datetime
    model_config = {"from_attributes": True}

class DietChartOut(BaseModel):
    id: UUID
    name: str
    parameters: dict          # full grid + meal_slots + is_template + generation_status
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class GenerateRequest(BaseModel):
    template_id: UUID

class PatchRequest(BaseModel):
    parameters: dict
```

### CSV parser

`backend/src/api/diet_charts.py` — `_parse_csv(file_bytes) -> dict`:
- Reads header row → `meal_slots`
- Reads rows 2–8 → `grid[day][slot] = {"food": ..., "timing": ...}` (split on ` · `)
- Raises `400` with clear message if header missing, fewer than 7 day rows, or unparseable cell

---

## C.5 LLM generation

**Prompt file**: `backend/prompts/diet_chart_generate_v1.md`
(YAML frontmatter: `version: 1`, `created: 2026-05-12`, `task: diet_chart_generate`)

**Inputs assembled at call time**:
1. Selected template's `parameters.grid` as JSON
2. Client's M000 session notes (`sessions.session_notes` where `session_number = 0`)
3. Session 1 summary / MOM draft text (if exists)

**Instruction** (prompt body):
> You are a health coach diet planning assistant. The HC has selected the template below as a starting point. Personalise it for this specific client based on their intake notes and first session summary. Adjust meal timings to fit the client's schedule, flag any foods that conflict with stated health conditions or preferences, and keep the exact same meal slot structure as the template. Return only valid JSON matching the template grid structure exactly — no explanation, no markdown fences.

**Output validation**: Pydantic model asserting all 7 days present, all meal slots present, each cell has `food` (string) and `timing` (string). One retry with stricter format hint if validation fails. Writes one `llm_calls` row on every attempt (success or failure) per ADR-0006.

**Fallback behaviour** (if LLM returns malformed JSON after retry):
- Return template grid unchanged
- Set `parameters.generation_status = "fallback"`
- Emit `warn`-level structured log: `event = "diet_chart.generate.fallback"`, include `client_id`, `template_id`, `prompt_version`, truncated raw response (≤ 500 chars)
- Call `sentry_sdk.capture_message("diet_chart.generate.fallback", level="warning", extras={...})`
- API response includes `generation_status: "fallback"` so frontend can show the amber banner

This pattern — warn log + Sentry capture_message + response flag — is the **platform standard for application-level graceful degradations**. See SESSION_LOG 2026-05-12 observability gap note; ADR-0006 amendment pending.

---

## C.6 Frontend

### New files

| File | Purpose |
|------|---------|
| `frontend/src/lib/api/dietCharts.ts` | API client: `listTemplates`, `uploadTemplate`, `deleteTemplate`, `generateChart`, `getChart`, `patchChart` |
| `frontend/src/app/(app)/settings/diet-chart-templates/page.tsx` | Template library management page |
| `frontend/src/app/(app)/clients/[clientId]/diet-chart/page.tsx` | Full chart editor page |

### Modified files

| File | Change |
|------|--------|
| `frontend/src/app/(app)/clients/[clientId]/page.tsx` | Add "Diet Chart" section at bottom |

---

### Surface 1 — `/settings/diet-chart-templates`

Added under Settings nav. Shows:

- Table: template name, `template_key`, meal slot count, uploaded date, Delete button (archive, not hard delete)
- "Upload template" button → native file picker (CSV only) → parsed preview (mini read-only grid, first 2 days) → "Confirm upload" → POST → row added to table
- Empty state: "No templates yet. Upload your first diet chart template to get started."

---

### Surface 2 — Client detail page diet chart section

Appended below existing sections on `clients/[clientId]/page.tsx`.

**No chart exists:**
```
Diet Chart
──────────
[Template: dropdown ▾]   [Generate]
```
Template dropdown lists HC's templates by name. "Generate" → calls `/generate` → loading skeleton → inline editable table appears below → "Save chart" button.

**Chart exists:**
```
Diet Chart                              [Edit chart →]
──────────
Mon  Breakfast: 3-egg omelette · 7:30 AM
     Lunch: Grilled chicken · 1:00 PM
Tue  Breakfast: Poha · 8:00 AM
     ...  (2-day preview, read-only)
```
"Edit chart →" links to `/clients/{id}/diet-chart`.

**Fallback amber banner** (when `generation_status === "fallback"`):
> AI generation had an issue — template loaded as starting point. The team has been notified. Edit the chart before saving.

---

### Surface 3 — `/clients/{clientId}/diet-chart`

Full-screen editor. Fetches the active chart on mount.

**Table layout**: rows = days (Mon–Sun), columns = meal slots. Each cell has two lines: food (editable `input`) and timing (editable `input`, smaller text). Tab/Enter navigates between cells.

**Column controls**: "＋ Add meal slot" appends a new column (HC names it). "×" on any column header removes it (with confirmation if cells are non-empty).

**Actions**:
- "Save chart" — PATCH `/api/clients/{id}/diet-chart` with updated `parameters`. Success toast: "Chart saved."
- "Regenerate with different template" — opens template picker inline; on confirm, calls `/generate` again (previous chart archived, new one loaded).

**Optimistic save**: table stays editable during the PATCH; "Saving…" text on button; revert + error toast if PATCH fails.

---

## C.7 MOM integration

In `backend/prompts/mom_v*.md` system section, add:

```
{%- if client_has_diet_chart %}
Note: A diet chart has been prepared for this client.
{%- endif %}
```

The MOM draft endpoint checks `GET /clients/{id}/diet-chart` (reuses the DB query, no extra HTTP call) and passes `client_has_diet_chart: bool` to the prompt assembly.

---

## C.8 Out of scope in P6C

- Sending chart to client (Unit_002)
- `prep_recipes` / `diet_chart_recipes` recipe library (future)
- Per-cell nutritional metadata (future)
- RAG-over-past-charts (future — library lookup is template-only in P6C)
- Chart versioning / history (future)
- Template sharing across HCs (future)

---

## C.9 Acceptance criteria

- [ ] HC uploads a CSV template → template appears in `/settings/diet-chart-templates` list
- [ ] HC selects template, clicks Generate on client detail page → editable chart appears within 10s
- [ ] `llm_calls` row written with `prompt_version = "diet_chart_generate_v1"`, all required fields populated
- [ ] HC edits cells inline → "Save chart" → PATCH succeeds → reloading the page shows the edited values
- [ ] HC adds a meal slot column → column persists after save
- [ ] Fallback path: mock LLM returning malformed JSON → template grid returned unchanged, `generation_status = "fallback"`, amber banner shown, `warn` log emitted, Sentry message captured
- [ ] Client detail page shows 2-day preview when chart exists
- [ ] "Edit chart →" navigates to full editor
- [ ] Generating a second chart for same client archives the first (`archived_at` set on old `diet_chart` record)
- [ ] HC2 cannot read HC1's templates or client charts (tenant isolation)
- [ ] MOM draft for a client with an active chart contains the "diet chart has been prepared" line
- [ ] MOM draft for a client with no chart does NOT contain that line
- [ ] Deleting a template in the library does not affect client charts that were generated from it (`template_ref` is just an ID — it's a historical reference, not a live foreign key constraint)

---

## C.10 Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement task-by-task. Steps use `- [ ]` syntax for tracking.

**Goal:** Add diet chart feature end-to-end: HC uploads CSV templates, AI personalises a template per client, HC edits the 7-day grid inline, MOM draft notes when a chart exists.

**Architecture:** New `diet_charts.py` router (6 endpoints, no prefix — routes span `/api/diet-charts/` and `/api/clients/{id}/diet-chart/`). LLM generation in `diet_chart_generate.py` following the `generate_mom_draft` pattern. Three frontend surfaces wired to the new API client module.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL JSONB (backend); Next.js App Router + React + Tailwind v4 + Zod (frontend); OpenRouter via `call_openrouter` + `parse_or_retry`.

---

### Task 1: Backend CRUD + CSV parser

**Files:**
- Create: `backend/src/api/diet_charts.py`
- Create: `backend/tests/unit/test_diet_chart_csv.py`
- Modify: `backend/src/main.py`

- [ ] **Step 1: Write failing unit tests for `_parse_csv_bytes`**

```python
# backend/tests/unit/test_diet_chart_csv.py
import pytest
from src.api.diet_charts import _parse_csv_bytes

SIMPLE_CSV = (
    "Day,Breakfast,Lunch,Dinner\n"
    "Monday,Oats · 7:30 AM,Dal rice · 1:00 PM,Soup · 8:00 PM\n"
    "Tuesday,Eggs · 8:00 AM,Roti sabzi · 1:00 PM,Salad · 7:30 PM\n"
)


def test_parses_meal_slots():
    result = _parse_csv_bytes(SIMPLE_CSV.encode())
    assert result["meal_slots"] == ["Breakfast", "Lunch", "Dinner"]


def test_parses_food_and_timing():
    result = _parse_csv_bytes(SIMPLE_CSV.encode())
    assert result["grid"]["Monday"]["Breakfast"] == {"food": "Oats", "timing": "7:30 AM"}
    assert result["grid"]["Monday"]["Lunch"] == {"food": "Dal rice", "timing": "1:00 PM"}


def test_skips_non_day_rows():
    csv = "Day,Breakfast\nMonday,Oats · 8am\nTotal,ignored\n"
    result = _parse_csv_bytes(csv.encode())
    assert list(result["grid"].keys()) == ["Monday"]


def test_raises_on_wrong_first_column():
    csv = "NotDay,Breakfast\nMonday,Oats · 8am\n"
    with pytest.raises(ValueError, match="First column header must be 'Day'"):
        _parse_csv_bytes(csv.encode())


def test_raises_on_no_slots():
    csv = "Day\nMonday\n"
    with pytest.raises(ValueError, match="at least one meal slot"):
        _parse_csv_bytes(csv.encode())


def test_cell_without_separator_gets_empty_timing():
    csv = "Day,Breakfast\nMonday,Oats\n"
    result = _parse_csv_bytes(csv.encode())
    assert result["grid"]["Monday"]["Breakfast"] == {"food": "Oats", "timing": ""}


def test_utf8_bom_stripped():
    csv_bytes = "\xef\xbb\xbfDay,Breakfast\nMonday,Oats · 8am\n".encode()
    result = _parse_csv_bytes(csv_bytes)
    assert result["meal_slots"] == ["Breakfast"]
```

- [ ] **Step 2: Run to verify failure**

```
cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
pytest tests/unit/test_diet_chart_csv.py -v
```
Expected: `ModuleNotFoundError` — `src.api.diet_charts` does not exist yet.

- [ ] **Step 3: Create `backend/src/api/diet_charts.py`**

```python
"""Diet chart endpoints — template library CRUD + client chart CRUD."""
import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, select

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models.clients import Client
from src.db.models.content import ContentAssignment, DietChart

router = APIRouter(tags=["diet-charts"])

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MAX_CSV_BYTES = 128 * 1024


# ── schemas ────────────────────────────────────────────────────────────────────


class DietChartOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    parameters: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DietChartPatch(BaseModel):
    parameters: dict


class GenerateRequest(BaseModel):
    template_id: UUID
    client_goal: str | None = None


class GenerateResponse(BaseModel):
    chart: DietChartOut
    generation_status: str  # "generated" | "fallback"


# ── helpers ────────────────────────────────────────────────────────────────────


def _parse_csv_bytes(data: bytes) -> dict:
    """Parse diet chart CSV → {meal_slots, grid}.
    Header: Day,<Slot1>,…  Cells: "food · timing".
    """
    text = data.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    fieldnames = list(reader.fieldnames)
    if not fieldnames or fieldnames[0].strip() != "Day":
        raise ValueError("First column header must be 'Day'")
    meal_slots = [f.strip() for f in fieldnames[1:] if f.strip()]
    if not meal_slots:
        raise ValueError("CSV must have at least one meal slot column")
    grid: dict[str, dict[str, dict[str, str]]] = {}
    for row in reader:
        day = (row.get("Day") or "").strip()
        if day not in DAYS:
            continue
        grid[day] = {}
        for slot in meal_slots:
            raw = (row.get(slot) or "").strip()
            if "·" in raw:
                food_part, timing_part = raw.split("·", 1)
                grid[day][slot] = {"food": food_part.strip(), "timing": timing_part.strip()}
            else:
                grid[day][slot] = {"food": raw, "timing": ""}
    return {"meal_slots": meal_slots, "grid": grid}


def _to_out(chart: DietChart) -> DietChartOut:
    return DietChartOut.model_validate(chart)


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


async def _get_active_chart(db: DbDep, client_id: UUID, hc_id: str) -> DietChart | None:
    return (await db.execute(
        select(DietChart)
        .join(ContentAssignment, and_(
            ContentAssignment.content_type == "diet_chart",
            ContentAssignment.content_id == DietChart.id,
        ))
        .where(
            ContentAssignment.client_id == client_id,
            ContentAssignment.hc_user_id == UUID(hc_id),
            DietChart.archived_at.is_(None),
        )
        .order_by(ContentAssignment.assigned_at.desc())
        .limit(1)
    )).scalar_one_or_none()


# ── template routes ────────────────────────────────────────────────────────────


@router.post("/api/diet-charts/templates/upload", status_code=status.HTTP_201_CREATED)
async def upload_template(
    file: UploadFile,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> DietChartOut:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="File must be a .csv")
    data = await file.read(MAX_CSV_BYTES + 1)
    if len(data) > MAX_CSV_BYTES:
        raise HTTPException(status_code=422, detail="CSV exceeds 128 KB limit")
    try:
        parsed = _parse_csv_bytes(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    name = file.filename[:-4]
    template_key = name.lower().replace(" ", "-")
    chart = DietChart(
        hc_user_id=UUID(hc_id),
        name=name,
        description=None,
        parameters={"is_template": True, "template_key": template_key, **parsed},
    )
    db.add(chart)
    await db.flush()
    await db.commit()
    return _to_out(chart)


@router.get("/api/diet-charts/templates")
async def list_templates(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> list[DietChartOut]:
    rows = (await db.execute(
        select(DietChart)
        .where(
            DietChart.hc_user_id == UUID(hc_id),
            DietChart.parameters["is_template"].as_boolean().is_(True),
            DietChart.archived_at.is_(None),
        )
        .order_by(DietChart.created_at.asc())
    )).scalars().all()
    return [_to_out(r) for r in rows]


@router.delete("/api/diet-charts/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_template(
    template_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> None:
    chart = (await db.execute(
        select(DietChart).where(
            DietChart.id == template_id,
            DietChart.hc_user_id == UUID(hc_id),
            DietChart.parameters["is_template"].as_boolean().is_(True),
        )
    )).scalar_one_or_none()
    if chart is None:
        raise HTTPException(status_code=404, detail="Template not found")
    chart.archived_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()


# ── client chart routes ────────────────────────────────────────────────────────


@router.get("/api/clients/{client_id}/diet-chart")
async def get_client_diet_chart(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> DietChartOut:
    await _get_owned_client(db, client_id, hc_id)
    chart = await _get_active_chart(db, client_id, hc_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="No active diet chart for this client")
    return _to_out(chart)


@router.post("/api/clients/{client_id}/diet-chart/generate")
async def generate_client_diet_chart(
    client_id: UUID,
    body: GenerateRequest,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> GenerateResponse:
    await _get_owned_client(db, client_id, hc_id)
    template = (await db.execute(
        select(DietChart).where(
            DietChart.id == body.template_id,
            DietChart.hc_user_id == UUID(hc_id),
            DietChart.parameters["is_template"].as_boolean().is_(True),
            DietChart.archived_at.is_(None),
        )
    )).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    existing = await _get_active_chart(db, client_id, hc_id)
    if existing is not None:
        existing.archived_at = datetime.now(timezone.utc)
        await db.flush()
    from src.llm_service.diet_chart_generate import generate_diet_chart  # noqa: PLC0415
    chart_params, generation_status = await generate_diet_chart(
        db=db,
        hc_user_id=UUID(hc_id),
        client_id=client_id,
        template_params=template.parameters or {},
        client_goal=body.client_goal,
    )
    chart = DietChart(
        hc_user_id=UUID(hc_id),
        name=f"{template.name} — {datetime.now(timezone.utc).strftime('%d %b %Y')}",
        description=None,
        parameters=chart_params,
    )
    db.add(chart)
    await db.flush()
    assignment = ContentAssignment(
        hc_user_id=UUID(hc_id),
        client_id=client_id,
        session_id=None,
        content_type="diet_chart",
        content_id=chart.id,
    )
    db.add(assignment)
    await db.flush()
    await db.commit()
    return GenerateResponse(chart=_to_out(chart), generation_status=generation_status)


@router.patch("/api/clients/{client_id}/diet-chart")
async def patch_client_diet_chart(
    client_id: UUID,
    body: DietChartPatch,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> DietChartOut:
    await _get_owned_client(db, client_id, hc_id)
    chart = await _get_active_chart(db, client_id, hc_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="No active diet chart for this client")
    chart.parameters = body.parameters
    chart.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    return _to_out(chart)
```

- [ ] **Step 4: Register router in `backend/src/main.py`**

Add after line 15 (the last router import):
```python
from src.api.diet_charts import router as diet_charts_router
```
Add after line 56 (`app.include_router(check_ins_router)`):
```python
app.include_router(diet_charts_router)
```

- [ ] **Step 5: Run unit tests**

```
pytest tests/unit/test_diet_chart_csv.py -v
```
Expected: 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/diet_charts.py \
        backend/tests/unit/test_diet_chart_csv.py \
        backend/src/main.py
git commit -m "feat(diet-charts): backend CRUD endpoints + CSV parser"
```

---

### Task 2: LLM generation + MOM integration

**Files:**
- Create: `backend/prompts/diet_chart_generate_v1.md`
- Create: `backend/src/llm_service/schemas/diet_chart.py`
- Create: `backend/src/llm_service/diet_chart_generate.py`
- Create: `backend/tests/unit/test_diet_chart_generate.py`
- Modify: `backend/src/llm_service/__init__.py`

- [ ] **Step 1: Write failing unit tests**

```python
# backend/tests/unit/test_diet_chart_generate.py
import pytest
from src.llm_service.schemas.diet_chart import DietChartGridSchema

VALID_JSON = (
    '{"meal_slots": ["Breakfast", "Lunch"],'
    ' "grid": {"Monday": {"Breakfast": {"food": "Oats", "timing": "7:30 AM"},'
    ' "Lunch": {"food": "Dal rice", "timing": "1:00 PM"}}}}'
)

TEMPLATE_PARAMS = {
    "is_template": True,
    "template_key": "high-protein",
    "meal_slots": ["Breakfast"],
    "grid": {"Monday": {"Breakfast": {"food": "Eggs", "timing": "8:00 AM"}}},
}


def test_schema_parses_valid_json():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    assert schema.meal_slots == ["Breakfast", "Lunch"]
    assert schema.grid["Monday"]["Breakfast"].food == "Oats"


def test_to_parameters_sets_is_template_false():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    assert schema.to_parameters(TEMPLATE_PARAMS)["is_template"] is False


def test_to_parameters_preserves_template_key():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    assert schema.to_parameters(TEMPLATE_PARAMS)["template_key"] == "high-protein"


def test_to_parameters_serialises_cells_as_dicts():
    schema = DietChartGridSchema.model_validate_json(VALID_JSON)
    params = schema.to_parameters(TEMPLATE_PARAMS)
    assert params["grid"]["Monday"]["Breakfast"] == {"food": "Oats", "timing": "7:30 AM"}


def test_template_grid_section_includes_day_and_food():
    from src.llm_service.diet_chart_generate import _template_grid_section
    section = _template_grid_section(TEMPLATE_PARAMS)
    assert "Monday" in section
    assert "Eggs · 8:00 AM" in section


def test_template_grid_section_omits_dot_when_timing_empty():
    from src.llm_service.diet_chart_generate import _template_grid_section
    params = {
        "meal_slots": ["Breakfast"],
        "grid": {"Monday": {"Breakfast": {"food": "Oats", "timing": ""}}},
    }
    section = _template_grid_section(params)
    assert "Oats" in section
    assert "·" not in section
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/unit/test_diet_chart_generate.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `backend/prompts/diet_chart_generate_v1.md`**

```markdown
---
version: "diet_chart_generate_v1"
created: "2026-05-12"
notes: >
  First version. Personalises a 7-day template grid to the client's goal.
  Returns strict JSON matching DietChartGridSchema.
---
You are a clinical nutrition assistant helping a health coach personalise a 7-day diet chart for a client.

The coach has selected the following template diet chart:

{{TEMPLATE_GRID}}

Client's health goal: {{CLIENT_GOAL}}

Return a personalised version of the grid adjusted for this goal.

Return ONLY valid JSON — no markdown fences, no explanation:
{
  "meal_slots": ["<slot1>", ...],
  "grid": {
    "Monday":    {"<slot>": {"food": "<description>", "timing": "<HH:MM AM/PM>"}, ...},
    "Tuesday":   { ... },
    "Wednesday": { ... },
    "Thursday":  { ... },
    "Friday":    { ... },
    "Saturday":  { ... },
    "Sunday":    { ... }
  }
}

Rules:
- Preserve all slot names and day names exactly as given
- Include all 7 days
- Food descriptions under 60 characters per cell
- Keep timings from the template unless nutritionally important to change

{{FORMAT_HINT}}
```

- [ ] **Step 4: Create `backend/src/llm_service/schemas/diet_chart.py`**

```python
from pydantic import BaseModel


class MealCellSchema(BaseModel):
    food: str
    timing: str


class DietChartGridSchema(BaseModel):
    meal_slots: list[str]
    grid: dict[str, dict[str, MealCellSchema]]

    def to_parameters(self, template_params: dict) -> dict:
        return {
            "is_template": False,
            "template_key": template_params.get("template_key", ""),
            "meal_slots": self.meal_slots,
            "grid": {
                day: {
                    slot: {"food": cell.food, "timing": cell.timing}
                    for slot, cell in slots.items()
                }
                for day, slots in self.grid.items()
            },
        }
```

- [ ] **Step 5: Create `backend/src/llm_service/diet_chart_generate.py`**

```python
"""LLM-based diet chart personalisation. Per ADR-0003."""
from __future__ import annotations

import logging
from uuid import UUID

import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm_service.chain import build_models_array, fallback_count_for
from src.llm_service.client import call_openrouter
from src.llm_service.config import get_llm_config
from src.llm_service.prompts import load_prompt
from src.llm_service.retry import STRICT_FORMAT_HINT, parse_or_retry
from src.llm_service.schemas.diet_chart import DietChartGridSchema
from src.llm_service.tracking import write_llm_call

logger = logging.getLogger(__name__)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _template_grid_section(template_params: dict) -> str:
    lines = ["Template grid:"]
    slots: list[str] = template_params.get("meal_slots", [])
    grid: dict = template_params.get("grid", {})
    for day in _DAYS:
        if day not in grid:
            continue
        lines.append(f"  {day}:")
        for slot in slots:
            cell = grid[day].get(slot, {})
            food = cell.get("food", "")
            timing = cell.get("timing", "")
            if timing:
                lines.append(f"    {slot}: {food} · {timing}")
            else:
                lines.append(f"    {slot}: {food}")
    return "\n".join(lines)


async def generate_diet_chart(
    db: AsyncSession,
    *,
    hc_user_id: UUID,
    client_id: UUID,
    template_params: dict,
    client_goal: str | None,
    request_id: UUID | None = None,
) -> tuple[dict, str]:
    """
    Personalise a diet chart from a template via LLM.
    Returns (parameters_dict, generation_status) where generation_status is
    "generated" or "fallback".
    """
    cfg = get_llm_config()
    prompt_file = load_prompt("diet_chart_generate_v1")
    models = build_models_array(cfg)

    template_section = _template_grid_section(template_params)
    goal_text = client_goal or "general health and balanced nutrition"

    system_prompt = (
        prompt_file.body
        .replace("{{TEMPLATE_GRID}}", template_section)
        .replace("{{CLIENT_GOAL}}", goal_text)
        .replace("{{FORMAT_HINT}}", "")
    )
    user_message = "Personalise the template diet chart for this client."

    try:
        result = await call_openrouter(
            models=models,
            system_prompt=system_prompt,
            user_message=user_message,
            no_training=cfg.no_training_header,
            no_retention=cfg.no_retention_header,
        )
    except Exception as exc:
        await write_llm_call(
            db,
            hc_user_id=hc_user_id,
            client_id=client_id,
            session_id=None,
            use_case="diet_chart_generation",
            prompt_version=prompt_file.version,
            model_requested=models[0],
            model_served=None,
            fallback_count=0,
            input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            validation_failed=False,
            snippet_count=0,
            snippet_tokens=0,
            inr_cost_estimate=None,
            raw_request_id=None,
            error_message=str(exc),
            prompt_text=system_prompt,
            completion_text="",
            request_id=request_id,
        )
        logger.warning(
            "diet_chart_generation.llm_error.fallback",
            extra={"hc_user_id": str(hc_user_id), "client_id": str(client_id), "error": str(exc)},
        )
        sentry_sdk.capture_message(
            f"diet_chart_generation: LLM call failed — {exc}",
            level="warning",
        )
        return {**template_params, "is_template": False}, "fallback"

    async def retry_fn() -> str:
        retry_result = await call_openrouter(
            models=models,
            system_prompt=system_prompt + STRICT_FORMAT_HINT,
            user_message=user_message,
            no_training=cfg.no_training_header,
            no_retention=cfg.no_retention_header,
        )
        return retry_result.content

    parsed, validation_failed, error_msg = await parse_or_retry(
        result.content, DietChartGridSchema, retry_fn
    )

    fc = fallback_count_for(result.model_served, cfg)
    await write_llm_call(
        db,
        hc_user_id=hc_user_id,
        client_id=client_id,
        session_id=None,
        use_case="diet_chart_generation",
        prompt_version=prompt_file.version,
        model_requested=models[0],
        model_served=result.model_served,
        fallback_count=fc,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        validation_failed=validation_failed,
        snippet_count=0,
        snippet_tokens=0,
        inr_cost_estimate=None,
        raw_request_id=result.raw_request_id,
        error_message=error_msg,
        prompt_text=system_prompt,
        completion_text=result.content,
        request_id=request_id,
    )

    if parsed is None:
        logger.warning(
            "diet_chart_generation.parse_failed.fallback",
            extra={
                "hc_user_id": str(hc_user_id),
                "client_id": str(client_id),
                "raw_snippet": result.content[:200],
            },
        )
        sentry_sdk.capture_message(
            "diet_chart_generation: JSON parse failed, returning template fallback",
            level="warning",
        )
        return {**template_params, "is_template": False}, "fallback"

    return parsed.to_parameters(template_params), "generated"
```

- [ ] **Step 6: Add MOM diet chart note to `backend/src/llm_service/__init__.py`**

In the imports section, extend line 8 (`from sqlalchemy import select`) to:
```python
from sqlalchemy import and_, select
```
After line 14 (`from src.db.models.coaching import ActionItem, CheckIn, Mom`), add:
```python
from src.db.models.content import ContentAssignment, DietChart
```
After line 127 (the `user_message = notes_section + ...` assignment), insert:
```python
    _active_chart = (await db.execute(
        select(DietChart)
        .join(ContentAssignment, and_(
            ContentAssignment.content_type == "diet_chart",
            ContentAssignment.content_id == DietChart.id,
        ))
        .where(
            ContentAssignment.client_id == client_id,
            ContentAssignment.hc_user_id == hc_user_id,
            DietChart.archived_at.is_(None),
        )
        .limit(1)
    )).scalar_one_or_none()
    if _active_chart is not None:
        user_message += "\n\nNote: A diet chart has been prepared for this client."
```

- [ ] **Step 7: Run unit tests**

```
pytest tests/unit/test_diet_chart_generate.py -v
```
Expected: 6 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/prompts/diet_chart_generate_v1.md \
        backend/src/llm_service/schemas/diet_chart.py \
        backend/src/llm_service/diet_chart_generate.py \
        backend/tests/unit/test_diet_chart_generate.py \
        backend/src/llm_service/__init__.py
git commit -m "feat(diet-charts): LLM generation + MOM integration"
```

---

### Task 3: Frontend — 3 surfaces

**Files:**
- Create: `frontend/src/lib/api/dietCharts.ts`
- Create: `frontend/src/app/(app)/settings/diet-chart-templates/page.tsx`
- Create: `frontend/src/app/(app)/clients/[clientId]/diet-chart/page.tsx`
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx`

- [ ] **Step 1: Create `frontend/src/lib/api/dietCharts.ts`**

```typescript
import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

export const DietChartOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  parameters: z.record(z.unknown()).nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const GenerateResponseSchema = z.object({
  chart: DietChartOutSchema,
  generation_status: z.string(),
});

export type DietChartOut = z.infer<typeof DietChartOutSchema>;

export async function uploadTemplate(file: File): Promise<DietChartOut> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetchWithAuth(`${API_URL}/api/diet-charts/templates/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return DietChartOutSchema.parse(await res.json());
}

export async function listTemplates(): Promise<DietChartOut[]> {
  const res = await fetchWithAuth(`${API_URL}/api/diet-charts/templates`);
  if (!res.ok) throw new Error(`List templates failed: ${res.status}`);
  return z.array(DietChartOutSchema).parse(await res.json());
}

export async function deleteTemplate(templateId: string): Promise<void> {
  const res = await fetchWithAuth(
    `${API_URL}/api/diet-charts/templates/${templateId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Delete template failed: ${res.status}`);
}

export async function getClientDietChart(clientId: string): Promise<DietChartOut | null> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/diet-chart`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Get diet chart failed: ${res.status}`);
  return DietChartOutSchema.parse(await res.json());
}

export async function generateDietChart(
  clientId: string,
  input: { template_id: string; client_goal?: string },
): Promise<{ chart: DietChartOut; generation_status: string }> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/diet-chart/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
  if (!res.ok) throw new Error(`Generate diet chart failed: ${res.status}`);
  return GenerateResponseSchema.parse(await res.json());
}

export async function patchDietChart(
  clientId: string,
  parameters: Record<string, unknown>,
): Promise<DietChartOut> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/diet-chart`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters }),
    },
  );
  if (!res.ok) throw new Error(`Patch diet chart failed: ${res.status}`);
  return DietChartOutSchema.parse(await res.json());
}
```

- [ ] **Step 2: Create `frontend/src/app/(app)/settings/diet-chart-templates/page.tsx`**

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  listTemplates,
  uploadTemplate,
  deleteTemplate,
  type DietChartOut,
} from "@/lib/api/dietCharts";

export default function DietChartTemplatesPage() {
  const [templates, setTemplates] = useState<DietChartOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setLoadError(true));
  }, []);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const created = await uploadTemplate(file);
      setTemplates((prev) => (prev ? [...prev, created] : [created]));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteTemplate(id);
      setTemplates((prev) => (prev ? prev.filter((t) => t.id !== id) : prev));
    } catch {
      // leave list as-is; optimistic delete not safe here
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Settings
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Diet chart templates
        </h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          Upload CSV templates. Each template is a 7-day grid the AI uses as a starting point when generating a client chart.
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-foreground">
          Upload a template
        </h2>
        <Separator />
        <p className="font-sans text-xs text-muted-foreground">
          CSV format: header row <code className="font-mono">Day,Breakfast,Lunch,…</code>, rows 2–8 are Monday–Sunday, cells are{" "}
          <code className="font-mono">food · timing</code>.
        </p>
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            disabled={uploading}
            className="font-sans text-sm text-foreground file:mr-3 file:cursor-pointer file:rounded file:border-0 file:bg-primary file:px-3 file:py-1.5 file:font-sans file:text-xs file:font-bold file:uppercase file:tracking-widest file:text-primary-foreground disabled:opacity-50"
          />
          {uploading && (
            <span className="font-sans text-xs text-muted-foreground">Uploading…</span>
          )}
        </div>
        {uploadError && (
          <p className="font-sans text-xs text-destructive">{uploadError}</p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-foreground">
          Library
        </h2>
        <Separator />
        {loadError ? (
          <p className="font-sans text-sm text-destructive">Could not load templates.</p>
        ) : templates === null ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : templates.length === 0 ? (
          <p className="py-2 font-heading text-xl font-black text-muted-foreground">
            No templates yet. <em>Upload one above.</em>
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-2xl border border-border">
            {templates.map((t) => (
              <li key={t.id} className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="font-heading text-base font-bold text-foreground">{t.name}</p>
                  <p className="font-sans text-xs text-muted-foreground">
                    {Array.isArray(
                      (t.parameters as Record<string, unknown>)?.meal_slots,
                    )
                      ? (
                          (t.parameters as Record<string, unknown>)
                            .meal_slots as string[]
                        ).join(" · ")
                      : ""}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(t.id)}
                  className="font-sans text-xs text-destructive underline-offset-4 hover:underline"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/app/(app)/clients/[clientId]/diet-chart/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  getClientDietChart,
  generateDietChart,
  patchDietChart,
  listTemplates,
  type DietChartOut,
} from "@/lib/api/dietCharts";
import { getClient, type ClientDetailOut } from "@/lib/api/clients";

type GridCell = { food: string; timing: string };
type Grid = Record<string, Record<string, GridCell>>;

const DAYS = [
  "Monday", "Tuesday", "Wednesday", "Thursday",
  "Friday", "Saturday", "Sunday",
];

function getGrid(chart: DietChartOut): Grid {
  return ((chart.parameters as Record<string, unknown>)?.grid as Grid) ?? {};
}

function getMealSlots(chart: DietChartOut): string[] {
  return (
    (chart.parameters as Record<string, unknown>)?.meal_slots as string[]
  ) ?? [];
}

export default function DietChartEditorPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [client, setClient] = useState<ClientDetailOut | null>(null);
  const [chart, setChart] = useState<DietChartOut | null | undefined>(undefined);
  const [templates, setTemplates] = useState<DietChartOut[]>([]);
  const [editedGrid, setEditedGrid] = useState<Grid>({});
  const [mealSlots, setMealSlots] = useState<string[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [clientGoal, setClientGoal] = useState("");
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fallbackWarning, setFallbackWarning] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [newSlotName, setNewSlotName] = useState("");

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      getClient(clientId),
      getClientDietChart(clientId),
      listTemplates(),
    ])
      .then(([c, dc, tpls]) => {
        setClient(c);
        setChart(dc);
        setTemplates(tpls);
        if (tpls.length > 0) setSelectedTemplateId(tpls[0].id);
        if (dc) {
          setEditedGrid(getGrid(dc));
          setMealSlots(getMealSlots(dc));
        }
      })
      .catch(() => setLoadError(true));
  }, [clientId]);

  async function handleGenerate() {
    if (!selectedTemplateId) return;
    setGenerating(true);
    setFallbackWarning(false);
    try {
      const { chart: newChart, generation_status } = await generateDietChart(
        clientId,
        { template_id: selectedTemplateId, client_goal: clientGoal || undefined },
      );
      setChart(newChart);
      setEditedGrid(getGrid(newChart));
      setMealSlots(getMealSlots(newChart));
      if (generation_status === "fallback") setFallbackWarning(true);
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    if (!chart) return;
    setSaving(true);
    setSaveError(null);
    try {
      const params = {
        ...(chart.parameters as Record<string, unknown>),
        meal_slots: mealSlots,
        grid: editedGrid,
      };
      const updated = await patchDietChart(clientId, params);
      setChart(updated);
      setEditedGrid(getGrid(updated));
      setMealSlots(getMealSlots(updated));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function updateCell(
    day: string,
    slot: string,
    field: "food" | "timing",
    value: string,
  ) {
    setEditedGrid((prev) => ({
      ...prev,
      [day]: {
        ...(prev[day] ?? {}),
        [slot]: {
          ...(prev[day]?.[slot] ?? { food: "", timing: "" }),
          [field]: value,
        },
      },
    }));
  }

  function addMealSlot() {
    const name = newSlotName.trim();
    if (!name || mealSlots.includes(name)) return;
    setMealSlots((prev) => [...prev, name]);
    setEditedGrid((prev) => {
      const next = { ...prev };
      for (const day of DAYS) {
        next[day] = { ...(next[day] ?? {}), [name]: { food: "", timing: "" } };
      }
      return next;
    });
    setNewSlotName("");
  }

  const loading = chart === undefined && !loadError;

  return (
    <div className="space-y-8">
      <Link
        href={`/clients/${clientId}`}
        className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        ← {client?.full_name ?? "Client"}
      </Link>

      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Nutrition
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Diet chart
        </h1>
      </div>

      {loadError && (
        <p className="font-sans text-sm text-destructive">
          Could not load diet chart.
        </p>
      )}

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {!loading && !loadError && (
        <>
          <section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
            <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
              {chart ? "Regenerate chart" : "Generate chart"}
            </h2>
            <Separator />
            {templates.length === 0 ? (
              <p className="font-sans text-sm text-muted-foreground">
                No templates in library.{" "}
                <Link
                  href="/settings/diet-chart-templates"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  Upload one →
                </Link>
              </p>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      Template
                    </label>
                    <select
                      value={selectedTemplateId}
                      onChange={(e) => setSelectedTemplateId(e.target.value)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 font-sans text-sm text-foreground"
                    >
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      Client goal (optional)
                    </label>
                    <input
                      type="text"
                      value={clientGoal}
                      onChange={(e) => setClientGoal(e.target.value)}
                      placeholder="e.g. weight loss, high protein…"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground"
                    />
                  </div>
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={generating || !selectedTemplateId}
                  className="rounded-lg bg-primary px-4 py-2 font-sans text-xs font-bold uppercase tracking-widest text-primary-foreground disabled:opacity-50"
                >
                  {generating ? "Generating…" : chart ? "Regenerate" : "Generate"}
                </button>
              </div>
            )}
          </section>

          {fallbackWarning && (
            <div className="rounded-lg border border-amber-400 bg-amber-50 px-4 py-3">
              <p className="font-sans text-sm text-amber-800">
                AI generation failed — showing the template grid unchanged. Edit cells below and save.
              </p>
            </div>
          )}

          {chart && (
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                  7-day grid
                </h2>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-lg bg-primary px-4 py-2 font-sans text-xs font-bold uppercase tracking-widest text-primary-foreground disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save chart"}
                </button>
              </div>
              {saveError && (
                <p className="font-sans text-xs text-destructive">{saveError}</p>
              )}
              <div className="overflow-x-auto rounded-2xl border border-border">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted">
                      <th className="w-24 p-3 text-left font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                        Day
                      </th>
                      {mealSlots.map((slot) => (
                        <th
                          key={slot}
                          className="min-w-[160px] border-l border-border p-3 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground"
                        >
                          {slot}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {DAYS.map((day) => (
                      <tr
                        key={day}
                        className="border-b border-border align-top last:border-0"
                      >
                        <td className="p-3">
                          <span className="font-heading text-sm font-bold text-foreground">
                            {day.slice(0, 3)}
                          </span>
                        </td>
                        {mealSlots.map((slot) => {
                          const cell = editedGrid[day]?.[slot] ?? {
                            food: "",
                            timing: "",
                          };
                          return (
                            <td key={slot} className="border-l border-border p-2">
                              <div className="space-y-1">
                                <input
                                  type="text"
                                  value={cell.food}
                                  onChange={(e) =>
                                    updateCell(day, slot, "food", e.target.value)
                                  }
                                  placeholder="Food"
                                  className="w-full rounded border border-border bg-background px-2 py-1 font-sans text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                                <input
                                  type="text"
                                  value={cell.timing}
                                  onChange={(e) =>
                                    updateCell(day, slot, "timing", e.target.value)
                                  }
                                  placeholder="Timing"
                                  className="w-full rounded border border-border bg-background px-2 py-1 font-sans text-xs text-muted-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={newSlotName}
                  onChange={(e) => setNewSlotName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addMealSlot()}
                  placeholder="New meal slot name…"
                  className="w-56 rounded-lg border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground"
                />
                <button
                  onClick={addMealSlot}
                  disabled={!newSlotName.trim()}
                  className="font-sans text-xs text-primary underline-offset-4 hover:underline disabled:opacity-40"
                >
                  + Add column
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Add diet chart section to `frontend/src/app/(app)/clients/[clientId]/page.tsx`**

Add to imports (after `listActionItems` import on line 14):
```typescript
import { getClientDietChart, type DietChartOut } from "@/lib/api/dietCharts";
```

Add to state (after `showClosed` on line 44):
```typescript
const [dietChart, setDietChart] = useState<DietChartOut | null | undefined>(undefined);
```

Extend the `Promise.all` in `useEffect` to include `getClientDietChart(clientId)` as a fifth call, and destructure the fifth result as `dc`, then call `setDietChart(dc)`. The updated `useEffect` body becomes:
```typescript
Promise.all([
  getClient(clientId),
  getClientAst(clientId),
  listSessions({ client_id: clientId, limit: 20 }),
  listActionItems({ client_id: clientId, status: "completed", limit: 50 }),
  getClientDietChart(clientId),
])
  .then(([c, a, s, closed, dc]) => {
    setClient(c);
    setAst(a);
    setSessions(s.items);
    setClosedItems(closed.items);
    setDietChart(dc);
  })
  .catch(() => setLoadError(true));
```

Add the following section after the closing `</section>` tag of the Session History section (after line 329):
```tsx
{/* Diet chart */}
<section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
  <div className="flex items-center justify-between">
    <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
      Diet chart
    </h2>
    <Link
      href={`/clients/${clientId}/diet-chart`}
      className="font-sans text-xs text-primary underline-offset-4 hover:underline"
    >
      {dietChart ? "Edit chart →" : "Generate →"}
    </Link>
  </div>
  <Separator />
  {dietChart === undefined ? (
    <Skeleton className="h-24 w-full" />
  ) : dietChart === null ? (
    <p className="py-2 font-sans text-sm italic text-muted-foreground">
      No diet chart yet.
    </p>
  ) : (
    (() => {
      const params = dietChart.parameters as Record<string, unknown>;
      const grid = (params?.grid ?? {}) as Record<
        string,
        Record<string, { food: string; timing: string }>
      >;
      const slots = (params?.meal_slots ?? []) as string[];
      return (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="py-1.5 pr-3 text-left font-sans font-bold text-muted-foreground">
                  Day
                </th>
                {slots.slice(0, 3).map((s) => (
                  <th
                    key={s}
                    className="border-l border-border px-3 py-1.5 text-left font-sans font-bold text-muted-foreground"
                  >
                    {s}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {["Monday", "Tuesday"].map((day) => (
                <tr key={day} className="border-b border-border last:border-0">
                  <td className="py-1.5 pr-3 font-heading font-bold text-foreground">
                    {day.slice(0, 3)}
                  </td>
                  {slots.slice(0, 3).map((s) => (
                    <td
                      key={s}
                      className="border-l border-border px-3 py-1.5 font-sans text-foreground"
                    >
                      {grid[day]?.[s]?.food ?? "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    })()
  )}
</section>
```

- [ ] **Step 5: Start dev server and smoke-test the 3 surfaces**

```
cd frontend && npm run dev
```

Check in browser:
- `/settings/diet-chart-templates` — renders heading + "No templates yet."
- `/clients/<any-id>` — Diet chart section visible in left column, shows skeleton then "No diet chart yet."
- `/clients/<any-id>/diet-chart` — renders generate form with "No templates in library. Upload one →"

No console errors in any of these states.

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/lib/api/dietCharts.ts" \
        "frontend/src/app/(app)/settings/diet-chart-templates/page.tsx" \
        "frontend/src/app/(app)/clients/[clientId]/diet-chart/page.tsx" \
        "frontend/src/app/(app)/clients/[clientId]/page.tsx"
git commit -m "feat(diet-charts): frontend — template library, chart editor, client detail preview"
```

---

*P6C implementation plan authored 2026-05-12.*
