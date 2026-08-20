# PHASE-03: Blood report upload and pre-consultation brief generation

**Unit**: Unit_003_ClientDiscoveryPipeline
**Status**: Draft
**Verification date**: TBD — fill in after implementation and verification
**Implements**: SPEC-0001 §Stage 4 (Lead uploads blood report); §LLM involvement (`lead_brief` task type); Acceptance criteria §Blood report upload, §Brief generation (partial — the two `llm_calls`-row-written and `brief_llm_call_id`-populated criteria are covered here; the DPDP `noindex` criterion is covered here for `/upload/:token`, mirroring PHASE-02's coverage of `/intake/:slug`)
**ADRs implemented**: ADR-0003 (LLM strategy) — new `lead_brief` task type, follows the existing prompt-file + schema + `parse_or_retry` + `write_llm_call` pattern. ADR-0005 (auth strategy) — `lead_upload_tokens` validation reuses the exact hash-and-compare pattern `lead_upload_tokens` issuance already established in PHASE-02 (mirroring `client_invite_tokens`). ADR-0006 (observability) — `llm_calls` row written for `lead_brief` on both success and failure, per the existing convention (no schema changes — see Decision D-1 below).

---

## 0. Per-requisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific I haven't provided. Ready?

## 1. Scope

This phase builds Stage 4 of SPEC-0001: a Lead who received the Stage 3 recommendation email opens `tapas.app/upload/:token`, uploads their blood report (PDF/JPEG/PNG), and — with no HC involvement — the system stores the file(s) in R2, extracts text from any PDF, and generates an LLM pre-consultation brief for the HC. Concretely: two public (token-authenticated) endpoints, PDF/JPEG/PNG magic-byte validation, R2 storage, a new `lead_brief` LLM task type, two new outbound HC-notification emails (success/failure), and the public upload page itself.

**Not in scope** (deferred to PHASE-04, mirroring how PHASE-02 isolated Stage 2/3 from Stage 4): `GET /api/leads`, `GET /api/leads/:id`, `PATCH /api/leads/:id`, `POST /api/leads/:id/remind`, `POST /api/leads/:id/convert`, `POST /api/leads/purge-expired` — i.e. all HC-facing Lead viewing, reminder, conversion, and purge (SPEC-0001 Stages 5–6). None of these endpoints exist yet in the codebase as of this phase's start. PHASE-01 (`leads`, `lead_questionnaire_responses`, `lead_upload_tokens`, `lead_files`, `hc_leadgen_config`) and PHASE-02 (public intake, Stage 2/3) are completed prerequisites this phase reads from but does not modify.

## 2. Deliverables planned

- `backend/src/lib/mime_sniff.py` (new) — pure function, 3-signature magic-byte check (PDF/JPEG/PNG), per PHASE-02 Decision D-5. No new dependency.
- `backend/prompts/lead_brief.md` (new) — YAML frontmatter (`task_type: lead_brief`, version `1.0.0`), prompt body per SPEC-0001's Inputs/Output rows.
- `backend/src/llm_service/schemas/lead_brief.py` (new) — `LeadBriefSchema` Pydantic model + `to_brief_text()`, mirroring `BriefSchema`'s shape.
- `backend/src/llm_service/__init__.py` — add `generate_lead_brief(...)`: new orchestration function, does not raise on failure (see Decision D-2).
- `backend/src/lib/email.py` — add `send_lead_brief_ready_email(...)` (success copy) and `send_lead_brief_failed_email(...)` (failure copy), mirroring `send_lead_test_recommendation_email`'s shape.
- `backend/src/api/upload.py` (new) — `GET /api/upload/:token` (public; token validity states only, no PII), `POST /api/upload/:token/files` (public, rate-limited; multipart upload, R2 storage, brief generation trigger).
- `backend/src/main.py` — register `upload_router`.
- `backend/tests/integration/test_upload_public.py` (new)
- `backend/tests/unit/test_mime_sniff.py` (new) — pure-function tests for magic-byte detection.
- `backend/tests/unit/test_lead_brief_prompt_assembly.py` (new) — pure-function tests for the prompt-input assembly logic (no DB/HTTP), same discipline as PHASE-02's `_build_test_recommendation` tests.
- `frontend/src/lib/api/upload.ts` (new) — unauthenticated API module, Zod schemas.
- `frontend/src/app/(public)/upload/[token]/layout.tsx` (new) — Server Component, `noindex` metadata.
- `frontend/src/app/(public)/upload/[token]/page.tsx` (new) — the public upload page.

## 3. Decisions made during this phase

**D-1 — No new `llm_calls` schema for this phase; reuse the existing `error_message` column.** SPEC-0001's §LLM involvement "On failure" row references `status='failed'` and `error_detail` columns "per the P7 migration adding those columns" — no such migration exists in this codebase (`backend/src/db/models/llm.py` has `error_message`, not `error_detail`, and no `status` column; that "P7" label belongs to a different unit's history, not this one). This phase treats the spec's wording as describing *behavior* (a failed call is identifiable) rather than mandating literal column names — the existing convention (`error_message` non-null ⟺ failed, matching how `generate_mom_draft`/`generate_brief` already behave) already satisfies every acceptance criterion under §Brief generation. Decided with SoJo, 2026-08-13. Same interpretive move as PHASE-02's D-4 (spec's "ILIKE" language read as semantics, not a literal query).

**D-2 — `generate_lead_brief()` does not raise on LLM failure; `generate_mom_draft`/`generate_brief` do.** Both existing orchestration functions raise `HTTPException` (503/422) on failure, appropriate because they're called mid-HC-driven-request where a failure should surface to the HC's screen. `lead_brief` fires inside an *unauthenticated Lead's* upload request — the Lead must see their upload succeed regardless of brief outcome (SPEC-0001's edge-case table: "Lead status still advances to `report_uploaded`" on brief failure). `generate_lead_brief()` therefore catches its own failures internally, writes the `llm_calls` row with `error_message` set (same as the other two functions' failure path), and returns `(None, None)` for `(brief_text, llm_call_id)` rather than propagating an exception. The caller (`POST /api/upload/:token/files`) never sees an exception from this call.

**D-3 — Rate limit on `POST /api/upload/:token/files`: 10 requests/hour per IP, reusing the existing `slowapi` `Limiter`.** SPEC-0001 states no explicit number for this endpoint (unlike intake's spec'd 5/hour). Proposed default: file uploads are heavier than a questionnaire submit but a legitimate Lead only needs a handful of attempts (initial + retries after a transient R2 failure per the edge-case table); 10/hour is generous enough for retries without being a meaningfully weaker ceiling than intake's. `GET /api/upload/:token` (read-only token-state check) is not rate-limited — same asymmetry as `GET /api/intake/:slug` vs `POST /api/intake/:slug` in PHASE-02. **Flagged for confirmation during spec review** — this number is this phase's judgment call, not spec'd.

**D-4 — `generate_lead_brief()` takes no snippets, per spec ("Snippet injection: None").** Structurally this makes it the simplest of the three orchestration functions — no `select_snippets`/`update_usage` calls, no `_format_snippets`. This also means `generate_lead_brief()` cannot reuse `generate_brief()`'s body via a shared helper without threading an unused snippet path through it; it is a standalone function, not a wrapper.

**D-5 — Multi-file upload is sequential, not concurrent, per file.** SPEC-0001's Stage 4 steps 6–8 describe a strict sequence (each file uploaded to R2, `lead_files` row created only after R2 confirms, token marked used only after *all* files succeed). Uploading files concurrently would complicate the "token not consumed on any failure" invariant (a partial-success race) for no real benefit at the expected file counts (≤5 files, ≤30 MB total per SPEC-0001 Stage 4 step 4's client-side caps). Sequential `for file in files: await ...` in the handler.

