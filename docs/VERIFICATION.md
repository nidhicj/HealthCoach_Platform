# Verification Checkpoints

Append-only. Each phase ends with a manual checkpoint. Mark items ✅ when confirmed, ❌ if failed (and note the fix).

---

## P4 — LLM Service

**Status**: verified 2026-05-04

### Prerequisites

`.env` must have both keys set before any LLM-dependent step:

```bash
OPENROUTER_API_KEY=<your key from openrouter.ai>
LLM_CALL_ENCRYPTION_KEY=<run: openssl rand -base64 32>
```

### 1. Automated suite

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest -v
# Expected: 144 passed
```

- [X] 144 tests pass

### 2. New routes registered

```bash
cd backend
PYTHONPATH=. .venv/bin/python3 -c "
from src.main import app
p4 = [r.path for r in app.routes if 'draft' in r.path or 'brief' in r.path]
for p in sorted(set(p4)): print(p)
"
```

Expected output includes:
`/api/sessions/{session_id}/brief`
`/api/sessions/{session_id}/mom/draft`

- [X] Both routes present

### 3. Server startup

```bash
cd backend
.venv/bin/uvicorn src.main:app --reload --port 8000 --env-file ../.env
```

- [X] Server starts without import errors

### 4. Setup — HC user, client, session

Run the printed export commands after each step.

```bash
# HC user (reuse from P3 if still in DB)
PYTHONPATH=. .venv/bin/python3 scripts/create_hc_user.py
# run: export HC_JWT=... and export HC_ID=...

# Create client
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"full_name": "Priya Sharma"}' | python3 -m json.tool
export CLIENT_ID=<id>

# Create session
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":1,\"scheduled_at\":\"2026-06-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION_ID=<id>
```

- [X] Client created with `code` field set (e.g. `"CP0001"`)
- [X] Session created (201)

### 5. POST /mom/draft — AI draft generation

```bash
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Client discussed hydration goals. Committed to 2.5L daily. Sleep improved from 10pm to 9:30pm."}' \
  | python3 -m json.tool
```

Expected:

- `status = "draft"`
- `draft_text` contains structured MOM text (SUMMARY, ACTION ITEMS, etc.) — not empty JSON
- `llm_call_id` is a UUID (not null)

```bash
export MOM_LLM_CALL_ID=<llm_call_id from response>
```

- [X] `status = "draft"`
- [X] `draft_text` is human-readable structured text
- [X] `llm_call_id` is not null

### 6. Verify `llm_calls` row

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT use_case, model_requested, model_served, fallback_count,
       input_tokens, output_tokens, latency_ms, validation_failed,
       prompt_version, snippet_count
FROM llm_calls WHERE id = '$MOM_LLM_CALL_ID';
"
```

Expected:

- `use_case = 'mom_generation'`
- `model_requested = 'meta-llama/llama-3.3-70b-instruct:free'`
- `model_served` is a non-null slug
- `validation_failed = false`
- `input_tokens > 0`, `output_tokens > 0`, `latency_ms > 0`
- `prompt_version = '1.0.0'`

- [X] `use_case = 'mom_generation'`
- [X] `model_served` non-null
- [X] `validation_failed = false`
- [X] Token counts and latency populated

### 7. Verify `prompt_text` is encrypted (not plain text)

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT length(prompt_text), left(encode(prompt_text, 'hex'), 8) AS hex_prefix
FROM llm_calls WHERE id = '$MOM_LLM_CALL_ID';
"
# hex_prefix should start with 'c30d04' (OpenPGP binary format magic bytes)
# NOT '596f7520' ('You ' in hex — the plaintext start of the system prompt)
```

- [X] `prompt_text` is binary (PGP prefix `c30d04...`) — not plain text

### 7a. Verify `prompt_text` and `completion_text` decrypt correctly

```bash
# Load the encryption key from .env (source it or substitute inline)
source ../.env   # sets $LLM_CALL_ENCRYPTION_KEY in current shell

psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT
  pgp_sym_decrypt(prompt_text, '$LLM_CALL_ENCRYPTION_KEY') AS decrypted_prompt,
  pgp_sym_decrypt(completion_text, '$LLM_CALL_ENCRYPTION_KEY') AS decrypted_completion
FROM llm_calls WHERE id = '$MOM_LLM_CALL_ID';
"
```

Expected:

- `decrypted_prompt` is readable plain text starting with `"You are an expert health coach assistant..."`
- `decrypted_completion` is the raw JSON string the LLM returned (should start with `{` and contain keys like `"summary"`, `"key_discussion_points"`, etc.)

Then verify that error-path rows (where no LLM response arrived) store NULL — not encrypted empty string:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT id, model_served,
  (prompt_text IS NULL) AS prompt_null,
  (completion_text IS NULL) AS completion_null
FROM llm_calls WHERE model_served IS NULL LIMIT 3;
"
# Expected: prompt_null = t, completion_null = t for rows where the HTTP call failed
# (success rows have model_served NOT NULL and both columns non-null)
```

- [X] `decrypted_prompt` starts with `"You are an expert health coach assistant"`
- [X] `decrypted_completion` is valid JSON with MOM keys
- [X] Error-path rows (model_served IS NULL) have NULL for both encrypted columns — skip if 0 rows (means all calls in dev DB succeeded; the 503 path was verified live during P4)

### 8. Re-draft overwrites MOM (idempotent)

```bash
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Second take — client also mentioned meal prep challenges."}' \
  | python3 -m json.tool
```

Expected: same session_id, new `llm_call_id`, `final_text = null`, `draft_text` reflects second call.

- [X] Re-draft succeeds (200, not 409)
- [X] `llm_call_id` changed to new value
- [X] `final_text` is null

### 9. PATCH /mom with AI draft → snippet captured

```bash
curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"final_text": "Priya CP0001 made excellent progress. She committed to drinking 2.5L of water daily using a tracking bottle. Sleep moved from 10pm to 9:30pm — encourage maintaining this schedule. Next session: review meal prep strategies."}' \
  | python3 -m json.tool
```

Then verify snippet was captured:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT snippet_type, left(hc_modified_text, 60) AS preview, client_id
FROM hc_style_snippets WHERE hc_user_id = '$HC_ID'
ORDER BY created_at DESC LIMIT 5;
"
```

Expected: at least one row with `snippet_type = 'edit'`, `client_id` = `$CLIENT_ID`.

- [X] `hc_style_snippets` row created with `snippet_type = 'edit'`
- [X] `client_id` matches the session's client

### 10. GET /brief — generates and caches

```bash
# First call — generates
curl -s http://localhost:8000/api/sessions/$SESSION_ID/brief \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Second call — must return same brief_text (cached — no second LLM call)
curl -s http://localhost:8000/api/sessions/$SESSION_ID/brief \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
```

Then check only one `llm_calls` row for brief:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT COUNT(*) FROM llm_calls
WHERE use_case = 'brief_generation' AND session_id = '$SESSION_ID';
"
# Expected: 1 (not 2)
```

- [X] Brief returned on first call (200)
- [X] Second call returns identical `brief_text`
- [X] Exactly 1 `llm_calls` row for `brief_generation`

### 11. Snippet injection — second draft includes style examples

Create a second session (so the snippet from step 9 is available) and request a draft. In the server logs, look for `DEBUG` lines mentioning snippets.

```bash
# Create second session
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":2,\"scheduled_at\":\"2026-06-15T10:00:00Z\"}" | python3 -m json.tool
export SESSION2_ID=<id>

curl -s -X POST http://localhost:8000/api/sessions/$SESSION2_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Reviewed meal prep. Client has been consistent with water."}' \
  | python3 -m json.tool
```

Then check `snippet_count > 0` in `llm_calls`:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT snippet_count, snippet_tokens FROM llm_calls
WHERE use_case = 'mom_generation'
ORDER BY created_at DESC LIMIT 1;
"
# Expected: snippet_count >= 1, snippet_tokens > 0
```

- [X] `snippet_count > 0` in llm_calls row for second session draft

### 12. Manual MOM — no snippet on PATCH

```bash
# New session, manual MOM (no AI draft)
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":3,\"scheduled_at\":\"2026-07-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION3_ID=<id>

curl -s -X POST http://localhost:8000/api/sessions/$SESSION3_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"draft_text": "I typed this myself."}' | python3 -m json.tool

count_before=$(psql -t postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  -c "SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';")

curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION3_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"final_text": "I edited this significantly — many new words added here for the review."}' | python3 -m json.tool

