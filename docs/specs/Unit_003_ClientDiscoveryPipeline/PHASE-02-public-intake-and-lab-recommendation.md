# PHASE-02: Public intake questionnaire and lab recommendation

**Unit**: Unit_003_ClientDiscoveryPipeline
**Status**: Draft
**Verification date**: Not yet verified — fill in after implementation and verification
**Implements**: SPEC-0001 §Stage 2 (Lead completes questionnaire), §Stage 3 (Lab test recommendation generated and emailed); Acceptance criteria §Lead questionnaire submission, §Lab recommendation and token; §DPDP (consent-capture items only — logging/robots items belong to whichever phase ships the full pipeline)
**ADRs implemented**: ADR-0005 (auth strategy) — this phase's `lead_upload_tokens` issuance mirrors the `client_invite_tokens` pattern it defines. No LLM or observability ADRs apply — this phase makes no LLM calls.

---

## 0. Per-requisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific I haven't provided. Ready?

## 1. Scope

This phase builds the public-facing half of the Lead intake funnel described in SPEC-0001: a prospective client opens the HC's intake link, fills out the HC's configured questionnaire, and — with no HC involvement — immediately receives an email with recommended blood tests and a link to upload their report later. Concretely: two public (unauthenticated) endpoints, one new outbound email, and the public intake page itself.

**Not in scope**: blood report upload, PDF text extraction, R2 storage, and LLM-generated pre-consultation brief (SPEC-0001 Stage 4) are deliberately deferred to a later phase — they introduce enough new subsystems (file storage, an LLM task type, PDF parsing) to warrant their own phase, mirroring how Unit_001 isolated its LLM-service work rather than bundling it with adjacent endpoints. HC review UI, conversion, rejection, and purge (Stages 5-6) are also out of scope. PHASE-01 (HC one-time setup, `hc_leadgen_config`) is a completed prerequisite this phase reads from but does not modify.

## 2. Deliverables shipped

Planned — to be updated with actuals as this phase is implemented and ships.

- `backend/src/lib/rate_limit.py` (new) — `slowapi` `Limiter` instance, conservative IP key (direct connection only, see Decision D-1)
- `backend/pyproject.toml` — add `slowapi` dependency
- `backend/src/main.py` — register the limiter and `RateLimitExceeded` exception handler
- `backend/src/lib/email.py` — add `send_lead_test_recommendation_email(...)`
- `backend/src/api/intake.py` (new) — `GET /api/intake/:slug` (public; returns `{hc_name, hc_photo_url, questionnaire}` only), `POST /api/intake/:slug` (public, rate-limited 5/hour/IP; creates the Lead + questionnaire responses + consent record, then synchronously runs Stage 3: builds the test recommendation, issues the upload token, sends the recommendation email)
- `backend/src/main.py` — register `intake_router`
- `backend/tests/integration/test_intake_public.py` (new)
- `backend/tests/unit/test_lead_test_recommendation.py` (new) — pure-function tests for the recommendation-matching logic
- `frontend/src/lib/api/intake.ts` (new) — unauthenticated API module, Zod schemas
- `frontend/src/app/(public)/intake/layout.tsx` (new) — Server Component, sets `noindex` metadata
- `frontend/src/app/(public)/intake/[slug]/page.tsx` (new) — the public questionnaire page

## 3. Decisions made during this phase

