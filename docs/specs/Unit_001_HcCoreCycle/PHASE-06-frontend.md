# PHASE-06: Frontend (HC Console) + Brand Identity Adoption

**Unit**: Unit_001_HcCoreCycle
**Status**: Draft
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