count_after=$(psql -t postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  -c "SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';")

echo "Before: $count_before | After: $count_after  (should be equal)"
```

- [X] Snippet count unchanged after patching a manual MOM

### 13. Wrong HC → 404

```bash
PYTHONPATH=. .venv/bin/python3 -c "
import uuid; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
hc2=str(uuid.uuid4())
t=create_access_token(sub=hc2,role='hc',hc_id=hc2,private_key=get_settings().jwt_private_key)
print('export HC2_JWT='+t)"
# run the export, then:
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC2_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "..."}'
# Expected: 404
```

- [X] Wrong HC → 404

### 14. Prompt version bump → reflected in `llm_calls` *(one-time structural check)*

> **Why this exists**: verifies that `llm_calls.prompt_version` is config-driven (YAML frontmatter), not hardcoded. Run once when first verifying P4; re-run only if `src/llm_service/prompts.py` is modified. Skip on routine re-verification.

```bash
# Edit backend/prompts/mom_draft.md — change version: "1.0.0" to "1.0.1"
# Restart uvicorn (Ctrl-C and rerun)
# Make one more POST /mom/draft call
# Then:
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT prompt_version FROM llm_calls WHERE use_case = 'mom_generation'
ORDER BY created_at DESC LIMIT 1;
"

# Expected: 1.0.1
# Revert: change version back to "1.0.0" and restart
```

- [X] Prompt version change visible in `llm_calls.prompt_version` without code change

### 15. Grep hygiene

```bash
cd backend

# No direct AsyncClient outside the factory
grep -r "httpx.AsyncClient(" src/ | grep -v "lib/http.py"
# Expected: no output

# Model slugs only in YAML — not in Python source
grep -rn "llama-3.3\|gemma-3\|nemotron\|gpt-oss" src/ --include="*.py"
# Expected: no output
```

- [X] No raw httpx.AsyncClient usage outside lib/http.py
- [X] Model slugs only in llm_config.yaml

### Summary table

| Check                                                     | Pass | Notes |
| --------------------------------------------------------- | ---- | ----- |
| 144 automated tests pass                                  | ✅   |       |
| `/mom/draft` route registered                           | ✅   |       |
| POST /mom/draft → AI draft_text + llm_call_id            | ✅   |       |
| llm_calls row: all fields populated                       | ✅   |       |
| prompt_text encrypted (PGP binary)                        | ✅   |       |
| prompt/completion decryptable, error rows NULL            | ✅   |       |
| Re-draft overwrites MOM, clears final_text                | ✅   |       |
| PATCH with AI draft → snippet captured                   | ✅   |       |
| GET /brief generates + caches (1 llm_calls row)           | ✅   |       |
| Second session draft injects snippets (snippet_count > 0) | ✅   |       |
| Manual MOM PATCH → no snippet                            | ✅   |       |
| Wrong HC → 404                                           | ✅   |       |
| Prompt version bump visible in llm_calls                  | ✅   |       |
| Grep hygiene (httpx, model slugs)                         | ✅   |       |

---

## P3 — Domain CRUD + Client OAuth ✅

**Status**: verified 2026-05-02

### Setup

```bash
cd backend

