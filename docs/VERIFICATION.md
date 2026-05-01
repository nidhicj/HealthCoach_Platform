# Verification Checkpoints

Append-only. Each phase ends with a manual checkpoint. Mark items ✅ when confirmed, ❌ if failed (and note the fix).

---

## P2 — Auth Service (current)

**Status**: ready to verify  
**Date**: 2026-05-01

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

| Check | Result |
|---|---|
| `uv run pytest -v` → 29 passed | ✅ |
| `alembic upgrade head` — 16 tables created | ✅ |
| `alembic downgrade base` then `upgrade head` — clean roundtrip | ✅ |
| `\d clients` → `journey_stage DEFAULT 'onboarding'` (no extra quotes) | ✅ |
| `\d moms` → `status DEFAULT 'draft'` | ✅ |
| Partial index `idx_refresh_tokens_active` uses `WHERE revoked_at IS NULL` | ✅ |
| All 16 tables present in `pg_tables` | ✅ |

---

## P0 — Repo Scaffolding

**Status**: partially verified (test suite green; wrangler/frontend manual steps pending)

| Check | Result |
|---|---|
| `uv run pytest tests/unit/` passes | ✅ |
| `uv run pytest tests/integration/test_health.py` passes | ✅ |
| `GET /healthz` returns `{"status":"ok","version":"0.1.0"}` | pending |
| `X-Request-ID` echoed in response headers | pending |
| Frontend `npm run dev` starts without errors (requires Node 22) | pending |
| `.env` not committed (in `.gitignore`) | ✅ |
| `docker-compose up` brings up postgres healthy | ✅ |
