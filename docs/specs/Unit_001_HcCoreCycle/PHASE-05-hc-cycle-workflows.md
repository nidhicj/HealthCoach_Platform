# PHASE-05: HC Cycle Workflows + Client File Library

**Unit**: Unit_001_HcCoreCycle
**Status**: Draft
**Verification date**: TBD — see `docs/VERIFICATION.md` § P5 Part A and § P5 Part B
**Implements**: `SPEC-0001-hc-core-cycle.md` §Stage 2 (M000 session), §Stage 3 (between sessions), §Stage 4 (M00N session), §Stage 5 (triage flags), §Stage 6 (coach-reviewed gate) — Part A; §Stage 1 (file uploads as session context) — Part B
**ADRs implemented**: ADR-0001 (S3 Mumbai for storage), ADR-0003 (LLM strategy — snippet capture exclusion, prompt assembly), ADR-0005 (auth — tenant scoping for all new endpoints), ADR-0006 (observability — PII redaction continues for all new prompt content)

---

## 1. Scope

P5 completes the HC Core Cycle product loop. **Part A** adds persistent `session_notes` (the textarea the HC types into during/after a session), extends the pre-session brief to include the full AST (open action items, status summary, trend tags) plus triage flags (missed items, no check-in >14 days, manual sentiment flags), builds the M000 first-session edge case (template prep view — no LLM, no prior data), adds a standalone `GET /clients/{id}/ast` endpoint, and wires the action item `missed` state into the triage computation. **Part B** adds the Client File Library: per-session file uploads to AWS S3 Mumbai, file metadata in a new `client_files` table, `session_notes.txt` mirroring to S3, file content injection into MOM and brief prompt assembly, and Zoom-summary file tagging to exclude those files from HC style-snippet learning.

Both parts ship in this phase and share this PHASE file. They have independent verification gates: SoJo verifies Part A completely before Part B implementation begins.

Not in scope: auto-flagging missed items on `due_date` (deferred to P7), sentiment auto-detection (deferred per ADR-0003), frontend UI (P6), async S3 cleanup sweep job (deferred to P7 — synchronous cleanup at MVP), embedding-based snippet retrieval (deferred per ADR-0003).

---

## 2. Deliverables shipped

### Part A — HC Cycle Workflows

#### A1. Migration: `sessions.session_notes`

File: `backend/alembic/versions/<hash>_add_session_notes.py`

- `ALTER TABLE sessions ADD COLUMN session_notes TEXT` (nullable, no default)
- Separate migration from Part B's `client_files` migration per CLAUDE.md §9

#### A2. ORM model update

File: `backend/src/db/models/sessions.py`
- Add `session_notes: Mapped[str | None] = mapped_column(Text)`

#### A3. `PATCH /sessions/{session_id}` — new endpoint

File: `backend/src/api/sessions.py`

New `SessionPatch` schema:
- `session_notes: str | None = None`

Endpoint behaviour:
- Accepts `SessionPatch` body; sets `session.session_notes` when provided
- Tenant-scoped: `session.hc_user_id == UUID(hc_id)`; otherwise 404
- Returns `SessionOut` (which is extended per A4 below)
- Part B will extend this endpoint to also write `session_notes.txt` to S3

#### A4. `SessionOut` extended

File: `backend/src/api/sessions.py`
- Add `session_notes: str | None` field to `SessionOut`
- `GET /sessions/{id}` returns `session_notes` via this schema (no separate endpoint needed)

#### A5. `POST /sessions/{session_id}/mom/draft` extended

File: `backend/src/api/sessions.py` (`draft_mom` function)
- Before calling `generate_mom_draft()`, persist `body.session_notes` to `sessions.session_notes`:
  ```
  sess.session_notes = body.session_notes
  await db.flush()
  ```
- This makes `session_notes` durable before the LLM call (protects against timeout loss)
- Re-draft path: each call to `POST /mom/draft` overwrites `session_notes` with the latest input, then overwrites `moms.draft_text` with the new draft

#### A6. `GET /clients/{client_id}/ast` — new endpoint

File: `backend/src/api/clients.py`

New response schema `AstOut`:
```python
class AstOut(BaseModel):
    open_items: list[ActionItemOut]
    missed_items: list[ActionItemOut]
    status_summary: str          # narrative text built from recent check-ins
    trend_tags: list[str]        # empty list at MVP (auto-tagging deferred)
    triage_flags: list[str]      # computed: missed items, no check-in, sentiment
```