# 1. Automated suite (run this first — must be green before manual steps)
uv run pytest -v
# Expected: 107 passed
```

Start the server in a second terminal:

```bash
cd backend
uv run uvicorn src.main:app --reload --port 8000 --env-file ../.env
```

(Uses the root `.env`. See `.env.example` for the required variables.)

### 2. All P3 routes registered

```bash
cd backend
uv run python3 -c "
from src.main import app
p3 = [r.path for r in app.routes if any(x in r.path for x in ['/clients','/sessions','/action-items','/check-ins','/me/','/auth/client'])]
for p in sorted(set(p3)): print(p)
"
```

Expected output includes all of:
`/api/auth/client/callback`, `/api/auth/client/start`, `/api/check-ins/{check_in_id}/flag`, `/api/clients`, `/api/clients/{client_id}`, `/api/clients/{client_id}/check-ins`, `/api/clients/{client_id}/invite`, `/api/action-items`, `/api/action-items/{item_id}`, `/api/me/action-items`, `/api/me/action-items/{item_id}`, `/api/me/check-ins`, `/api/me/moms`, `/api/me/moms/{mom_id}`, `/api/sessions`, `/api/sessions/{session_id}`, `/api/sessions/{session_id}/brief`, `/api/sessions/{session_id}/end`, `/api/sessions/{session_id}/mom`, `/api/sessions/{session_id}/mom/send`

- [X] All routes listed above present

### 3. Create a real HC user in the dev DB and generate a JWT

`clients.hc_user_id` is a FK to `users` — the JWT sub must be a real user row.

```bash
cd backend
python3 scripts/create_hc_user.py
```

Run the printed `export HC_JWT=...` and `export HC_ID=...` commands before steps 4–8.

### 4. HC — create client, list, cross-tenant

```bash
# Create client
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"full_name": "Priya Sharma"}' | python3 -m json.tool
export CLIENT_ID=<id from response>

# List → Priya appears
curl -s http://localhost:8000/api/clients -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool

# Second HC tries to read Priya → 404
uv run python3 -c "
import uuid; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
hc2=str(uuid.uuid4()); t=create_access_token(sub=hc2,role='hc',hc_id=hc2,private_key=get_settings().jwt_private_key)
print('export HC2_JWT='+t)"
# run the export, then:
curl -s http://localhost:8000/api/clients/$CLIENT_ID -H "Authorization: Bearer $HC2_JWT"
# Expected: {"detail":"Client not found"}
```

- [X] Client created → 201 with journey_stage="onboarding"
- [X] Own client in list
- [X] Cross-tenant GET by ID → 404

### 5. Session + MOM lifecycle

```bash
# Create session
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":1,\"scheduled_at\":\"2026-06-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION_ID=<id>

# Create MOM (status should be "draft")
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"draft_text":"Discussed nutrition goals."}' | python3 -m json.tool

# Send MOM
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/send \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
export MOM_ID=<id from send response>
# Expected: status="sent", sent_at not null
```

- [X] Session created → 201
- [X] MOM created → status=draft
- [X] MOM sent → status=sent, sent_at populated

### 6. Action items

```bash
curl -s -X POST http://localhost:8000/api/action-items \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"description\":\"Drink 2L water daily\",\"due_date\":\"2026-06-08\"}" | python3 -m json.tool
# Expected: 201, status="open", due_date="2026-06-08"
export AI_ID=<id>

curl -s -X PATCH http://localhost:8000/api/action-items/$AI_ID \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"status":"completed"}' | python3 -m json.tool
# Expected: status="completed", completed_at not null
```

- [X] Action item created with due_date, default status=open
- [X] Marked completed → completed_at populated

### 7. Invite flow

```bash
curl -s -X POST http://localhost:8000/api/clients/$CLIENT_ID/invite \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: 201 with invite_token, invite_url containing /api/auth/client/start?invite=
export INVITE_TOKEN=<invite_token>

# Valid invite → Google URL
curl -s "http://localhost:8000/api/auth/client/start?invite=$INVITE_TOKEN" | python3 -m json.tool
# Expected: {"auth_url": "https://accounts.google.com/..."}

