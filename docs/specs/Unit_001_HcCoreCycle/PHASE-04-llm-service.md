# PHASE-04: LLM Service

**Unit**: Unit_001_HcCoreCycle
**Status**: Complete | Verified
**Verification date**: 2026-05-04 — `docs/VERIFICATION.md` § P4
**Implements**: SPEC-0002 §Acceptance criteria (all criteria met)
**ADRs implemented**: ADR-0003 (LLM strategy — primary), ADR-0001 §LLM model chain, ADR-0006 §5 (observability — amended during this phase)

---

## 1. Scope

P4 built `backend/src/llm_service/` end-to-end: OpenRouter HTTP client, model-chain config, prompt file loader, `llm_calls` tracking with pgcrypto column encryption, snippet capture and injection, and two new API endpoints (`POST /mom/draft`, `GET /brief`). A migration added pgcrypto support and the encrypted `prompt_text`/`completion_text` columns to `llm_calls`, as well as the `clients.code` pseudonym column. The phase ended with 144/144 tests passing and all 15 manual verification checks green.

Not in scope: snippet retirement sweep (P7), full AST + triage flags in brief (P5), action item extraction endpoint (ai_assist.md prompt created; wired P5), ADR-0003/ADR-0006 formal amendment docs.

## 2. Deliverables shipped

**Migration `95df31e31f5f`**:
- `CREATE EXTENSION IF NOT EXISTS pgcrypto`
- `llm_calls.prompt_text BYTEA` — pgcrypto-encrypted system + user prompt
- `llm_calls.completion_text BYTEA` — pgcrypto-encrypted raw LLM response
- `clients.code VARCHAR NOT NULL UNIQUE` — CP\<NNNN\> pseudonym, unique per HC tenant
- `llm_calls.client_id FK → clients ON DELETE CASCADE`

**`backend/prompts/`** — three prompt files with YAML frontmatter (`version`, `created`, `notes`):
- `mom_draft.md` v1.0.0 — MOM draft generation from session notes + style snippets
- `brief_assemble.md` v1.0.0 — pre-session brief from prior MOM + recent check-ins
- `ai_assist.md` v1.0.0 — generic in-session assist (endpoint wired P5)

**`backend/src/llm_service/`** — full module:
- `llm_config.yaml` — 3-model chain (llama-3.3-70b primary → gemma-3-27b → nemotron-3-super-120b-a12b), `snippet_pool_size`, `snippet_token_budget`, `validation_retry_count`
- `config.py` — `LLMConfig` dataclass, `get_llm_config()` (`lru_cache`)
- `prompts.py` — `PromptFile`, `load_prompt()` — YAML frontmatter parser, version field written directly to `llm_calls.prompt_version`
- `tracking.py` — `write_llm_call()` — raw SQL INSERT with `pgp_sym_encrypt()`; NULL for error-path rows where no HTTP response arrived
- `snippets.py` — `capture()` (diff gate: threshold + whitespace filter), `select()` (Option C hybrid — see §3), `update_usage()`
- `client.py` — `call_openrouter()` — `make_http_client()` factory, `timeout=120.0`, returns `OpenRouterResult`
- `chain.py` — `build_models_array()`, `fallback_count_for()`
- `retry.py` — `parse_or_retry()` — one retry with stricter format hint on Pydantic validation failure
- `schemas/` — `MomDraftSchema` (with `to_draft_text()`), `BriefSchema` (with `to_brief_text()`), `ActionItemSchema`
- `__init__.py` — `generate_mom_draft()`, `generate_brief()` — full orchestration (snippets → LLM → tracking → error handling)

**`backend/src/api/sessions.py`** updated:
- `MomOut` + `BriefOut` response schemas now include `llm_call_id`
- `POST /{session_id}/mom/draft` — generates AI draft via `generate_mom_draft()`, upserts MOM row
- `GET /{session_id}/brief` — cache-first (return existing brief), then `generate_brief()` (replaced P3 404 stub)
- `PATCH /{session_id}/mom` — snippet capture gate: fires `snippets.capture()` only when `mom.llm_call_id IS NOT NULL` and `final_text != draft_text`

**`backend/src/api/clients.py`** updated:
- `create_client()` computes `CP<NNNN>` code via `MAX(CAST(SUBSTRING(code FROM 3) AS INTEGER)) + 1` before INSERT

**`backend/src/telemetry/scrub.py`** updated:
- `prompt_text` and `completion_text` added to `_PII_KEYS`