Computation (at request time, not cached):
- `open_items`: `ActionItem.status == 'open'` AND `ActionItem.client_id == client_id` AND `ActionItem.hc_user_id == hc_id` (tenant check)
- `missed_items`: `ActionItem.status == 'missed'` for same client
- `status_summary`: narrative assembled from recent check-ins (last 14 days), or "No recent check-ins." if none
- `triage_flags`:
  - `missed_action_item` if any action item is `status='missed'`
  - `no_recent_checkin` if zero check-ins in last 14 days
  - `manual_sentiment_flag` if any `check_ins.sentiment_flag IS NOT NULL` in last 30 days
- `trend_tags`: `[]` (deferred)
- Cross-tenant: 404 if `client.hc_user_id != UUID(hc_id)`

#### A7. `generate_brief()` extended — M000 detection + full AST

File: `backend/src/llm_service/__init__.py`

**M000 path** (`session.session_number == 0`):
- Skip LLM entirely; no `llm_calls` row written for this case
- Return a template prep view (static string); triage_flags = []
- Template content:
  ```
  M000 PREPARATION BRIEF — {client_code}

  CLIENT CONTEXT:
  Goal: {client.course_goal or "Not yet set"}
  Course start: {client.course_start_date or "TBD"}
  Notes: {client.metadata.get('intake_notes', 'None provided') if client.metadata else 'None provided'}

  FIRST SESSION CHECKLIST:
  - Establish rapport and mutual expectations
  - Clarify health goal and success criteria
  - Assess current baseline (diet, activity, sleep, stress)
  - Identify top 3 constraints (time, budget, medical, cultural)
  - Agree on check-in cadence and preferred channels
  - Set 1–2 action items for the coming week
  - Confirm next session date
  ```
- `briefs` row is still created (so the endpoint is idempotent), but `llm_call_id = None`

**M00N path** (all other sessions):
- Load client code (existing pattern)
- Load previous MOM: most recent `moms.final_text` for this client (excluding current session)
- Load AST:
  - Open action items: `ActionItem.status == 'open'` for this client (limit 10)
  - Missed items: `ActionItem.status == 'missed'` for this client (limit 10)
- Triage computation:
  - `CHECKIN_TRIAGE_DAYS = 14` (constant)
  - `SENTIMENT_LOOKBACK_DAYS = 30` (constant)
  - Recent check-ins (last 14 days): `check_ins.created_at >= NOW() - 14 days`
  - Triage flags assembled from missed items, no-check-in, sentiment flag presence
- Load snippets (existing pattern)
- Assemble prompt with `{{AST_SECTION}}` and `{{TRIAGE_SECTION}}` placeholders (updated prompt file)
- Return `(brief_text, triage_flags, llm_call_id)`

#### A8. `brief_assemble.md` prompt updated

File: `backend/prompts/brief_assemble.md`
- Version bump: `1.0.0` → `1.1.0`
- Add `{{AST_SECTION}}` placeholder: formatted list of open + missed action items
- Add `{{TRIAGE_SECTION}}` placeholder: formatted triage flags or "No triage flags."
- `{{RECENT_CHECK_INS}}` placeholder remains (now sourced from last 14 days)

#### A9. Diagram update (housekeeping)

File: `docs/diagrams/0002-data-model.md`
- Add `sessions.session_notes TEXT` to sessions table
- Add `clients.code VARCHAR NOT NULL UNIQUE` to clients table (P4 delta, not yet in diagram)
- Add `llm_calls.prompt_text BYTEA` and `llm_calls.completion_text BYTEA` to llm_calls table (P4 delta)
- Update changelog entry

#### A10. Integration tests (Part A)

New test files (target: ~21 new tests):
- `backend/tests/test_session_notes.py` (~6 tests):
  - PATCH saves `session_notes`; GET returns it
  - `POST /mom/draft` persists `session_notes` to DB before LLM call (verify via GET)
  - Re-draft: second POST with different `session_notes` overwrites DB value and produces new `llm_calls` row
  - Cross-tenant PATCH → 404
- `backend/tests/test_ast_endpoint.py` (~5 tests):
  - Empty AST (no items, no check-ins) returns correct structure
  - Open items appear in AST
  - Missed item → `missed_action_item` in `triage_flags`
  - No check-in in 14 days → `no_recent_checkin` in `triage_flags`
  - Cross-tenant → 404