# Invalid invite → 400
curl -s "http://localhost:8000/api/auth/client/start?invite=totallyfaketoken" | python3 -m json.tool
# Expected: 400
```

- [X] invite_url contains `/api/auth/client/start?invite=`
- [X] Valid invite → 200 with Google auth URL
- [X] Invalid invite → 400

### 8. Client-facing endpoints

```bash
# Generate unlinked client JWT (no client record in DB)
uv run python3 -c "
import uuid,os; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
t=create_access_token(sub=str(uuid.uuid4()),role='client',hc_id=os.environ['HC_ID'],private_key=get_settings().jwt_private_key)
print('export CLIENT_JWT='+t)"
# run the export

curl -s http://localhost:8000/api/me/moms -H "Authorization: Bearer $CLIENT_JWT"
# Expected: 404 {"detail":"Client record not found"}  — not 500, not 200

curl -s http://localhost:8000/api/me/moms -H "Authorization: Bearer $HC_JWT"
# HC token on /api/me route → Expected: 401 or 403 (role=hc not allowed on /api/me/*)
```

- [X] Unlinked client JWT → /api/me/* returns 404 (not 500)
- [X] HC JWT on /api/me/* → 401/403

### 9. Coach-reviewed gate grep

```bash
cd backend
grep -n "status.*sent\|sent.*status" src/api/me.py
# Expected: lines showing WHERE status = "sent" filter in list_my_moms and get_my_mom

grep -rn "mom_text\|final_text\|draft_text" src/api/me.py
# Expected: no output — me.py exposes MomOut schema, doesn't reference raw text field names
```

- [X] status="sent" filter present in me.py for both MOM endpoints
- [X] No raw text field manipulation in me.py

### 10. Pagination with >20 items

```bash
for i in $(seq 1 25); do
  curl -s -X POST http://localhost:8000/api/clients \
    -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
    -d "{\"full_name\":\"Bulk $i\"}" > /dev/null
done

curl -s "http://localhost:8000/api/clients?limit=20" -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: 20 items, next_cursor is not null

curl -s 'http://localhost:8000/api/clients?cursor=notvalidbase64!!!' \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: 400 {"detail": "Invalid cursor"}
```

- [ ]
- [X] Invalid cursor → 400

### 11. Brief stub returns correct message

```bash
curl -s http://localhost:8000/api/sessions/$SESSION_ID/brief \
  -H "Authorization: Bearer $HC_JWT"
# Expected: 404 {"detail":"Brief not found (generation is P5)"}
```

- [X] Brief endpoint → 404 with P5 message

### 12. Grep hygiene

```bash
cd backend
grep -r "httpx.AsyncClient(" src/ | grep -v "lib/http.py"
# Expected: no output

grep -r "\bSession(" src/ | grep -v "AsyncSession\|async_sessionmaker\|class Session"
# Expected: no output (all Session( usages are model instantiation or class definition)
```

- [X] No raw httpx.AsyncClient outside factory
- [X] No sync Session() usage

### Summary table

| Check                           | Pass | Notes |
| ------------------------------- | ---- | ----- |
| 107 automated tests pass        | ✅   |       |
| All routes registered           | ✅   |       |
| Client CRUD + cross-tenant 404  | ✅   |       |
| Session + MOM lifecycle         | ✅   |       |
| Action items + completed_at     | ✅   |       |
| Invite URL + start endpoint     | ✅   |       |
| Unlinked client JWT → 404      | ✅   |       |
| HC JWT on /api/me/* → 401/403  | ✅   |       |
| Coach-reviewed gate grep        | ✅   |       |
| Pagination >20 + invalid cursor | ✅   |       |
| Brief → 404 with P5 message    | ✅   |       |
| Grep hygiene (httpx, Session)   | ✅   |       |

---

## P2 — Auth Service ✅

**Status**: verified 2026-05-01

### Automated (run first)

```bash
cd backend
uv run pytest -v
```

Expected: **37 passed**

### 1. Auth routes registered

```bash
uv run python -c "from src.main import app; print([r.path for r in app.routes])"
```

Expected output includes: `/api/auth/google/start`, `/api/auth/google/callback`, `/api/auth/refresh`, `/api/auth/logout`

### 2. `/api/auth/google/start` returns an auth URL

Start the server:

```bash
DATABASE_URL=postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  uv run uvicorn src.main:app --reload --port 8000
```

Then in another terminal:

```bash
curl -s http://localhost:8000/api/auth/google/start | python3 -m json.tool
```

Expected: `{"auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."}` (even with empty `GOOGLE_CLIENT_ID` — URL is still constructed)

### 3. Protected endpoint returns 401 without token

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz
# Expected: 200

# Any future protected endpoint (P3 onwards) will return:
# curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/clients/
# Expected: 401
```