**New tests** (38 added, 1 stale test removed, net +37):
- `test_llm_tracking.py` (4) — `write_llm_call()` happy path, error path, NULL columns on error
- `test_llm_snippets.py` (9) — capture gate (threshold, whitespace, no-llm-call-id), select pool + budget, update_usage
- `test_mom_draft.py` (7) — POST /mom/draft generates draft, re-draft overwrites, PATCH captures snippet, manual MOM PATCH does not
- `test_scrub_extended.py` (4) — `prompt_text`/`completion_text` scrubbed from log output
- `test_llm_service_config.py` (7) — `LLMConfig` loading, `get_llm_config()` singleton, model chain validation
- `test_llm_service_prompts.py` (7) — `load_prompt()` frontmatter parsing, version field extraction, missing-file error
- Removed stale `test_get_brief_returns_404_when_none` (P3 stub, now superseded by P4 generation)

## 3. Decisions made during this phase

**Decision A — Snippet selection algorithm (Option C hybrid)**: Selected over the ADR-0003 default (`last_used_at DESC NULLS FIRST`). Implementation: pull a pool of 25 most-recent snippets by `created_at DESC` (`snippet_pool_size` in `llm_config.yaml`), then re-sort the pool by `last_used_at ASC NULLS FIRST` (unused snippets surface first), then walk in order until the 2K-token budget (`snippet_token_budget`) is exhausted. This gives variety (unused snippets get a turn) while keeping selection deterministic and debuggable. Cross-tenant safety: pool query always filters by `hc_user_id` from JWT.

**Decision B — Amend ADR-0006 §5 to store encrypted prompt and completion**: ADR-0006's original position was "never write prompt or response text into `llm_calls`." During P4 it became clear that debugging LLM output quality without the actual prompt and completion was untenable. SoJo decided to amend: add `prompt_text BYTEA` and `completion_text BYTEA` with three layers of protection: (1) `clients.code` CP\<NNNN\> pseudonym replaces client name/email in prompts, (2) columns encrypted via `pgp_sym_encrypt()` using `LLM_CALL_ENCRYPTION_KEY`, (3) reads are tenant-scoped (only accessible via `hc_user_id` filter). ADR-0006 §5 to be updated formally before P5.

**Fallback encryption key**: `write_llm_call()` uses `LLM_CALL_ENCRYPTION_KEY` from settings, with a hardcoded fallback (`"dev-only-placeholder-not-for-production"`) when the env var is empty. This ensures `pgp_sym_encrypt()` never receives an empty passphrase in dev environments. Production must set a real key — the setting name is explicit about it.

## 4. Bugs fixed mid-phase

**`clients.code NOT NULL` violation on `POST /api/clients`**: Migration `95df31e31f5f` made `clients.code` NOT NULL, but `create_client()` in `clients.py` never assigned it. Every POST to create a client failed with a DB constraint error. Fixed by computing the next code in `create_client()` as `MAX(CAST(SUBSTRING(code FROM 3) AS INTEGER)) + 1` over existing codes for the same HC tenant, then assigning before INSERT. First client for a new HC gets `CP0001`.

**`llm_config.yaml` had 4 models; OpenRouter `models` array limit is 3**: The initial config listed llama-3.3-70b, gemma-3-27b, gpt-oss-120b, and nemotron-3-super-120b-a12b. OpenRouter silently caps the `models` fallback array at 3 entries and ignores the rest. Also, `gpt-oss-120b:free` is not a valid OpenRouter slug. Fixed by removing it; final chain is llama-3.3-70b → gemma-3-27b → nemotron-3-super-120b-a12b.

**httpx timeout too short for free models**: The `make_http_client()` call in `client.py` initially used the library default (5 s). Free-tier models on OpenRouter regularly take 30–60 s. Fixed: `timeout=120.0` passed to `make_http_client()`. Also changed `detail=str(exc)` → `detail=repr(exc)` in error responses — `str()` on some exception types produces an empty string, making 503 responses silent.

## 5. Source docs consulted