- `backend/tests/test_brief_extended.py` (~7 tests):
  - M000 session → brief returns template view, no `llm_calls` row written
  - M00N brief includes open action items in `brief_text`
  - M00N brief includes missed item → `triage_flags` non-empty
  - M00N brief: check-in within 14 days → no `no_recent_checkin` flag
  - Brief is idempotent (second GET returns same brief, no second `llm_calls` row)
  - Cross-tenant → 404
  - Client with role=client cannot GET brief → 403 (coach-reviewed gate)
- `backend/tests/test_mom_workflow.py` (~3 tests — extending existing test file if it exists):
  - Re-draft path: two consecutive `POST /mom/draft` calls with different `session_notes` → two `llm_calls` rows with different encrypted `prompt_text`
  - Re-draft overwrites `draft_text`, clears `final_text`
  - Manual MOM (no `llm_call_id`) PATCH → still no snippet captured

---

### Part B — Client File Library

#### B1. S3 credentials in config

File: `backend/src/config.py`
- Add `aws_access_key_id: str = ""`
- Add `aws_secret_access_key: str = ""`
- Add `aws_s3_bucket_name: str = ""`
- Add `aws_region: str = "ap-south-1"`

File: `.env.example`
- Add the four S3 vars with placeholder values and comments

#### B2. `backend/src/lib/s3.py` — AWS Sig V4 client (new)

Uses Python stdlib only (`hmac`, `hashlib`, `datetime`, `urllib.parse`) + `make_http_client()` for HTTP transport. No boto3.

Key functions:
```python
def build_session_file_key(
    hc_user_id: UUID, client_code: str, client_full_name: str,
    session_date: date, session_number: int, filename: str
) -> str:
    # Returns: hc-{hc_user_id}/client_session_library/{CP####}_{sanitized_name}/{YYYY-MM-DD}_session-{NN:02d}/{sanitized_filename}
    ...

def _sanitize(s: str, max_len: int = 40) -> str:
    return re.sub(r'[^A-Za-z0-9_.\-]', '_', s)[:max_len]

def _get_session_date_ist(scheduled_at: datetime) -> date:
    return scheduled_at.astimezone(ZoneInfo("Asia/Kolkata")).date()

async def s3_put(key: str, content: bytes, content_type: str) -> None:
    # Signs PUT request with AWS Sig V4 and uploads
    ...

async def s3_delete(key: str) -> None:
    # Signs DELETE request with AWS Sig V4
    ...

async def s3_exists(key: str) -> bool:
    # Signs HEAD request, returns True if 200 else False
    ...
```

Sig V4 signing:
1. Canonical request: HTTP method, URI, sorted query string, signed headers (host, x-amz-content-sha256, x-amz-date), payload hash
2. String to sign: `AWS4-HMAC-SHA256 + newline + timestamp + newline + scope + newline + hex(sha256(canonical_request))`
3. Signing key: HMAC-SHA256 chain using secret key, date, region, service, `aws4_request`
4. Authorization header: `AWS4-HMAC-SHA256 Credential=.../..., SignedHeaders=..., Signature=...`

#### B3. Migration: `client_files` table

File: `backend/alembic/versions/<hash>_add_client_files.py`

```sql
CREATE TABLE client_files (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    hc_user_id       UUID NOT NULL REFERENCES users(id),
    client_id        UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    storage_path     TEXT NOT NULL,
    mime_type        TEXT NOT NULL,
    size_bytes       BIGINT NOT NULL,
    uploaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_zoom_summary  BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_client_files_session ON client_files (session_id);
CREATE INDEX idx_client_files_hc      ON client_files (hc_user_id);
CREATE INDEX idx_client_files_client  ON client_files (client_id);
```

Separate migration from Part A's `sessions.session_notes` per CLAUDE.md §9.

#### B4. `ClientFile` ORM model

File: `backend/src/db/models/files.py` (new file)

```python
class ClientFile(Base):
    __tablename__ = "client_files"
    id: Mapped[UUID] = ...
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    hc_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    is_zoom_summary: Mapped[bool] = mapped_column(Boolean, server_default="false")
```

Register in `backend/src/db/models/__init__.py`.

#### B5. `backend/src/api/files.py` — file CRUD router (new)

Accepted MIME types (constant at top of file):
```python
ALLOWED_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
```

Zoom auto-detection: filename starts with `zoom_ai_summary_` → `is_zoom_summary=True`