### 4. JWT decode at jwt.io

Generate a test token:

```bash
cd backend
uv run python3 - <<'EOF'
from src.auth.jwt_utils import create_access_token
import uuid

# Use the test keys from test_jwt_utils.py
PRIV = open("/tmp/test_priv.pem").read()  # regenerate if gone: see Step 1 in plan
token = create_access_token(
    sub=str(uuid.uuid4()), role="hc", hc_id=str(uuid.uuid4()),
    private_key=PRIV,
)
print(token)
EOF
```

Paste into https://jwt.io and confirm payload contains: `sub`, `role`, `hc_id`, `iss: https://api.parivarthan.com`, `aud: parivarthan-api`, `exp`

### 5. Refresh token rotation (DB check)

```bash
cd backend
uv run python3 - <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.auth.refresh import issue_refresh_token, rotate_refresh_token
from src.db.models import User
from src.db.base import Base
import uuid

DB = "postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev"

async def main():
    engine = create_async_engine(DB)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email=f"verify-{uuid.uuid4().hex[:6]}@test.com", google_sub=uuid.uuid4().hex)
        db.add(user)
        await db.flush()
        raw = await issue_refresh_token(db, user.id)
        new_raw, uid = await rotate_refresh_token(db, raw)
        print(f"Rotation OK — user_id: {uid}")
        try:
            await rotate_refresh_token(db, raw)
        except ValueError as e:
            print(f"Old token correctly rejected: {e}")
        await db.rollback()
    await engine.dispose()

asyncio.run(main())
EOF
```

Expected:

```
Rotation OK — user_id: <uuid>
Old token correctly rejected: refresh token replay detected — all sessions revoked
```

### 6. `grep` check — no raw httpx usage outside factory

```bash
grep -r "httpx.AsyncClient(" backend/src | grep -v "lib/http.py"
```

Expected: **no output** (all httpx usage goes through `make_http_client()`)

---

## P1 — Data Layer ✅

**Status**: verified 2026-05-01

| Check                                                                         | Result |
| ----------------------------------------------------------------------------- | ------ |
| `uv run pytest -v` → 29 passed                                             | ✅     |
| `alembic upgrade head` — 16 tables created                                 | ✅     |
| `alembic downgrade base` then `upgrade head` — clean roundtrip           | ✅     |
| `\d clients` → `journey_stage DEFAULT 'onboarding'` (no extra quotes)    | ✅     |
| `\d moms` → `status DEFAULT 'draft'`                                     | ✅     |
| Partial index `idx_refresh_tokens_active` uses `WHERE revoked_at IS NULL` | ✅     |
| All 16 tables present in `pg_tables`                                        | ✅     |

---

## P0 — Repo Scaffolding

**Status**: partially verified (test suite green; wrangler/frontend manual steps pending)

| Check                                                             | Result  |
| ----------------------------------------------------------------- | ------- |
| `uv run pytest tests/unit/` passes                              | ✅      |
| `uv run pytest tests/integration/test_health.py` passes         | ✅      |
| `GET /healthz` returns `{"status":"ok","version":"0.1.0"}`    | pending |
| `X-Request-ID` echoed in response headers                       | pending |
| Frontend `npm run dev` starts without errors (requires Node 22) | pending |
| `.env` not committed (in `.gitignore`)                        | ✅      |
| `docker-compose up` brings up postgres healthy                  | ✅      |