## 4. Bugs fixed mid-phase

Not yet executed — this section is filled in during/after implementation, per the project template.

## 5. Source docs consulted

- `docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` — §Stage 4, §Data (`lead_files`), §API surface (Public — `/api/upload/*`), §LLM involvement (`lead_brief`), §Coach-reviewed gate, §Edge cases and failure modes (R2 failure, unextractable PDF, expired/used token, LLM failure), §Acceptance criteria (§Blood report upload, §Brief generation)
- `docs/specs/Unit_003_ClientDiscoveryPipeline/PHASE-01-leadgen-data-layer-and-setup.md` §Task 3 — confirms `LeadFile`, `leads.brief_text`, `leads.brief_llm_call_id` already exist; no new migration needed this phase
- `docs/specs/Unit_003_ClientDiscoveryPipeline/PHASE-02-public-intake-and-lab-recommendation.md` §3 (D-5 MIME magic-byte approach, D-6 deferred OTP), §8 Carry-over (explicitly anticipates this phase) — the public-endpoint pattern (`intake.py`), the `LeadUploadToken` pattern this phase's validation consumes, `backend/tests/conftest.py`'s `reset_rate_limiter` fixture
- `docs/decisions/0003-llm-strategy.md`, `docs/decisions/0005-auth-strategy.md`, `docs/decisions/0006-observability.md`
- Existing code read directly as prior art: `backend/src/llm_service/__init__.py` (`generate_mom_draft`, `generate_brief` — orchestration shape, `write_llm_call` failure-path convention), `backend/src/lib/file_extraction.py` (`extract_text`, already handles PDF via `pypdf`), `backend/src/lib/s3.py` (`s3_put`, R2 client, no boto3 per its own header comment), `backend/src/db/models/llm.py` (`LlmCall` — confirms no `status`/`error_detail` columns, informing D-1), `backend/src/db/models/leadgen.py` (`Lead`, `LeadFile`, `LeadUploadToken` — confirms schema is already in place), `backend/src/api/intake.py` and `backend/src/api/files.py` (public-endpoint and file-upload conventions), `backend/prompts/brief_assemble.md` (prompt-file format to mirror)