**`POST /sessions/{session_id}/files`** (multipart):
- Accepts `files: list[UploadFile]` + optional `is_zoom_summary: bool = False` form field
- For each file:
  - Validate MIME type; raise 400 if not in allowlist
  - Read content; validate size; raise 400 if over limit
  - Auto-detect Zoom summary from filename
  - Build S3 key via `build_session_file_key(...)`
  - Upload to S3 via `s3_put()`
  - Create `ClientFile` row in DB
- Returns list of `ClientFileOut` (id, session_id, original_filename, storage_path, mime_type, size_bytes, uploaded_at, is_zoom_summary)
- Tenant-scoped: session must belong to `hc_id`; otherwise 404

**`GET /sessions/{session_id}/files`**:
- Returns list of `ClientFileOut` for the session
- Tenant-scoped; cross-tenant → 404

**`DELETE /sessions/{session_id}/files/{file_id}`**:
- Queries `ClientFile` by id; validates `hc_user_id == UUID(hc_id)` and `session_id` matches
- Deletes S3 object via `s3_delete(file.storage_path)`
- Deletes DB row
- Idempotent: if file_id not found, returns 404 (not 500)
- If S3 delete fails, logs error but still deletes DB row (S3 orphan is recoverable; DB orphan is not)

Register router in `backend/src/main.py`.

#### B6. `PATCH /sessions/{session_id}` extended (from Part A)

File: `backend/src/api/sessions.py` (`patch_session` function)
- After saving `session_notes` to DB, also mirror to S3:
  ```python
  if body.session_notes is not None and sess.session_notes is not None:
      key = build_session_file_key(
          hc_user_id=UUID(hc_id),
          client_code=client.code,
          client_full_name=client.full_name,
          session_date=_get_session_date_ist(sess.scheduled_at),
          session_number=sess.session_number,
          filename="session_notes.txt",
      )
      await s3_put(key, sess.session_notes.encode("utf-8"), "text/plain")
  ```
- Overwrite is the correct behaviour (every save, not just first)
- S3 write failure: log warning but do NOT fail the request (DB is canonical; S3 is a mirror)

#### B7. `backend/src/lib/file_extraction.py` — text extraction (new)

```python
async def extract_text(content: bytes, mime_type: str) -> str:
    if mime_type in ("text/plain", "text/markdown"):
        return content.decode("utf-8", errors="replace")
    elif mime_type == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        doc = Document(BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""
```

Libraries:
- `pypdf` ≥ 4.x — pure Python, actively maintained, Pyodide-compatible
- `python-docx` — check Pyodide compat at runtime; if it fails on Workers, route docx extraction to DO Bangalore via a flag or return empty string with a warning log

Add to `backend/pyproject.toml` dependencies.

#### B8. `llm_config.yaml` extended

File: `backend/src/llm_service/llm_config.yaml`
- Add `file_content_max_tokens_per_file: 5000`
- Add `file_content_max_total_tokens: 15000`

#### B9. `LLMConfig` dataclass extended

File: `backend/src/llm_service/config.py`
- Add `file_content_max_tokens_per_file: int = 5000`
- Add `file_content_max_total_tokens: int = 15000`

#### B10. `generate_mom_draft()` and `generate_brief()` extended

File: `backend/src/llm_service/__init__.py`

New helper:
```python
async def _assemble_file_content_section(
    db: AsyncSession,
    session_id: UUID,
    config: LLMConfig,
) -> tuple[str, bool]:
    """Returns (formatted_file_section, zoom_sources_present)."""
    files = (await db.execute(
        select(ClientFile).where(ClientFile.session_id == session_id)
    )).scalars().all()
    
    if not files:
        return "", False
    
    zoom_present = any(f.is_zoom_summary for f in files)
    total_tokens_used = 0
    sections = []
    
    for f in files:
        # Fetch content from S3 via s3_head/get (or store content in DB as an option)
        # Decision: fetch from S3 on demand at prompt assembly time
        content = await s3_get(f.storage_path)  # new s3_get function
        text = await extract_text(content, f.mime_type)
        
        # Token budget per file (estimate: 4 chars ≈ 1 token)
        token_estimate = len(text) // 4
        if token_estimate > config.file_content_max_tokens_per_file:
            char_limit = config.file_content_max_tokens_per_file * 4
            text = text[:char_limit] + "\n[... truncated, file too long ...]"
        
        remaining_budget = (config.file_content_max_total_tokens - total_tokens_used) * 4
        if len(text) > remaining_budget:
            text = text[:remaining_budget] + "\n[... total file budget exceeded ...]"
        
        total_tokens_used += len(text) // 4
        sections.append(f"### {f.original_filename}\n{text}")
    
    file_section = "## Uploaded files:\n" + "\n\n".join(sections)
    return file_section, zoom_present
```

