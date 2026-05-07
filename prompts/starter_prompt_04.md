We are continuing the build. Scope of this session: **PHASE-05 — HC Cycle Workflows + Client File Library**, per `docs/build-plan.md`. PHASE-05 has two parts (A and B) that ship together but verify independently. Stop at the end of PHASE-05 — do not start PHASE-06.

P0–P4 are complete and manually verified. Latest state: 144/144 tests passing. The cleanup session has run; specs live under `docs/specs/Unit_001_HcCoreCycle/`. ADR-0006 §5 and ADR-0003 §4/§7 amendments landed (2026-05-04) and are in effect.

# Mandatory preparation (before writing any code)

1. Read `CLAUDE.md` (root) and `PREFLIGHT.md` in full. The anthem and the preflight block are non-negotiable for every substantive response in this session.
2. Read `docs/SESSION_LOG.md` — the latest three entries. P4 entry, naming-cleanup entry, PHASE-04 retroactive-write entry. These together are your authoritative current state. Trust them, but verify against the actual files when something looks off.
3. Read `docs/build-plan.md` Phase 5 section in full (it has Part A and Part B subsections). Also read the "How to use this when working with Claude Code" loop — the first step is "write the PHASE file before implementation begins."
4. Read every primary source doc the matrix marks for P5:
   - `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` — full read. The HC cycle stages (especially Stages 1–6) define what Part A implements; M000 stage 2 is the first-session edge case.
   - `docs/domain/glossary.md` — for HC cycle terminology (MOM, brief, AST, action item, snippet, check-in)
   - `docs/domain/actors.md` — for who can read/write what (Part A's coach-reviewed gate, Part B's tenant-scoped file access)
   - `docs/decisions/0003-llm-strategy.md` (amended 2026-05-04) — `llm_calls` schema, snippet selection, retention rules
   - `docs/decisions/0006-observability.md` (amended 2026-05-04) — PII redaction, prompt/completion encryption, scrub() coverage
   - `docs/decisions/0001-stack-selection.md` — S3 Mumbai for storage (Part B)
   - `docs/decisions/0005-auth-strategy.md` — tenant scoping pattern (applies to all new endpoints)
5. Read `docs/specs/Unit_001_HcCoreCycle/PHASE-04-llm-service.md` — the retroactive write covers what P4 shipped. Pay attention to:
   - Section 3 (decisions) — Option C snippet selection, ADR amendment context
   - Section 7 (lessons learned) — patterns to inherit
   - Section 8 (carry-over) — what P5 directly builds on (`session_notes` is currently transient; `llm_service.prompts.assemble_*` is the chokepoint to extend)
6. Read `docs/specs/template-phase-plan.md` and `.claude/skills/skill-write-phase-plan.md` — you'll write the PHASE-05 plan using these.
7. Read `docs/diagrams/0002-data-model.md` — for current schema. Part A adds a column; Part B adds a table.

If any referenced document is missing, contradicts another, or contradicts SESSION_LOG, **stop and produce a `## Context missing` block** per anthem rule 7. Do not guess. Do not pick a winner silently.

# Source-doc consistency check (do this before writing any code)

After reading the source docs, produce a short report:
- "Source docs consistent: [yes / no]"
- If no: list each contradiction.
- Specifically confirm:
  - (a) ADR-0006 §5 amendment (2026-05-04) is present in the file — search for "amended 2026-05-04"
  - (b) ADR-0003 §4 amendment (2026-05-04) is present in the file
  - (c) `clients.code` column exists in the data-model diagram and matches what's in the DB (per migration `95df31e31f5f`)
  - (d) `llm_calls.prompt_text` and `llm_calls.completion_text` are in the diagram as encrypted columns

# Operating rules for this session