## 6. Verification

Not yet executed — this section is filled in after implementation, per the project template. Verification should cover, at minimum, every checkbox under SPEC-0001's §Acceptance criteria → §Blood report upload and §Brief generation, plus the DPDP `noindex` criterion for `/upload/:token`.

## 7. Lessons learned

Not yet executed — this section is filled in after implementation, per the project template.

## 8. Carry-over to subsequent phases (anticipated)

- `backend/src/api/upload.py` and `backend/src/lib/mime_sniff.py` — whichever phase adds any other unauthenticated file-intake surface should reuse `mime_sniff.py` rather than re-implementing magic-byte checks.
- **PHASE-04 (Stage 5–6) depends on this phase's `leads.brief_text`/`brief_llm_call_id` and `lead_files` rows being populated** — Lead Detail page (`GET /api/leads/:id`) reads all three; conversion (`POST /api/leads/:id/convert`) copies `brief_text` verbatim into the M000 session per SPEC-0001 Stage 6.
- **PHASE-02's Stage-3 two-commit recovery gap (leads stuck at `questionnaire_submitted` if Stage 3's second commit fails) is still unresolved** — out of this phase's scope, still owed to whichever phase builds `POST /api/leads/:id/remind` (now confirmed to be PHASE-04, not this one).
- D-3's rate-limit number (10/hour) is this phase's own judgment call, not spec-derived — flag for revisit alongside PHASE-02's D-1 (same unresolved IP-trust-topology issue applies here too, same `Limiter`).
- No ADR amendment needed for D-1 (no schema change) — but if a future phase *does* need a real `status`/`error_detail` column on `llm_calls` (e.g. for a dashboard querying failure rate cheaply without string-matching `error_message IS NOT NULL`), that phase should write the actual migration SPEC-0001 assumed already existed, and should also correct SPEC-0001's own wording at that point.

---

## Implementation Plan