Extended `user_message` assembly:
```python
notes_section = f"## HC's typed notes:\n{session_notes or '(no notes entered)'}"
file_section, zoom_present = await _assemble_file_content_section(db, session_id, cfg)
user_message = notes_section + ("\n\n" + file_section if file_section else "")
```

Also add `s3_get()` to `backend/src/lib/s3.py`:
```python
async def s3_get(key: str) -> bytes:
    # Signs GET request with AWS Sig V4 and returns response body bytes
    ...
```

**Snippet capture exclusion** (`backend/src/api/sessions.py`, `patch_mom` function):
- Before calling `snippets.capture()`, check if any file for this session has `is_zoom_summary=True`:
  ```python
  zoom_file_exists = (await db.execute(
      select(ClientFile.id)
      .where(ClientFile.session_id == session_id, ClientFile.is_zoom_summary == True)
      .limit(1)
  )).scalar_one_or_none()
  if mom.llm_call_id is not None and body.final_text != mom.draft_text and not zoom_file_exists:
      await capture(...)
  ```

#### B11. `domain/glossary.md` additions

- **`session_notes`** — HC's typed observations during/after a session; persisted to `sessions.session_notes` column; feeds LLM prompts; mirrored read-only to S3 as `session_notes.txt`; DB column is canonical
- **`session_notes.txt` (S3 mirror)** — read-only copy of `session_notes`, written to S3 on every PATCH to `sessions.session_notes`; HC may view it for reference; if edited on disk, the next platform save overwrites; never read back by the system
- **`client_files`** — per-session uploaded files (Zoom AI summaries, PDFs, handwritten notes); metadata in `client_files` table; file content in AWS S3 Mumbai at the documented path pattern
- **`is_zoom_summary` flag** — marks a file as originating from Zoom AI Companion; such files' content reaches the LLM for context but does not contribute to HC style snippets

#### B12. Integration tests (Part B)

Target: ~20 new tests

- `backend/tests/test_s3_client.py` (~4 tests):
  - `s3_put()` produces correctly signed Authorization header (mock httpx, inspect headers)
  - `s3_delete()` correct signing
  - `build_session_file_key()` correct path structure (unit test — no HTTP)
  - Sanitization: name with spaces/special chars → correct output

- `backend/tests/test_file_upload.py` (~6 tests):
  - Upload 1 file → `client_files` row created; `GET /sessions/{id}/files` returns it
  - Multi-file upload → all rows created
  - File over 25 MB → 400
  - Invalid MIME type → 400
  - Cross-tenant upload → 404
  - `DELETE /sessions/{id}/files/{file_id}` → row deleted; idempotent second call → 404

- `backend/tests/test_session_notes_mirror.py` (~3 tests):
  - PATCH `session_notes` → mock s3_put called with correct key and content
  - Second PATCH → s3_put called again (overwrite)
  - S3 failure → PATCH still returns 200 (S3 is non-blocking mirror)

- `backend/tests/test_file_prompt_injection.py` (~4 tests):
  - Mock file content in DB; generate MOM draft → `llm_calls.prompt_text` (decrypted) contains `## HC's typed notes:` and `## Uploaded files:` sections
  - Token truncation: file > `file_content_max_tokens_per_file` → truncated with `[... truncated...]`
  - Total budget: multiple files exceeding `file_content_max_total_tokens` → last file(s) truncated

- `backend/tests/test_zoom_snippet_exclusion.py` (~2 tests):
  - Session with Zoom-tagged file → generate draft → PATCH mom with edit → no `hc_style_snippets` row created
  - Session with non-Zoom file → same flow → snippet IS captured

- `backend/tests/test_client_cascade_s3.py` (~1 test):
  - Create client, upload 2 files (mock S3), delete client → `client_files` rows gone (DB cascade); `s3_delete` called for each file

---

## 3. Decisions made during this phase