- Run a preflight block (per `PREFLIGHT.md`) before every substantive response. Compressed (3 lines) is fine for tight follow-ups; full preflight before each new sub-task.
- **PHASE plan first, code second.** Anthem rule 9. Before any implementation code, write `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` using `template-phase-plan.md` and `skill-write-phase-plan.md`. The PHASE plan covers BOTH Part A and Part B — single file, two parts inside. Get SoJo's confirmation on the PHASE plan before writing implementation code.
- **Two-part execution.** Build Part A in full → declare ready for manual verification → SoJo verifies → fix any failures → only then start Part B. Part A and Part B share one PHASE file but two verification gates. See "Two-stage completion" section below.
- **Verify before claiming done.** "It should work" is banned (rule 14). Run pytest, hit endpoints with curl, query S3 (Part B), inspect `llm_calls.prompt_text` via decryption. The Postgres MCP (read-only) is available — use it for verification queries; never as a fallback to skip writing tests.
- Commit per `CONTRIBUTING.md`. Conventional commits, one logical change per commit. Don't squash multiple deliverables into one commit.
- No secrets in code. `OPENROUTER_API_KEY`, `LLM_CALL_ENCRYPTION_KEY` already populated. Part B may need new env vars (S3 credentials and bucket name) — confirm against ADR-0001 / `docs/ops/secrets-management.md` before adding.
- Maintain `docs/SESSION_LOG.md` and `docs/VERIFICATION.md` as you go (see "Living docs" section below).

# Phase 5 scope — what to build

This is the contract from `docs/build-plan.md` Phase 5 plus the design decisions resolved in the prep conversation (2026-05-04 → 2026-05-05). The PHASE plan must reflect both.

## Part A — HC Cycle Workflows

### Deliverables

1. **Add `sessions.session_notes` column** (text, nullable). Alembic migration. HC types observations during/after session; persisted; viewable; editable freely. Every PATCH overwrites; new draft regeneration uses latest content.

2. **Pre-session brief endpoint** (`GET /sessions/{session_id}/brief`) — already exists from P4 as cache-first then `generate_brief()`. Extend per Part A scope:
   - Pull prior MOM (if exists) + AST (open action items, recent status, trends) + snippet payload (per P4 Option C selection) + recent check-ins
   - Pass all of the above to the LLM service via the brief prompt assembly
   - For M000 (first session): empty AST and empty snippets → return the M000 prep view per SPEC-0001 §Stage 2 (intake notes + checklist), NOT a normal brief

3. **MOM workflow end-to-end**:
   - `POST /sessions/{session_id}/mom/draft` — already exists from P4. Extend to **persist `session_notes`** before generating the prompt: write `sessions.session_notes` first, then call `generate_mom_draft()` with it.
   - `PATCH /sessions/{session_id}/mom` — already exists from P4 (snippet capture fires). No change needed unless something surfaces.
   - `POST /sessions/{session_id}/mom/send` — already exists from P3. No change.
   - **Re-draft path**: HC may regenerate the draft after editing `session_notes`. Each call writes a new `llm_calls` row. The MOM `draft_text` is overwritten with the latest draft. Verify via integration test.

4. **Session notes CRUD**:
   - `GET /sessions/{id}` — extend response to include `session_notes`
   - `PATCH /sessions/{id}` — accept `session_notes` field; persist it
   - HC can re-edit `session_notes` after a draft has been generated; subsequent draft regeneration uses the updated content

5. **Action item lifecycle**:
   - States: `open` → `in_progress` → `completed` / `missed`. P3 has CRUD; P5 adds the `missed` transition logic — manual transition is acceptable in P5 (auto-flagging on `due_date` is P7). Document the deferral in PHASE plan.
   - Triage flag aggregation: action items in `missed` state surface in the next brief's triage section.

6. **AST endpoint** (`GET /clients/{client_id}/ast`):
   - Returns structured response: open action items list, status summary, trend tags
   - Computed at request time (not cached) per ADR-0003 deferral
   - Tenant-scoped per ADR-0005

