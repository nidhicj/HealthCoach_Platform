# Verification Checkpoints

Append-only. Each phase ends with a manual checkpoint. Mark items ✅ when confirmed, ❌ if failed (and note the fix).

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