**D-1 — Rate-limit key defaults to the direct connection IP, not `X-Forwarded-For`.** All browser traffic reaches the backend through a same-origin BFF proxy (`frontend/src/app/api/[...path]/route.ts`), which forwards whatever `X-Forwarded-For` value it receives without setting one itself. Whether Cloud Run's real edge prepends or appends the true client IP to that header — and therefore which end of the list is trustworthy — could not be verified from this repo alone, and an attacker can also reach the backend's own public URL directly, bypassing the proxy and setting that header to anything. Trusting the wrong end would make the rate limit a false sense of security rather than a real one. Default: trust only the direct TCP connection IP (`slowapi`'s `get_remote_address`). Effect: direct backend hits are limited correctly; browser-originated traffic via the BFF proxy shares one coarser bucket per deployment (all Leads using the frontend look like one IP to the limiter) until this is revisited with the real trusted-hop configuration. Decided with SoJo, 2026-08-03.

**D-2 — Stage 3 email delivery failure does not fail the Lead's request.** If `send_lead_test_recommendation_email` raises (e.g. a transient Resend outage), the failure is caught and logged, not re-raised — the Lead's questionnaire submission is already legitimately committed to the database by that point in the flow, and failing the whole HTTP request over an email-delivery problem would lose real, correctly-captured data over a recoverable issue. No resend/reminder capability exists until a later phase (`POST /api/leads/:id/remind`, per SPEC-0001's API surface). Decided with SoJo, 2026-08-03.

**D-3 — Missing HC profile photo renders blank, not a generated placeholder.** `users.photo_url` can be null (e.g. an HC created via the dev seed script, or one who signed up without a Google avatar). The public intake page simply omits the image element in that case, rather than generating an initials-based placeholder avatar — simplest, and consistent with how the rest of the app already handles missing user data; no initials-avatar UI exists anywhere else in the app to reuse. Decided with SoJo, 2026-08-03.

**D-4 — SPEC-0001's "ILIKE" language for condition-rule keyword matching (Stage 3 step 3) is implemented as Python substring matching, not a literal SQL query.** The matching runs against questionnaire response data the request already holds in memory from Stage 2 — there is no reason to round-trip to Postgres for data the process already has. Read as describing case-insensitive substring matching *semantics*, not mandating a literal `ILIKE` query.

**D-5 (forward-looking — does not apply to this phase's own build, recorded for whichever phase implements Stage 4) — blood-report upload MIME validation will use a minimal hand-written 3-signature magic-byte check (PDF/JPEG/PNG), not a new dependency.** The existing repo convention (`backend/src/api/files.py`) trusts the declared `Content-Type` header alone, which is defensible there because the uploader is already an authenticated identity with an accountable account — that compensating control does not exist for Stage 4's upload endpoint, which is unauthenticated (a bearer-style link mailed to a Lead with no account). Decided with SoJo, 2026-08-03.

**D-6 (forward-looking, explicitly out of scope) — OTP email verification on the Stage 4 upload link was considered and deferred, not adopted.** It would address a different risk (proving who is using the link) than MIME validation (verifying what was uploaded), is substantially more implementation work (new schema, endpoints, email flow, its own rate-limiting, new frontend UX), and is not in SPEC-0001 today. Flagged as a possible future SPEC-0001 amendment requiring its own brainstorming/design pass — not committed to any current phase. Decided with SoJo, 2026-08-03.

## 4. Bugs fixed mid-phase

None yet — phase not yet executed. PHASE-01's real experience (6 bugs caught across per-task and final-branch review; see PHASE-01 and the SESSION_LOG 2026-08-02 entry) is the expectation to calibrate against: this section should be filled in honestly as implementation surfaces real issues, not left as "no issues" without verification.

## 5. Source docs consulted

- `docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` — §Stage 2, §Stage 3, §Data (`leads`, `lead_questionnaire_responses`, `lead_upload_tokens`), §API surface (Public), §Acceptance criteria (Lead questionnaire submission, Lab recommendation and token, DPDP), §Edge cases and failure modes (duplicate email, HC not configured)
- `docs/specs/Unit_003_ClientDiscoveryPipeline/PHASE-01-leadgen-data-layer-and-setup.md` — confirms the current shipped schema/model state this phase builds on (`Lead`, `LeadQuestionnaireResponse`, `LeadUploadToken`, `HcLeadgenConfig`), and the D-1/D-2 fixed-question-key conventions this phase's questionnaire-response mapping must respect
- `docs/decisions/0005-auth-strategy.md` — the `client_invite_tokens` pattern this phase's upload-token issuance mirrors exactly
- `docs/domain/compliance-india.md` — DPDP consent requirements informing Stage 2's same-transaction `consent_given_at`/`consent_purpose` requirement
- Existing code read directly as prior art (not docs, but load-bearing for this plan): `backend/src/auth/router.py` (public-endpoint and token-validation pattern), `backend/src/api/clients.py` (token generation), `backend/src/lib/email.py` (email function shape), `backend/src/api/leadgen.py` (IntegrityError disambiguation pattern; no-services-layer convention), `backend/src/main.py`, `frontend/src/app/api/[...path]/route.ts` (BFF proxy), `frontend/src/app/(public)/layout.tsx` and `frontend/src/app/(app)/clients/[clientId]/page.tsx` (routing and data-fetching conventions)

## 6. Verification

Not yet executed — phase not yet built. Once implemented, the verification bar mirrors PHASE-01's: full backend + frontend test suite green, a `docs/VERIFICATION.md` entry, and a manual/Playwright browser walkthrough of the intake page (HC's configured questionnaire renders correctly, consent gate works, submission shows the same-page confirmation with no redirect, duplicate submission shows the correct plain-language message, `noindex` meta tag present). Fill in actual date, test count, and `VERIFICATION.md` link upon completion.

## 7. Lessons learned

Not yet executed — to be filled in honestly upon completion. This section is what the next phase (Stage 4) reads first; do not pre-fill with speculative lessons before the work has actually happened.

## 8. Carry-over to subsequent phases

- `backend/src/api/intake.py` — establishes the public-endpoint file location and no-auth-dependency pattern; whichever phase adds `GET`/`POST /api/upload/:token` (Stage 4) should follow the same structure, likely as a sibling module.
- `backend/src/lib/rate_limit.py` — the shared `Limiter` instance and its conservative IP-key default (D-1). Reuse this module if a later phase needs rate limiting rather than standing up a second one.
- **D-1 is an explicit unresolved item, not a closed decision** — whoever next touches rate limiting, or deploys this to a real environment with known edge topology, needs to revisit the IP-key logic with real infra information rather than treating the conservative default as permanent.
- **D-5 (MIME magic-byte approach) directly informs Stage 4.** The 3-signature check (PDF/JPEG/PNG) and its rationale — this repo's existing Content-Type-only convention relies on an authenticated, accountable uploader, which Stage 4's endpoint lacks — should be applied there, not re-litigated from scratch.
- `LeadUploadToken` rows created by this phase's Stage 3 step (14-day expiry, SHA-256 hash, raw token embedded in the emailed link) are exactly what Stage 4's upload endpoint will validate and consume — the token pattern itself needs no further design work by that phase.
- `frontend/src/app/(public)/intake/` establishes the public-route pattern (a Server Component `layout.tsx` for page metadata, wrapping a `"use client"` page) that a later `/upload/[token]` page should mirror.

---

## Implementation Plan

Ordered task breakdown for whoever executes this phase (expected via `superpowers:subagent-driven-development`, one fresh implementer + reviewer per task, matching PHASE-01's execution approach — though PHASE-01's *document* format should not be repeated, its execution discipline should be).

**Task 1 — Rate-limiting infra (`slowapi`).** Add `slowapi` to `backend/pyproject.toml`. New `backend/src/lib/rate_limit.py` exporting a module-level `limiter = Limiter(key_func=get_remote_address)` per Decision D-1. Wire `app.state.limiter = limiter` and the `RateLimitExceeded` exception handler in `backend/src/main.py`, near the existing `CORSMiddleware` registration. Gotcha to design around: `slowapi`'s in-memory storage is a process-global singleton not reset between test functions by default — add an autouse, function-scoped conftest fixture that resets it before each test (verify the exact reset API against the installed `slowapi`/`limits` version rather than assuming, same discipline PHASE-01 applied to the standalone-script session-factory pattern).

**Task 2 — Email: `send_lead_test_recommendation_email`.** New function in `backend/src/lib/email.py`, mirroring `send_action_items_email`'s exact shape: `html.escape()` on every interpolated body value (not the subject), inline HTML/CSS matching the existing brand colors, Resend call. Subject and body content match SPEC-0001 Stage 3 step 8 verbatim.

**Task 3 — `GET /api/intake/:slug`.** New `backend/src/api/intake.py`, registered in `main.py`. Public (no `HcClaimsDep`/`ClientClaimsDep`, mirrors `auth/router.py`'s public-endpoint style, uses `DbDep` directly). Resolve `hc_slug` → `HcLeadgenConfig` joined to `User`; generic 404 if unresolved (no existence-leaking, consistent with the repo's cross-tenant-404 convention). Response is a strict allowlist model built field-by-field — `{hc_name, hc_photo_url, questionnaire}` only, never `model_validate()` on the full config object, so a future column addition to `HcLeadgenConfig` can't silently leak through this endpoint. `hc_name` from `first_name`/`last_name`; `hc_photo_url` blank when null per D-3.

**Task 4 — `POST /api/intake/:slug` (Stage 2).** Same file. Request body: submitted answers keyed by question key, plus `consent_ack: bool` (server-enforced true, defense-in-depth beyond the frontend checkbox). Validate before any write: every `required: true` question answered; `multiple_choice` answers within the configured options; `scale` answers in range 1–10. One transaction: create the `Lead` row (`status="questionnaire_submitted"`, `consent_given_at=now()`, `consent_purpose=<verbatim spec copy>`) mapping the six fixed keys onto `Lead` columns per PHASE-01's D-2, plus one `LeadQuestionnaireResponse` row per question (preserving `question_text` verbatim). On `uq_leads_hc_user_id_email` violation: rollback, then re-query to confirm the collision is genuinely on that constraint before returning 409 with the spec's exact plain-language message — do not trust a bare `except IntegrityError`, mirroring the disambiguation pattern already established in `leadgen.py`'s `init_leadgen_config`.

**Task 5 — Stage 3 orchestration.** Fires inline in the same handler, immediately after Stage 2's commit (no separate endpoint, per spec). Extract a pure, independently unit-tested `_build_test_recommendation(test_panel, responses) -> dict` — standard tests always included, case-insensitive substring keyword matching against `condition_rules` (D-4), dedup, exact `{standard, additions: [{test, triggered_by}], all_tests}` shape. Unit-test this in isolation (no DB, no HTTP) — the false-addition and dedup edge cases are exactly what SPEC-0001's acceptance criteria scrutinize. Then: set `lead.test_recommendation` + `status="tests_recommended"`, issue the `LeadUploadToken` using the exact `client_invite_tokens` generation pattern (`os.urandom(32).hex()` raw token, `hashlib.sha256(...).hexdigest()` stored hash, 14-day expiry), commit, then attempt the recommendation email wrapped in try/except per D-2 (log on failure, don't raise).

**Task 6 — Frontend: `frontend/src/lib/api/intake.ts`.** New module using plain `fetch()` against the same-origin BFF proxy — not `fetchWithAuth`, since these calls are unauthenticated. Zod schemas mirroring the backend's request/response shapes. Functions surface the structured 409 (duplicate email) and 429 (rate-limited) bodies distinctly so the page can render the spec's exact plain-language copy for each, not a generic error.

**Task 7 — Frontend: the public intake page.** New `frontend/src/app/(public)/intake/layout.tsx` — a Server Component (no `"use client"`) exporting `metadata.robots = {index: false, follow: false}`, satisfying the DPDP `noindex` requirement in a way a client component cannot (this codebase's page convention is 100% `"use client"` + `useParams()`, confirmed via existing pages, which is why the metadata has to live in a wrapping layout). `frontend/src/app/(public)/intake/[slug]/page.tsx` stays `"use client"`: renders HC name/photo, a dynamic form driven by the fetched `questionnaire` array (`free_text`/`multiple_choice`/`scale`, using plain styled `<input>` elements — no `Checkbox`/`RadioGroup` primitive exists in this repo yet), the exact consent copy from SPEC-0001 Stage 2 step 3 gating the submit button, and on success a same-page confirmation state (no redirect, per spec). Renders the spec's exact plain-language messages on 409/429.

**Verification, end to end:** integration tests mirror `test_client_auth.py`'s no-auth-headers pattern (HC sets up leadgen config via `hc_headers`, then all intake calls go through `http_client` with no `Authorization` header) — duplicate-email 409, rate-limit 429 (5 requests with distinct emails succeed, 6th fails), consent-required 422, and the DPDP acceptance criterion that `consent_given_at`/`consent_purpose` are non-null before any `lead_questionnaire_responses` rows exist, in the same transaction. Full backend + frontend suite green, plus the manual browser walkthrough described in §6, before this phase is considered done.