Ordered task breakdown for whoever executes this phase (expected via `superpowers:subagent-driven-development`, one fresh implementer + reviewer per task, matching PHASE-01/PHASE-02's execution discipline).

### Task 1 — `backend/src/lib/mime_sniff.py`

Pure function `sniff_mime(content: bytes) -> str | None` — checks the first bytes of `content` against three signatures: `%PDF` → `application/pdf`, `\xff\xd8\xff` → `image/jpeg`, `\x89PNG\r\n\x1a\n` → `image/png`. Returns `None` if none match (caller rejects). No dependency on declared `Content-Type` or filename extension anywhere in this function — per D-5 (PHASE-02's, not this phase's D-5) and the acceptance criterion that a `.jpg`-named PDF is accepted and a `.exe` is rejected regardless of declared MIME type. Unit-test with real minimal byte sequences for each signature, plus a clearly-neither case (e.g. `.exe` magic bytes `MZ`).

### Task 2 — `backend/prompts/lead_brief.md` + `backend/src/llm_service/schemas/lead_brief.py`

Prompt file: YAML frontmatter (`version: "1.0.0"`, `created`, `notes`), body instructs the LLM to return JSON matching `{questionnaire_findings: str, blood_report_highlights: str, suggested_discussion_points: list[str], flags: list[str]}` (per SPEC-0001's Output row), with placeholders `{{QUESTIONNAIRE_SECTION}}`, `{{TEST_RECOMMENDATION_SECTION}}`, `{{BLOOD_REPORT_TEXT}}` (empty-string-safe — the unextractable-PDF case must produce a readable gap note in `blood_report_highlights`, not a crash). `LeadBriefSchema(BaseModel)` with a `to_brief_text()` method assembling the four fields into a single formatted string for `leads.brief_text`, mirroring `BriefSchema.to_brief_text()`'s style.

### Task 3 — `generate_lead_brief()` in `backend/src/llm_service/__init__.py`

New function, signature `generate_lead_brief(db, *, lead_id: UUID, hc_user_id: UUID, request_id: UUID | None = None) -> tuple[str | None, UUID | None]`. Loads `Lead` (404 if missing — should not happen, caller already resolved it), `HcLeadgenConfig.questionnaire` for question labels, `LeadQuestionnaireResponse` rows for answers, `leads.test_recommendation`, and the extracted blood-report text (passed in by the caller, already assembled from all accepted files via `extract_text()` — this function does not touch R2 or `lead_files` itself, keeping it testable without file I/O). Builds `system_prompt` via placeholder substitution, calls `call_openrouter`, `parse_or_retry` against `LeadBriefSchema`, `write_llm_call` with `hc_user_id=hc_user_id, client_id=None, session_id=None, use_case="lead_brief"`. **Per D-2: wraps the entire body in try/except — on any failure (LLM call exception, validation failure), writes the `llm_calls` row with `error_message` set exactly as the exception path already does, and returns `(None, None)` instead of raising.** No snippet calls at all (D-4).

### Task 4 — Email: `send_lead_brief_ready_email` / `send_lead_brief_failed_email`

Two new functions in `backend/src/lib/email.py`, mirroring `send_action_items_email`'s shape (`html.escape()` on interpolated values, existing brand inline CSS, Resend call). Subjects/bodies per SPEC-0001 Stage 4 step 13 (success) and the §Edge cases table's LLM-failure row (failure). Sent to the **HC**, not the Lead — confirm `hc_user_id` → `users.email` resolution follows the same pattern as PHASE-02's Stage 3 email.

### Task 5 — `GET /api/upload/:token`

New `backend/src/api/upload.py`, registered in `main.py`. Public (no `HcClaimsDep`, uses `DbDep` directly — mirrors `intake.py`). Hash the path token (SHA-256, same as `LeadUploadToken.token_hash`), look up the row. Branch: not found → generic invalid-link message; `used_at` set → "already uploaded" message (spec's exact copy); `expires_at` past → "link expired" message (spec's exact copy); otherwise valid → return `{hc_name}` only (resolved via the token's lead → `hc_user_id` → `users`), no Lead PII, no questionnaire data. All four states return `200` with a discriminated response shape (not 404) — the page needs to render *which* invalid state occurred, unlike the cross-tenant-404 convention (this isn't a tenant-isolation case, it's a Lead-facing state machine).

### Task 6 — `POST /api/upload/:token/files` (Stage 4 core)

Same file. Rate-limited per D-3. Re-validate token exactly as Task 5 (not found/used/expired → matching error responses, no upload processed). Client-side caps (≤5 files, ≤10 MB/file, ≤30 MB total) re-validated server-side — reject the whole batch before any R2 write if violated. Per file, per D-5 (sequential): read bytes, `sniff_mime()` (Task 1) — reject batch on any unrecognized file before any R2 write (partial-batch validation happens up front, not interleaved with upload, so a late rejection can't leave earlier files already in R2 while the token stays unused); build the R2 key `leads/<lead_id>/reports/<epoch_ms>_<sanitized_filename>` (reuse `_sanitize()` from `s3.py`, exported if not already); `s3_put()`; on success, create `LeadFile` row (not yet committed). After all files succeed: commit `LeadFile` rows, set `lead_upload_tokens.used_at = NOW()`, `leads.status = "report_uploaded"`, commit. Then: for each accepted PDF, `extract_text()` (empty string on failure/non-PDF, per spec); concatenate; call `generate_lead_brief()` (Task 3). If it returns a brief: set `leads.brief_text`, `leads.brief_llm_call_id`, commit, send `send_lead_brief_ready_email`. If it returns `(None, None)`: `leads.status` stays `report_uploaded` (already set), send `send_lead_brief_failed_email` instead — **do not** re-raise or fail the HTTP response; the Lead's upload already succeeded and must see a success confirmation regardless of brief outcome (D-2). Wrap the email sends themselves in try/except, log-only on failure — same non-blocking convention as PHASE-02's D-2.

### Task 7 — Frontend: `frontend/src/lib/api/upload.ts`

New module, plain `fetch()` against the same-origin BFF proxy, unauthenticated (mirrors `intake.ts`). Zod schemas for the token-state response (Task 5) and the upload response. Multipart form submission for the files POST. Surfaces the four token states (valid/expired/used/invalid) and the R2-failure "retry, your link is still valid" case distinctly, per spec's exact plain-language copy for each.

### Task 8 — Frontend: the public upload page

New `frontend/src/app/(public)/upload/[token]/layout.tsx` — Server Component, `metadata.robots = {index: false, follow: false}`, same reasoning as PHASE-02 Task 7 (this codebase's page convention is `"use client"` + `useParams()`, which can't export page-level metadata itself). `frontend/src/app/(public)/upload/[token]/page.tsx` — `"use client"`: on load, calls `GET /api/upload/:token`, renders the appropriate state (expired/used/invalid message with no upload UI, or the valid state with HC name + instructions + consent notice + file picker). Client-side pre-validation (file count/size/type) before enabling submit, per spec's step 4. On submit: multipart POST, loading state, success confirmation (spec's step 13's Lead-facing equivalent — the Lead sees a generic "reports received" confirmation, not the brief itself, per §Coach-reviewed gate: the brief is HC-internal and never delivered to the Lead). Render the R2-failure retry message on transient failure.

**Verification, end to end:** integration tests mirror `test_intake_public.py`'s no-auth pattern — token states (valid/expired/used/not-found) for both endpoints, magic-byte accept (`.jpg`-named PDF) / reject (`.exe`), R2-failure-leaves-token-unused (mock `s3_put` to raise), `lead_files` row created only after simulated R2 success, brief-generation success path (`llm_calls` row + `brief_text`/`brief_llm_call_id` populated) and failure path (`llm_calls` row with `error_message`, `brief_text` stays null, `leads.status` still advances), unextractable-PDF gap-note path. Full backend + frontend suite green, plus a manual browser walkthrough (valid upload happy path, expired-link state, used-link state, at minimum) before this phase is considered done.