7. **Triage flags in brief**:
   - Brief assembly includes a "triage" section listing missed action items, manually-flagged sentiment concerns, and recency-based concerns (e.g., client hasn't checked in for X days)
   - Sentiment flags are manual at MVP — exposed via `PATCH /check-ins/{id}/flag` from P3 already
   - Recency-based concerns: define rule in PHASE plan (e.g., "no check-in for >7 days" or similar — confirm in SPEC-0001)

### Acceptance criteria (Part A)

These are tickable in `docs/VERIFICATION.md` § P5 Part A:

- [ ] End-to-end M00N session works: HC creates session → enters notes (text) → notes persist → generates brief → conducts session → generates MOM draft → edits → sends
- [ ] `sessions.session_notes` viewable via `GET /sessions/{id}` and editable via `PATCH /sessions/{id}`; HC can re-edit after a draft has been generated
- [ ] Brief includes: 1+ snippet (if available), open action items count, last MOM summary, recent check-in summary
- [ ] Re-draft path: HC edits `session_notes`, regenerates draft, second `llm_calls` row appears; second draft reflects updated notes
- [ ] Action items from sent MOM appear in next brief's AST as `open`
- [ ] Action item manually transitioned to `missed` → flagged in next brief's triage section
- [ ] Coach-reviewed gate verified at workflow level: client cannot view brief content (briefs are HC-internal)
- [ ] AST endpoint returns structured response with open items, status summary, trend tags
- [ ] M000 flow: first session has empty AST and empty snippets → brief endpoint returns "M000 prep" view per SPEC-0001 §Stage 2
- [ ] Cross-tenant: HC2 cannot see HC1's session_notes, briefs, AST data via any endpoint
- [ ] All tests passing (target: ~165+, delta from P4: +20 or so)

---

## Part B — Client File Library

### Deliverables

1. **Storage layout** on AWS S3 Mumbai (per ADR-0001):
   - Path pattern: `client_session_library/CP<NNNN>_<Sanitized_FirstName>_<Sanitized_LastName>/<YYYY-MM-DD>_session-<NN>/<filename>`
   - Per-HC tenant isolation via S3 prefix per HC, OR per-HC bucket — decide in PHASE plan with reasoning. Prefix is simpler; bucket-per-HC is stronger isolation.
   - Sanitization: `[A-Za-z0-9_.-]`, replace spaces with `_`, max 40 chars per name segment
   - Date in IST (per the build-plan decision); session number is zero-padded two-digit per-client

2. **`client_files` table** (Alembic migration):
   ```
   id              UUID PRIMARY KEY
   session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE
   hc_user_id      UUID NOT NULL REFERENCES users(id)
   client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE
   original_filename TEXT NOT NULL
   storage_path    TEXT NOT NULL                 -- S3 key
   mime_type       TEXT NOT NULL
   size_bytes      BIGINT NOT NULL
   uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
   is_zoom_summary BOOLEAN NOT NULL DEFAULT FALSE
   ```
   Tenant-scoped per ADR-0005. Cascade-delete on client deletion (the CASCADE handles it; the consent-revocation purge in ADR-0003 §7 cascade is already correct via `clients` cascade).

3. **`session_notes.txt` mirroring** (Option A — DB is canonical, decided 2026-05-04):
   - When `sessions.session_notes` is saved/updated (Part A `PATCH /sessions/{id}` endpoint), backend ALSO writes a `session_notes.txt` file into that session's S3 folder
   - The DB column is canonical; the file is a read-only mirror written on every save
   - HC may view the file for backtrack reference; if they edit it on disk, the next textarea save overwrites their edit
   - Document this clearly in `domain/glossary.md` and in the PHASE plan

4. **File upload endpoint**: `POST /sessions/{session_id}/files` (multipart):
   - Accepts 1+ files in one request
   - Validates: max file size (suggested 25 MB; finalize in PHASE plan), accepted MIME types whitelist (`text/plain`, `text/markdown`, `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, plus a small list — finalize in PHASE plan)
   - Optional `is_zoom_summary` query param or per-file flag in the multipart form
   - Auto-detection placeholder: filenames matching `zoom_ai_summary_*` may auto-set the flag — provisional convention to be finalized later, document as TODO in PHASE plan
   - Returns: list of created `client_files` rows with IDs and storage paths
   - Tenant-scoped: only the HC who owns the session can upload

5. **File listing endpoint**: `GET /sessions/{session_id}/files`:
   - Returns metadata for all files in this session (NOT the file contents — list only)
   - Tenant-scoped

6. **File deletion endpoint**: `DELETE /sessions/{session_id}/files/{file_id}`:
   - Removes both the S3 object and the `client_files` row
   - Tenant-scoped
   - Idempotent (404 if already deleted, not 500)

7. **LLM prompt assembly extended** in `backend/src/llm_service/prompts.py`:
   - The MOM and brief prompt assembly extend to include file content
   - Format per Option (b), decided 2026-05-04: distinct sections in the assembled prompt:
     ```
     ## HC's typed notes:
     <sessions.session_notes content>
     
     ## Uploaded files:
     ### <filename 1>
     <file content>
     
     ### <filename 2>
     <file content>
     ```
   - File content extraction: text and markdown files read directly; PDF files use a Python PDF library (e.g., `pypdf` or `pdfplumber` — pick one, document choice); .docx files use `python-docx` or similar
   - Token budget consideration: file content can be large. Define a max-tokens-per-file or max-total-file-tokens cap in `llm_config.yaml`. If exceeded, truncate with a clear marker (e.g., `[... truncated, file too long ...]`) and log a warning.

8. **Snippet capture exclusion for Zoom-tagged files**:
   - The snippet capture path (P4's `snippets.capture()`) MUST NOT learn style from content originating in files where `is_zoom_summary=true`
   - HC's edits to LLM drafts remain snippet-eligible regardless of source — what matters is that the Zoom AI's voice never enters the snippet library as the "original" pre-edit text
   - Implementation: when capturing a snippet, if the LLM's draft was generated from a prompt that included Zoom-tagged file content, mark the resulting snippet's `original_text` source provenance, OR exclude the snippet entirely if the diff appears to originate from Zoom-summary content. Decide approach in PHASE plan; verify by integration test.

### Acceptance criteria (Part B)

These are tickable in `docs/VERIFICATION.md` § P5 Part B:

- [ ] HC uploads 1+ files for a session via `POST /sessions/{id}/files` → files appear in S3 at the documented path → `client_files` rows created
- [ ] `client_files` rows are tenant-scoped: HC2 cannot see HC1's file metadata via any endpoint
- [ ] When `sessions.session_notes` is saved, `session_notes.txt` exists in the session's S3 folder with matching content
- [ ] If HC edits `session_notes` again, the file is overwritten with the new content
- [ ] HC generates MOM draft after uploading files → assembled prompt (visible in `llm_calls.prompt_text` via decryption) contains both "HC's typed notes:" and "Uploaded files:" sections with the right content under each
- [ ] HC uploads a file with `is_zoom_summary=true` → that file's content reaches the LLM but does NOT produce a `hc_style_snippets` row when the HC subsequently edits the draft
- [ ] HC uploads multiple files in one request → all appear in S3 and `client_files`
- [ ] HC deletes a file via `DELETE /sessions/{id}/files/{file_id}` → S3 object gone, `client_files` row gone
- [ ] Cascade-delete: revoking client consent (`DELETE FROM clients WHERE id = X`) removes all `client_files` rows AND all S3 objects under that client's prefix (test the cascade explicitly — S3 cleanup may need a separate sweep job; document in PHASE plan if so)
- [ ] File size and MIME validation: oversized or wrong-MIME file → 400 with clear error
- [ ] Pseudonymization preserved: file content is part of `prompt_text` but the storage path uses `clients.code` (not `clients.full_name`)
- [ ] All tests passing (target: ~185+, delta from Part A: +20 or so)

---

# Known gotchas for P5 (must be honored from day 1)

1. **Tenant scoping in EVERY new endpoint and EVERY new query.** Same pattern as P3/P4. Cross-tenant access = 404 (never 403). Add an integration test for every new endpoint that asserts cross-tenant access returns 404.

2. **Coach-reviewed gate continues.** Briefs are HC-internal; clients cannot view them. Test explicitly with a client-role JWT.

3. **S3 setup**: confirm the `boto3` or `aioboto3` library is appropriate for Cloudflare Python Workers (Pyodide compatibility). If not Pyodide-compatible, route file-upload endpoints to DO Bangalore per ADR-0002 — same pattern as DB-touching endpoints. Document the choice in PHASE plan.

4. **S3 credentials and bucket name in env vars**: add to `.env.example` (placeholder). Document in `docs/ops/secrets-management.md`. Don't hardcode bucket names — use `S3_BUCKET_NAME` or similar.

5. **Pseudonymization in S3 paths**: paths use `clients.code`, not `clients.full_name`. The sanitized full name is OK in the path for HC convenience (per the folder structure decision), BUT the `code` is the load-bearing identifier. If client name contains characters that fail sanitization, the path still works because `code` is always present and stable.

6. **`session_notes.txt` mirror is on every save, not just first save.** Overwrite is the correct behavior. Test by saving notes, viewing the file, editing notes, viewing the file again — content should reflect the latest save.

7. **Re-draft path correctness**: every draft regeneration writes a new `llm_calls` row. The encrypted `prompt_text` should differ between draft 1 and draft 2 if `session_notes` changed. Test this — decrypt both rows and verify difference.

8. **Snippet capture exclusion for Zoom files**: subtle. The HC's edit of the draft is what creates a snippet. If the draft was heavily influenced by Zoom AI summary content (which is in the prompt), an HC edit might be edit-from-Zoom-AI-style rather than edit-from-LLM-default-style. The point is to keep the Zoom AI's voice out of style learning. The simplest safe approach: when ANY file with `is_zoom_summary=true` was in the prompt, suppress snippet capture for that draft. More nuanced approaches (only suppress if the edit overlaps Zoom content) are deferred. Pick the simple approach for P5; document the tradeoff in PHASE plan.

9. **File content extraction**: PDF and .docx libraries vary in quality. Use a library that's mature and Pyodide-compatible if running on Workers, or DO Bangalore otherwise. Document the chosen libraries and their licenses in `pyproject.toml` and PHASE plan.

10. **Token budget for file content**: large files can blow the LLM context window. The `llm_config.yaml` already has `snippet_token_budget`; add `file_content_max_tokens_per_file` (suggested: 5000) and `file_content_max_total_tokens` (suggested: 15000) — finalize in PHASE plan. Truncate with a clear marker if exceeded.

11. **All httpx through `make_http_client()`** — same as P0–P4. Verify at end: `grep -r "httpx.AsyncClient(" backend/src | grep -v lib/http.py` returns empty.

12. **`get_settings()` not `settings`** — same as P0–P4.

13. **Absolute imports** — same as P0–P4.

14. **Test isolation: savepoints** — P3+ uses savepoint-based isolation. Inherit; don't fight it.

15. **Migration discipline**: Part A adds one column (`sessions.session_notes`); Part B adds one table (`client_files`). Two separate migrations, not one bundled.

# MCP: confirm Postgres MCP is reachable

Already verified for P3 and P4. Verify still reachable at start of P5 (read-only schema introspection). After Part A migration, refresh the MCP's schema cache so it sees the new column. Same after Part B.

# Living docs — maintain as you go

SoJo will not be reading every commit. They WILL read `SESSION_LOG.md` and `VERIFICATION.md` between sessions. Keep both current.

## `docs/SESSION_LOG.md` (append-only, latest at top)

At the end of each part (Part A complete, then Part B complete), append an entry. Specifically:

```markdown
## YYYY-MM-DD — P5 Part A: HC Cycle Workflows

**Done**:
- [bullet per major sub-task]

**Decided** (link ADRs / specs):
- [any decision that emerged mid-session]

**Bugs fixed mid-session**:
- [any]

**Part A status**: ✅ complete — manual verification passed YYYY-MM-DD (or ⏳ awaiting verification)

**Pending / next**:
- P5 Part B: Client File Library
- [any Part A carry-overs]

**Open questions for SoJo**:
- [any]
```

Same shape for Part B.

## `docs/VERIFICATION.md` (manual checklist for SoJo)

Append a section with TWO subsections — Part A and Part B — each with its own checks. SoJo ticks Part A independently before Part B is started.

Structure:

```markdown
## P5 — HC Cycle Workflows + Client File Library

### Part A — HC Cycle Workflows

**Status**: ⏳ awaiting verification (or ✅ verified YYYY-MM-DD)

[checks per Part A acceptance criteria — concrete curl commands and expected outputs]

### Part B — Client File Library

**Status**: ⏳ awaiting verification (or ✅ verified YYYY-MM-DD)

[checks per Part B acceptance criteria — concrete curl commands, S3 verification commands, expected outputs]
```

Each check has:
- The exact command to run (curl, psql, or Postgres MCP query)
- The expected output
- A checkbox

# Two-stage completion: Part A and Part B each have their own gate

P5 has two completion gates. Both must pass before P5 is considered done.

## Stage 1 — Part A: Claude Code declares "ready for manual verification"

When all Part A deliverables are implemented, all Part A automated tests pass, the PHASE plan covers Part A in full, and `SESSION_LOG.md` + `VERIFICATION.md` are updated with the Part A section, produce the `## P5 Part A verification summary`. End with — verbatim:

> **P5 Part A is ready for SoJo's manual verification. Not complete until manual verification passes. Awaiting confirmation before Part B work begins.**

Then STOP. Do not start Part B. Wait.

## Stage 2 — Part A: SoJo runs manual verification

Three outcomes:
- **Pass** → SoJo says "Part A verified, proceed to Part B." Then begin Part B.
- **Fail** → SoJo lists failures. Fix them in this same session (write failing test → fix → confirm green → update VERIFICATION.md). Re-issue ready-for-verification message. Repeat.
- **Spec gap** → discuss with SoJo. Decide whether to fix in Part A or defer.

## Stage 3 — Part B: Claude Code declares "ready for manual verification"

After Part A is verified by SoJo, build Part B. When complete, produce `## P5 Part B verification summary`. End with — verbatim:

> **P5 Part B is ready for SoJo's manual verification. P5 is not complete until manual verification passes. Awaiting confirmation before any P6 work begins.**

Then STOP.

## Stage 4 — Part B: SoJo runs manual verification

Same three-outcome structure as Stage 2.

# Definition of done for P5 (after both parts verified)

- All Part A and Part B deliverables implemented
- Two new migrations: `sessions.session_notes`, `client_files` table
- All endpoints implemented and tenant-scoped
- LLM prompt assembly extended for file content
- `session_notes.txt` mirroring working
- Snippet capture exclusion for Zoom files working
- All tests passing (target: ~185+ from current 144)
- PHASE-05 plan at `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md`, status: Complete | Verified
- `SESSION_LOG.md` updated with Part A entry AND Part B entry
- `VERIFICATION.md` § P5 Part A and Part B both ticked
- Conventional commits, atomic
- No `httpx.AsyncClient(` outside `src/lib/http.py`
- No raw secret references outside `get_settings()`
- Cross-tenant access tests for every new endpoint

# Start

Begin with a preflight block covering this whole session. Then:

1. Read the prep documents listed above (in order)
2. Produce the source-doc consistency report
3. Write `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` per `template-phase-plan.md` and `skill-write-phase-plan.md` — covers BOTH Part A and Part B in one file with clear section separation
4. Present the PHASE plan for SoJo's review **before** writing any implementation code
5. Wait for SoJo's confirmation on the PHASE plan before implementation
6. Then implement Part A → declare ready for verification → wait
7. After Part A verified: implement Part B → declare ready for verification → wait