- `docs/decisions/0003-llm-strategy.md` — primary: model chain design, snippet strategy, `llm_calls` schema fields, OpenRouter integration pattern
- `docs/decisions/0001-stack-selection.md` §LLM model chain — model slug list and routing policy
- `docs/decisions/0006-observability.md` §5 — original "no prompt/completion in llm_calls" posture; amended during this phase
- `docs/specs/Unit_001_HcCoreCycle/SPEC-0002-llm-service.md` — acceptance criteria, module structure, API endpoint contracts, snippet flow design, `llm_calls` write semantics table
- `docs/diagrams/0002-data-model.md` — `llm_calls`, `hc_style_snippets`, `moms`, `briefs` table schemas
- `prompts/starter_prompt_03.md` — build context, mandatory preparation checklist, known gotchas (OpenRouter model limit, pgcrypto setup)

## 6. Verification

- **Verification date**: 2026-05-04
- **Verification record**: `docs/VERIFICATION.md` § P4
- **Test count at end of phase**: 144 passing (delta from P3: +37)
- **Key checks** (all 15 passed ✅):
  - 144 automated tests pass
  - Both new routes registered (`/mom/draft`, `/brief`)
  - POST `/mom/draft` → `draft_text` populated, `llm_call_id` non-null, `llm_calls` row with all fields
  - `prompt_text` is PGP binary (hex prefix `c30d04...`), not plain text; decrypts correctly; error-path rows store NULL
  - Re-draft overwrites `draft_text`, clears `final_text`, updates `llm_call_id`
  - PATCH with AI draft + diff → `hc_style_snippets` row captured; manual MOM PATCH → no snippet
  - GET `/brief` generates on first call, returns cached brief on second (1 `llm_calls` row total)
  - Second session draft injects snippets (`snippet_count > 0` in `llm_calls`)
  - Wrong HC → 404 (cross-tenant isolation)
  - Prompt version bump reflected in `llm_calls.prompt_version` without code change (one-time structural check)
  - Grep hygiene: no raw `httpx.AsyncClient()` outside `lib/http.py`; model slugs only in `llm_config.yaml`

## 7. Lessons learned

- **pgcrypto BYTEA is opaque until you decrypt it**: Reading `prompt_text` directly from psql shows binary garbage. During verification we had to use `pgp_sym_decrypt(prompt_text, '<key>')` to confirm the column was working. The VERIFICATION.md step 7a captures the exact query. Add a `SELECT pgp_sym_decrypt(...)` line to any future debugging runbook for this table.
- **Verify OpenRouter model slugs and array limits before writing config**: The `models` array limit of 3 is not prominently documented. `gpt-oss-120b:free` appeared in planning docs but is not a valid slug. Validate every slug at [openrouter.ai/models](https://openrouter.ai/models) before committing the config file.
- **Free-tier LLM latency is 30–60 s — size your timeout accordingly**: The 5 s httpx default is fine for paid APIs; it silently kills free-tier calls. `timeout=120.0` gives enough headroom. When adding new LLM endpoints in P5+, set the timeout explicitly on every `make_http_client()` call rather than relying on defaults.
- **`repr(exc)` over `str(exc)` for exception detail fields**: `str()` on several httpx and validation exception types returns an empty string. `repr()` always includes the class name and args. Use `repr(exc)` in `detail=` fields for any 4xx/5xx response that wraps a library exception.
- **The fallback encryption key prevents a silent pgcrypto failure**: `pgp_sym_encrypt()` raises an error on an empty passphrase. Without the fallback key, any developer running without `LLM_CALL_ENCRYPTION_KEY` in `.env` gets a 500 on every LLM call. The fallback makes dev work without the key; the explicit name makes it impossible to accidentally ship the fallback to production.

## 8. Carry-over to subsequent phases

- `backend/src/llm_service/__init__.py` — `generate_mom_draft()` and `generate_brief()` are the LLM integration points P5 calls; do not bypass them for new use cases
- `backend/src/llm_service/snippets.py` — snippet library is ready for P5 injection into the action-item extraction prompt and any future in-session assist calls
- `backend/prompts/ai_assist.md` — prompt file created in P4; endpoint to be wired in P5
- `backend/src/llm_service/llm_config.yaml` — all model chain changes, snippet settings, and retry counts go here; no Python code changes needed for tuning
- Convention: every new LLM use case gets its own `use_case` string in `write_llm_call()` and its own prompt file; the tracking and prompt loader patterns established here apply unchanged
- Convention: pgcrypto BYTEA pattern (`pgp_sym_encrypt` on write, `pgp_sym_decrypt` for debugging) is the template for any future sensitive column additions
- Convention: `clients.code` CP\<NNNN\> pseudonym is injected into prompts in place of client PII; P5 prompt files must follow this same substitution pattern