**Decision A — M000 detection via `session_number == 0`**: SPEC-0001 §Stage 2 references `is_first_session=true` but no such column exists in the schema or ORM model. The live convention uses `session_number = 0` for M000. The M000 brief skips the LLM entirely and returns a static template — no `llm_calls` row written. The `briefs` row is still created (so the endpoint is idempotent on repeat requests).

**Decision B — `session_notes` is a new column distinct from `notes_internal`**: The existing `sessions.notes_internal` field (present since P1) is for HC private admin notes, not fed to the LLM. The new `sessions.session_notes` column is specifically the HC's typed observations that feed MOM draft and brief generation. They are intentionally separate: HCs may use `notes_internal` for administrative context and `session_notes` for AI-input content.

**Decision C — S3 operations via httpx + AWS Signature V4 (no boto3)**: boto3 and aioboto3 rely on threading and are not Pyodide-compatible. All S3 operations (PUT, GET, DELETE, HEAD) are performed using `make_http_client()` with AWS Signature V4 signing implemented in pure Python stdlib (`hmac`, `hashlib`, `datetime`, `urllib.parse`). This keeps all file-related endpoints Pyodide-compatible on Cloudflare Workers. No DO Bangalore routing is needed for S3 in this phase.

**Decision D — Per-HC S3 prefix (not per-HC bucket)**: Single bucket (`S3_BUCKET_NAME` env var); tenant isolation via path prefix `hc-{hc_user_id}/`. Per-bucket would require dynamic bucket provisioning (complex for 1–2 HCs at MVP). Prefix isolation is enforced by `build_session_file_key()`; cross-HC access is prevented at the API layer per ADR-0005.

**Decision E — Snippet capture exclusion: session-level Zoom suppression**: When ANY file in the session has `is_zoom_summary=True`, snippet capture for all drafts from that session is suppressed. The conservative approach: the Zoom AI's voice is definitively excluded from style learning. A more nuanced diff-based approach (suppress only if the edit overlaps Zoom content) is deferred. This is documented as a known limitation.

**Decision F — S3 cascade delete is synchronous at MVP**: On client deletion/consent revocation, S3 objects are deleted synchronously (query all `client_files` → delete each S3 object → proceed with DB delete/cascade). At MVP file counts (tens of files per client), latency is acceptable. An async sweep job for orphaned S3 objects is deferred to P7 and documented as a TODO in this file.

**Decision G — File content fetched from S3 at prompt-assembly time**: File content is not stored in the DB. At prompt-assembly time, `generate_mom_draft()` and `generate_brief()` fetch each file's bytes from S3 via a new `s3_get()` function. This adds network latency per file but keeps the DB free of large binary content. At MVP file counts (2–5 files per session), this is acceptable.

**Decision H — Triage thresholds**: `CHECKIN_TRIAGE_DAYS = 14` (no check-in in >14 days triggers `no_recent_checkin` triage flag), `SENTIMENT_LOOKBACK_DAYS = 30` (manual sentiment flag in last 30 days triggers `manual_sentiment_flag`). Both are module-level constants in `llm_service/__init__.py` for easy tuning.

**Decision I — `python-docx` Pyodide compatibility**: If `python-docx` proves incompatible with Pyodide at runtime, `.docx` extraction returns an empty string and logs a warning. The prompt still includes the section header with the filename but no content. This is acceptable at MVP — most HC uploads are PDFs or plain text. Document as a known limitation and revisit if HC reports are docx-heavy.

---

## 4. Bugs fixed mid-phase

None recorded — phase not yet started.

---

## 5. Source docs consulted

- `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` — HC cycle stages; §Stage 2 (M000), §Stage 4 (M00N), §Stage 5 (triage flag computation rules), §Stage 6 (coach-reviewed gate)
- `docs/domain/glossary.md` — term definitions for MOM, AST, action item, snippet, check-in; additions needed per §B11
- `docs/domain/actors.md` — coach-reviewed gate; who reads `briefs` (HC only); tenant scoping
- `docs/decisions/0003-llm-strategy.md` — `llm_calls` schema, snippet capture exclusion, retention rules; §4 and §7 amendments 2026-05-04
- `docs/decisions/0006-observability.md` — PII redaction (prompt/completion encryption continues); §5 amendment 2026-05-04
- `docs/decisions/0001-stack-selection.md` — S3 Mumbai (ap-south-1) for object storage
- `docs/decisions/0005-auth-strategy.md` — tenant scoping pattern (`hc_id` from JWT) applied to all new endpoints; cross-tenant → 404
- `docs/specs/Unit_001_HcCoreCycle/PHASE-04-llm-service.md` — P4 carry-over: `generate_mom_draft()` / `generate_brief()` interfaces, `make_http_client()` pattern, `write_llm_call()` pattern, `clients.code` pseudonym substitution in prompts
- `docs/diagrams/0002-data-model.md` — schema reference; note: diagram predates P3/P4 additions (stale — use migration files as authoritative)

---

## 6. Verification

- **Verification date**: TBD — Phase in progress
- **Verification record**: `docs/VERIFICATION.md` § P5 Part A and § P5 Part B (to be added before implementation completes)
- **Test count at end of phase**: target ~185+ (144 at P4 end; Part A target +21, Part B target +20)
- **Key checks (Part A)**:
  - [ ] `sessions.session_notes` column exists after running migrations
  - [ ] PATCH `sessions/{id}` with `session_notes` → persists; GET returns it
  - [ ] `POST /mom/draft` persists `session_notes` to DB before generating
  - [ ] Re-draft: second `POST /mom/draft` with changed notes → second `llm_calls` row with different encrypted `prompt_text`
  - [ ] `GET /clients/{id}/ast` returns structured response with open items and triage flags
  - [ ] Missed action item → `missed_action_item` in AST triage flags
  - [ ] M000 session (session_number=0) → brief endpoint returns template view; no `llm_calls` row written
  - [ ] M00N brief includes AST items and triage flags in `brief_text`
  - [ ] Client-role JWT cannot GET brief → 403
  - [ ] HC2 cannot GET HC1's AST, sessions, or briefs → 404
  - [ ] All tests passing (~165+)
- **Key checks (Part B)**:
  - [ ] `client_files` table exists after running Part B migration
  - [ ] Upload 1+ files → `client_files` rows + S3 objects created at documented path
  - [ ] PATCH `session_notes` → `session_notes.txt` appears in S3 at correct path
  - [ ] Second PATCH → `session_notes.txt` overwritten with new content
  - [ ] MOM draft generated after file upload → `llm_calls.prompt_text` (decrypted via psql) contains `## HC's typed notes:` and `## Uploaded files:` sections
  - [ ] Upload Zoom-tagged file → generate draft → PATCH mom with edit → no `hc_style_snippets` row created
  - [ ] Upload non-Zoom file → same flow → snippet IS captured
  - [ ] DELETE file → S3 object gone + `client_files` row gone
  - [ ] Delete client → all `client_files` rows gone (DB cascade) + S3 delete called for each file
  - [ ] File over 25 MB → 400; wrong MIME type → 400
  - [ ] HC2 cannot list/upload/delete HC1's files → 404
  - [ ] All tests passing (~185+)

---

## 7. Lessons learned

Phase in progress — to be recorded on completion. Will include observations on AWS Sig V4 signing complexity, pypdf Pyodide compatibility findings, and any triage flag edge cases discovered during testing.

---

## 8. Carry-over to subsequent phases

- `backend/src/lib/s3.py` — S3 Sig V4 client; P6 frontend will need presigned read URLs for file display; add `s3_presign_get()` to this module in P6
- `backend/src/api/files.py` — file CRUD; P6 frontend integrates upload/list/delete into session UI
- `backend/src/lib/file_extraction.py` — text extraction; reusable for future document types (audio transcripts, etc.)
- `backend/src/llm_service/__init__.py` — `generate_mom_draft()` and `generate_brief()` now accept file context via `_assemble_file_content_section()`; all future LLM generation follows this assembly pattern
- `backend/src/db/models/files.py` — `ClientFile` model; P9 consent-revocation smoke test must verify S3 cleanup
- Convention: `build_session_file_key()` is the single source of truth for S3 paths; never construct paths ad-hoc elsewhere
- Convention: `session_notes.txt` is always a mirror, never a source of truth; never read back from S3 by the system
- Convention: Zoom-tagged files suppress snippet capture at the session level; this granularity is intentional and documented in glossary
- Convention: S3 cascade delete must be coded explicitly in every client-deletion path (DB cascade removes `client_files` rows; S3 deletion is application code responsibility)
- TODO (deferred to P7): async S3 cleanup sweep for orphaned objects (objects in S3 whose `client_files` DB row is missing, e.g., due to failed upload cleanup)
- TODO (deferred to P7): auto-flagging of missed action items when `due_date < NOW()` — currently requires manual transition to `status='missed'`
