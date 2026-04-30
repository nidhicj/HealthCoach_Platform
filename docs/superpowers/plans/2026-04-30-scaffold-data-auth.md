# Phase 0-1-2: Scaffold → Data Layer → Auth Service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the complete repo skeleton (P0), all database tables with migrations (P1), and the Google OAuth + JWT auth system (P2) per `docs/build-plan.md`.

**Architecture:** FastAPI on Cloudflare Python Workers backed by AWS RDS Postgres (local via Docker). Auth is fully owned: Google OAuth → ES256 JWT + refresh token rotation stored as SHA256 hashes. All DB access is async-only via asyncpg.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, asyncpg, python-jose[cryptography], httpx, uv, Cloudflare Workers (pywrangler), Next.js 15, Docker Compose (local Postgres)

**Session scope:** Stop at end of P2. Do NOT begin P3.

**Assumptions baked in (resolve CM items before executing):**
- CM-1: ADR-0003 marked Accepted before P1 begins
- CM-2: `llm_calls` uses `model_requested`/`model_served`/`prompt_version`/`request_id` columns
- CM-3: circular FK resolved via deferred `op.create_foreign_key()` in llm_calls migration
- CM-4: `retired_at` added to `hc_style_snippets` in P1 migration
- CM-5: all Python commands use `uv run` (not manual venv activation)
- CM-6: config file is `wrangler.toml`; `pywrangler` is just the CLI command name

---

## File map

```
parivarthan_platform/          ← repo root
├── .gitignore
├── .env.example
├── .dev.vars.example
├── .wranglerignore
├── docker-compose.yml
│
├── backend/
│   ├── pyproject.toml
│   ├── wrangler.toml
│   ├── .wranglerignore
│   └── src/
│       ├── main.py                     ← FastAPI app + health check
│       ├── config.py                   ← pydantic-settings env config
│       ├── lib/
│       │   └── http.py                 ← make_http_client() factory
│       ├── telemetry/
│       │   ├── scrub.py                ← PII scrub() function
│       │   ├── log.py                  ← get_logger() bound structured logger
│       │   └── sentry.py              ← Sentry init
│       ├── db/
│       │   ├── models.py              ← all SQLAlchemy 2.0 ORM models
│       │   ├── session.py             ← AsyncSession factory
│       │   └── migrations/
│       │       ├── env.py             ← Alembic env
│       │       ├── script.py.mako
│       │       └── versions/
│       │           └── 0001_initial_schema.py
│       └── auth/
│           ├── jwt_utils.py           ← ES256 sign/verify
│           ├── oauth.py               ← Google OAuth flow
│           ├── refresh.py             ← refresh token rotation + revocation
│           ├── dependencies.py        ← require_role(), current_tenant()
│           └── router.py              ← auth endpoints
│
├── backend/tests/
│   ├── conftest.py                    ← pytest fixtures (DB, client)
│   ├── unit/
│   │   ├── test_scrub.py
│   │   └── test_jwt_utils.py
│   └── integration/
│       ├── test_health.py
│       ├── test_models_roundtrip.py
│       ├── test_cascade_delete.py
│       └── test_auth.py
│
└── frontend/
    ├── package.json
    ├── next.config.js
    └── src/
        └── app/
            └── page.tsx               ← minimal placeholder
```

---

## P0 — Repo Scaffolding

---

### Task P0.1: Git init + base folder structure

**Files:**
- Create: `.gitignore` (root)
- Create: `README.md` (root, minimal)

- [ ] **Step 1: Init git repo**

```bash
cd /mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform
git init
git checkout -b main
```
Expected: `Initialized empty Git repository in .../parivarthan_platform/.git/`

- [ ] **Step 2: Create root .gitignore**

Create `/mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform/.gitignore`:

```gitignore
# Secrets
.env
.env.local
.dev.vars
*.pem
*.key

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/

# Node
node_modules/
.next/
out/

# Cloudflare / Wrangler
.wrangler/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Claude
.claude/settings.local.json
```

- [ ] **Step 3: Verify gitignore covers the right paths**

```bash
cat .gitignore | grep -E "\.env$|\.dev\.vars$|\.venv"
```
Expected output should show all three patterns.

- [ ] **Step 4: Commit**

```bash
git add .gitignore CLAUDE.md PREFLIGHT.md CONTRIBUTING.md README.md docs/ prompts/starter_prompt_01.md
git commit -m "chore: initial repo structure and docs"
```

---

### Task P0.2: Root environment files

**Files:**
- Create: `.env.example` (root)
- Create: `.dev.vars.example` (root)
- Create: `.wranglerignore` (root)

- [ ] **Step 1: Create .env.example**

```bash
cat > .env.example << 'EOF'
# --- Postgres (local dev via Docker Compose) ---
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev
TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test

# --- Auth ---
JWT_PRIVATE_KEY=<ES256 PEM private key — generate with openssl>
JWT_PUBLIC_KEY=<ES256 PEM public key — generate with openssl>
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
API_BASE_URL=http://localhost:8787

# --- LLM ---
OPENROUTER_API_KEY=<from openrouter.ai>

# --- Observability ---
SENTRY_DSN=<from sentry.io>
APP_ENV=dev

# --- App ---
APP_VERSION=0.1.0
EOF
```

- [ ] **Step 2: Create .dev.vars.example (Cloudflare Workers dev secrets)**

```bash
cat > .dev.vars.example << 'EOF'
# Cloudflare Workers dev environment secrets (.dev.vars is gitignored)
# Copy to .dev.vars and fill in real values for local Workers dev
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev
JWT_PRIVATE_KEY=
JWT_PUBLIC_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
OPENROUTER_API_KEY=
SENTRY_DSN=
APP_ENV=dev
API_BASE_URL=http://localhost:8787
EOF
```

- [ ] **Step 3: Create root .wranglerignore (workers-py #92 workaround)**

```bash
cat > .wranglerignore << 'EOF'
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
tests/
docs/
scripts/
*.md
EOF
```

- [ ] **Step 4: Verify .env is gitignored**

```bash
echo "DATABASE_URL=test" > .env
git status | grep .env
git status | grep -v "untracked"
rm .env
```
Expected: `.env` should NOT appear as a tracked file.

- [ ] **Step 5: Commit**

```bash
git add .env.example .dev.vars.example .wranglerignore
git commit -m "chore(config): add env templates and wranglerignore"
```

---

### Task P0.3: Docker Compose for local Postgres

**Files:**
- Create: `docker-compose.yml` (root)

- [ ] **Step 1: Create docker-compose.yml**

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: localdevpassword
      POSTGRES_DB: parivarthan_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

- [ ] **Step 2: Start Postgres and verify**

```bash
docker compose up -d postgres
sleep 3
docker compose exec postgres psql -U postgres -c "\l"
```
Expected: list of databases including `parivarthan_dev`.

- [ ] **Step 3: Also create the test DB**

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE parivarthan_test;"
```
Expected: `CREATE DATABASE`

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(infra): add docker-compose for local Postgres"
```

---

### Task P0.4: Backend Python project setup

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/wrangler.toml`
- Create: `backend/.wranglerignore`

- [ ] **Step 1: Create backend/pyproject.toml**

```toml
[project]
name = "parivarthan-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.27",
    "asyncpg>=0.29",
    "python-jose[cryptography]>=3.3",
    "sentry-sdk[fastapi]>=2.0",
    "structlog>=24.0",
    "python-multipart>=0.0.9",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
    "mypy>=1.10",
    "httpx>=0.27",
    "workers>=0.1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "S"]
ignore = ["S101"]  # allow assert in tests

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

- [ ] **Step 2: Create backend/wrangler.toml**

```toml
name = "parivarthan-backend"
main = "src/main.py"
compatibility_date = "2026-01-01"
compatibility_flags = ["python_workers"]

[observability]
enabled = true

[env.production]
name = "parivarthan-backend-production"
```

- [ ] **Step 3: Create backend/.wranglerignore**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
tests/
```

- [ ] **Step 4: Install dependencies**

```bash
cd backend
uv sync
```
Expected: packages resolved and installed into `.venv/`. No errors.

- [ ] **Step 5: Verify uv sync succeeded**

```bash
cd backend
uv run python -c "import fastapi; import sqlalchemy; import alembic; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/pyproject.toml backend/wrangler.toml backend/.wranglerignore
git commit -m "chore(backend): init Python project with uv, FastAPI, SQLAlchemy, Alembic"
```

---

### Task P0.5: Telemetry scaffolding — scrub() and structured logger

These must exist from day one per ADR-0006 and CLAUDE.md §8 (PII rule).

**Files:**
- Create: `backend/src/telemetry/__init__.py`
- Create: `backend/src/telemetry/scrub.py`
- Create: `backend/src/telemetry/log.py`
- Create: `backend/src/telemetry/sentry.py`
- Create: `backend/tests/unit/test_scrub.py`

- [ ] **Step 1: Write the failing test for scrub()**

Create `backend/tests/__init__.py` (empty), `backend/tests/unit/__init__.py` (empty), then:

```python
# backend/tests/unit/test_scrub.py
import pytest
from src.telemetry.scrub import scrub


def test_scrub_email():
    event = {"extra": {"email": "user@example.com", "note": "hello"}}
    result = scrub(event)
    assert result["extra"]["email"] == "<redacted>"
    assert result["extra"]["note"] == "hello"


def test_scrub_jwt_in_string():
    event = {"message": "token eyJhbGciOiJFUzI1NiJ9.payload.signature used"}
    result = scrub(event)
    assert "eyJ" not in result["message"]


def test_scrub_authorization_header():
    event = {"request": {"headers": {"authorization": "Bearer secret-token"}}}
    result = scrub(event)
    assert result["request"]["headers"]["authorization"] == "<redacted>"


def test_scrub_ip_truncation():
    event = {"ip": "192.168.1.100"}
    result = scrub(event)
    assert result["ip"] == "192.168.1.0"


def test_scrub_nested_transcript():
    event = {"data": {"transcript_content": "Patient said they feel stressed"}}
    result = scrub(event)
    assert result["data"]["transcript_content"] == "<redacted>"


def test_scrub_leaves_safe_fields():
    event = {"user_id": "abc-uuid", "hc_id": "xyz-uuid", "ms": 42}
    result = scrub(event)
    assert result["user_id"] == "abc-uuid"
    assert result["hc_id"] == "xyz-uuid"
    assert result["ms"] == 42
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend
uv run pytest tests/unit/test_scrub.py -v
```
Expected: `ModuleNotFoundError: No module named 'src'` or `ImportError`

- [ ] **Step 3: Create the telemetry package and implement scrub()**

```bash
mkdir -p src/telemetry
touch src/__init__.py src/telemetry/__init__.py
```

```python
# backend/src/telemetry/scrub.py
"""PII scrubber for Sentry events and structured log lines. Per ADR-0006 §3."""
import re
from typing import Any

_PII_KEYS = frozenset({
    "email", "phone", "name", "full_name", "display_name",
    "password", "token", "secret", "authorization", "cookie",
    "transcript", "transcript_content", "mom_content", "snippet_content",
    "original_text", "hc_modified_text", "refresh_token",
})

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def _scrub_value(key: str, value: Any) -> Any:
    if key.lower() in _PII_KEYS:
        return "<redacted>"
    if key.lower() == "ip" and isinstance(value, str):
        return _truncate_ip(value)
    if isinstance(value, str):
        value = _JWT_RE.sub("<jwt_redacted>", value)
        value = _EMAIL_RE.sub("<email_redacted>", value)
    return value


def _truncate_ip(ip: str) -> str:
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:3]) + "::"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
    return ip


def scrub(obj: Any) -> Any:
    """Recursively scrub PII from a dict/list/str. Safe to call on Sentry events."""
    if isinstance(obj, dict):
        return {k: _scrub_value(k, scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(item) for item in obj]
    return obj
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd backend
uv run pytest tests/unit/test_scrub.py -v
```
Expected: all 6 tests PASS.

- [ ] **Step 5: Create the structured logger**

```python
# backend/src/telemetry/log.py
"""Structured JSON logger per ADR-0006 §2. Binds request_id/user_id/hc_id/role."""
import json
import time
from datetime import datetime, timezone
from typing import Any
from .scrub import scrub


class BoundLogger:
    def __init__(self, request_id: str, user_id: str | None,
                 hc_id: str | None, role: str) -> None:
        self._base = {"request_id": request_id, "user_id": user_id,
                      "hc_id": hc_id, "role": role}

    def _emit(self, level: str, event: str, extra: dict[str, Any] | None = None) -> None:
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            **self._base,
        }
        if extra:
            record["extra"] = extra
        print(json.dumps(scrub(record)))

    def info(self, event: str, **extra: Any) -> None:
        self._emit("info", event, extra or None)

    def warn(self, event: str, **extra: Any) -> None:
        self._emit("warn", event, extra or None)

    def error(self, event: str, **extra: Any) -> None:
        self._emit("error", event, extra or None)


def get_logger(request_id: str, user_id: str | None = None,
               hc_id: str | None = None, role: str = "anon") -> BoundLogger:
    return BoundLogger(request_id, user_id, hc_id, role)
```

- [ ] **Step 6: Create Sentry init stub**

```python
# backend/src/telemetry/sentry.py
"""Sentry initialization per ADR-0006 §1."""
import os
from .scrub import scrub

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    def _before_send(event: dict, hint: dict) -> dict | None:  # type: ignore[type-arg]
        return scrub(event)  # type: ignore[return-value]

    def init_sentry() -> None:
        dsn = os.getenv("SENTRY_DSN", "")
        if not dsn:
            return
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("APP_ENV", "dev"),
            release=os.getenv("APP_VERSION", "0.1.0"),
            traces_sample_rate=0.0,
            profiles_sample_rate=0.0,
            send_default_pii=False,
            before_send=_before_send,
            before_breadcrumb=lambda bc, hint: scrub(bc),
            integrations=[FastApiIntegration()],
        )

except ImportError:
    def init_sentry() -> None:  # type: ignore[misc]
        pass
```

- [ ] **Step 7: Commit**

```bash
cd ..
git add backend/src/telemetry/ backend/tests/unit/test_scrub.py backend/tests/__init__.py backend/tests/unit/__init__.py backend/src/__init__.py
git commit -m "feat(telemetry): add scrub(), structured logger, Sentry init stub"
```

---

### Task P0.6: HTTP client factory + config

**Files:**
- Create: `backend/src/lib/http.py`
- Create: `backend/src/config.py`

- [ ] **Step 1: Create config.py**

```python
# backend/src/config.py
"""Environment-driven settings. All env vars read here, nowhere else."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      extra="ignore")

    # Database
    database_url: str = ""
    test_database_url: str = ""

    # Auth
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    api_base_url: str = "http://localhost:8787"

    # LLM
    openrouter_api_key: str = ""

    # Observability
    sentry_dsn: str = ""
    app_env: str = "dev"
    app_version: str = "0.1.0"


settings = Settings()
```

- [ ] **Step 2: Create lib/http.py factory (workers-py #68 workaround)**

```bash
mkdir -p backend/src/lib
touch backend/src/lib/__init__.py
```

```python
# backend/src/lib/http.py
"""HTTP client factory. ALL httpx.AsyncClient instances must go through here.
Workers-py #68: httpx on Cloudflare Workers omits User-Agent unless explicitly set."""
import httpx

_USER_AGENT = "parivarthan-backend/0.1 (https://parivarthan.com)"

# Pre-commit hook or CI should grep for raw `httpx.AsyncClient(` outside this file
# and fail the build. This factory is the single approved instantiation point.


def make_http_client(**kwargs: object) -> httpx.AsyncClient:
    """Return a configured AsyncClient with User-Agent set."""
    headers = dict(kwargs.pop("headers", {}))  # type: ignore[arg-type]
    headers.setdefault("User-Agent", _USER_AGENT)
    return httpx.AsyncClient(headers=headers, **kwargs)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/lib/ backend/src/config.py
git commit -m "feat(backend): add config settings and http client factory (workers-py #68)"
```

---

### Task P0.7: FastAPI app + health-check endpoint

**Files:**
- Create: `backend/src/main.py`
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_health.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend
uv run pytest tests/integration/test_health.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.main'`

- [ ] **Step 3: Create conftest.py**

```python
# backend/tests/conftest.py
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
```

- [ ] **Step 4: Create main.py**

```python
# backend/src/main.py
"""FastAPI application entry point for Cloudflare Python Workers."""
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .telemetry.sentry import init_sentry
from .telemetry.log import get_logger


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    init_sentry()
    yield


app = FastAPI(title="Parivarthan API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    logger = get_logger(request_id)
    request.state.logger = logger
    logger.info("request.start", method=request.method, path=request.url.path)
    response = await call_next(request)
    logger.info("request.end", status=response.status_code)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run test to confirm it passes**

```bash
cd backend
uv run pytest tests/integration/test_health.py -v
```
Expected: `test_health_check PASSED`

- [ ] **Step 6: Verify Worker boots locally**

```bash
cd backend
uv run pywrangler dev &
sleep 3
curl -s http://localhost:8787/health
```
Expected: `{"status":"ok"}`

Kill the background process: `kill %1`

- [ ] **Step 7: Commit**

```bash
cd ..
git add backend/src/main.py backend/tests/conftest.py backend/tests/integration/
git commit -m "feat(backend): FastAPI app with health check and request logging middleware"
```

---

### Task P0.8: Frontend skeleton

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Create frontend/package.json**

```json
{
  "name": "parivarthan-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "15.3.1",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "typescript": "^5",
    "tailwindcss": "^4",
    "@tailwindcss/postcss": "^4",
    "eslint": "^9",
    "eslint-config-next": "15.3.1"
  }
}
```

- [ ] **Step 2: Create next.config.js**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {};
module.exports = nextConfig;
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Create minimal app shell**

```bash
mkdir -p frontend/src/app
```

```tsx
// frontend/src/app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

```tsx
// frontend/src/app/page.tsx
export default function Home() {
  return <main><h1>Parivarthan — coming soon</h1></main>;
}
```

- [ ] **Step 5: Install and verify**

```bash
cd frontend
npm install
npm run dev &
sleep 5
curl -s http://localhost:3000 | grep -i parivarthan
kill %1
```
Expected: HTML containing "Parivarthan"

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat(frontend): Next.js 15 skeleton"
```

---

## P0 verification

Run these before declaring P0 complete. Tick each checkbox only after the command passes.

- [ ] `tree -L 3 backend/ frontend/ | head -60` — matches ADR-0004 layout
- [ ] `cd backend && uv sync` — succeeds with no errors
- [ ] `cd backend && uv run pywrangler dev` — Worker boots on localhost:8787
- [ ] `curl localhost:8787/health` — returns `{"status":"ok"}`
- [ ] `cd frontend && npm run dev` — Next.js boots on localhost:3000
- [ ] `docker compose up -d postgres && psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "\dt"` — connection works
- [ ] `cd backend && uv run pytest tests/` — health + scrub tests pass
- [ ] `git log --oneline` — no secrets in diff (`git diff HEAD~5` should show no keys/passwords)

**STOP. Wait for SoJo to verify P0 before starting P1.**

---

## P1 — Data Layer

---

### Task P1.0: Resolve ADR-0003 schema (run before any P1 code)

**Files:**
- Modify: `docs/decisions/0003-llm-strategy.md` — status Proposed → Accepted; add missing columns
- Modify: `docs/diagrams/0002-data-model.md` — add `auth_refresh_tokens` table + `retired_at` on snippets

- [ ] **Step 1: Flip ADR-0003 to Accepted**

Edit line 3 of `docs/decisions/0003-llm-strategy.md`:
```
**Status**: Accepted
```

- [ ] **Step 2: Amend llm_calls schema in ADR-0003 §4**

Replace the `CREATE TABLE llm_calls` block in ADR-0003 with the reconciled version:

```sql
CREATE TABLE llm_calls (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id        UUID,                                -- from X-Request-ID (ADR-0006 §4)
    hc_user_id        UUID NOT NULL REFERENCES users(id),
    client_id         UUID REFERENCES clients(id),
    session_id        UUID REFERENCES sessions(id),
    use_case          TEXT NOT NULL,                      -- 'mom_generation', 'brief_generation', etc.
    model_requested   TEXT NOT NULL,                      -- first model in chain attempted
    model_served      TEXT,                               -- model that actually responded (null if all failed)
    prompt_version    TEXT,                               -- from prompt YAML frontmatter
    fallback_count    INTEGER NOT NULL DEFAULT 0,
    input_tokens      INTEGER NOT NULL,
    output_tokens     INTEGER NOT NULL,
    latency_ms        INTEGER NOT NULL,
    validation_failed BOOLEAN NOT NULL DEFAULT FALSE,
    snippet_count     INTEGER NOT NULL DEFAULT 0,
    snippet_tokens    INTEGER NOT NULL DEFAULT 0,
    inr_cost_estimate NUMERIC(10, 4),
    raw_request_id    TEXT,                               -- OpenRouter request ID
    error_message     TEXT
);

CREATE INDEX idx_llm_calls_created_at ON llm_calls (created_at DESC);
CREATE INDEX idx_llm_calls_hc_use_case ON llm_calls (hc_user_id, use_case);
CREATE INDEX idx_llm_calls_validation_failed ON llm_calls (validation_failed) WHERE validation_failed = TRUE;
```

- [ ] **Step 3: Update data model diagram to add auth_refresh_tokens**

Add the following section to `docs/diagrams/0002-data-model.md` after the `users` table, before `identities`:

```markdown
### `auth_refresh_tokens`

(Per ADR-0005 §10. Added 2026-04-30 — was missing from original diagram.)

\```sql
CREATE TABLE auth_refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    successor_id    UUID REFERENCES auth_refresh_tokens(id),
    user_agent      TEXT,
    ip_at_issue     INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id ON auth_refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON auth_refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_active ON auth_refresh_tokens (user_id)
    WHERE revoked_at IS NULL AND expires_at > NOW();
\```
```

Also add `retired_at TIMESTAMPTZ` column to `hc_style_snippets` DDL in the diagram.

- [ ] **Step 4: Commit diagram + ADR updates**

```bash
git add docs/decisions/0003-llm-strategy.md docs/diagrams/0002-data-model.md
git commit -m "docs(adr): accept ADR-0003; reconcile llm_calls schema; add auth_refresh_tokens to data model"
```

---

### Task P1.1: SQLAlchemy 2.0 models

**Files:**
- Create: `backend/src/db/__init__.py`
- Create: `backend/src/db/models.py`

- [ ] **Step 1: Write failing import test**

```python
# backend/tests/unit/test_models_import.py
from src.db.models import (
    User, Client, Session, Mom, Brief, ActionItem,
    CheckIn, Consent, HcStyleSnippet, LlmCall,
    AuthRefreshToken, AuditLog, DietChart, PrepRecipe,
    DietChartRecipe, ContentAssignment,
)

def test_all_models_importable():
    assert User.__tablename__ == "users"
    assert Client.__tablename__ == "clients"
    assert AuthRefreshToken.__tablename__ == "auth_refresh_tokens"
    assert LlmCall.__tablename__ == "llm_calls"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && uv run pytest tests/unit/test_models_import.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create models.py**

```bash
mkdir -p src/db && touch src/db/__init__.py
```

```python
# backend/src/db/models.py
"""SQLAlchemy 2.0 ORM models. All tables per docs/diagrams/0002-data-model.md.
Cascade rules: every FK to clients has ON DELETE CASCADE."""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    ARRAY, Boolean, CheckConstraint, Date, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    google_sub: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    is_operator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(),
                                                  onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column()

    __table_args__ = (Index("idx_users_email", "email"),)


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column()
    revoked_at: Mapped[Optional[datetime]] = mapped_column()
    successor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_refresh_tokens.id"))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    ip_at_issue: Mapped[Optional[str]] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_token_hash", "token_hash"),
    )


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(Text)
    phone: Mapped[Optional[str]] = mapped_column(Text)
    timezone: Mapped[Optional[str]] = mapped_column(Text)
    journey_stage: Mapped[str] = mapped_column(
        Text, nullable=False, default="onboarding",
        server_default="onboarding")
    course_start_date: Mapped[Optional[date]] = mapped_column(Date)
    course_end_date: Mapped[Optional[date]] = mapped_column(Date)
    course_goal: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(),
                                                  onupdate=func.now())

    __table_args__ = (
        Index("idx_clients_hc_user_id", "hc_user_id"),
        Index("idx_clients_journey_stage", "hc_user_id", "journey_stage"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column()
    ended_at: Mapped[Optional[datetime]] = mapped_column()
    zoom_meeting_id: Mapped[Optional[str]] = mapped_column(Text)
    transcript_s3_key: Mapped[Optional[str]] = mapped_column(Text)
    summary_s3_key: Mapped[Optional[str]] = mapped_column(Text)
    notes_internal: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_sessions_client_id", "client_id"),
        Index("idx_sessions_hc_user_id_scheduled", "hc_user_id", "scheduled_at"),
        UniqueConstraint("client_id", "session_number",
                         name="idx_sessions_client_session_number"),
    )


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"))
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"))
    use_case: Mapped[str] = mapped_column(Text, nullable=False)
    model_requested: Mapped[str] = mapped_column(Text, nullable=False)
    model_served: Mapped[Optional[str]] = mapped_column(Text)
    prompt_version: Mapped[Optional[str]] = mapped_column(Text)
    fallback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    snippet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snippet_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inr_cost_estimate: Mapped[Optional[float]] = mapped_column(Numeric(10, 4))
    raw_request_id: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_llm_calls_created_at", "created_at"),
        Index("idx_llm_calls_hc_use_case", "hc_user_id", "use_case"),
    )


class Mom(Base):
    __tablename__ = "moms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"),
        unique=True, nullable=False)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    final_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft",
                                         server_default="draft")
    sent_at: Mapped[Optional[datetime]] = mapped_column()
    sent_to_email: Mapped[Optional[str]] = mapped_column(Text)
    # FK to llm_calls added after llm_calls table exists (see migration 0001)
    llm_call_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(),
                                                  onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'reviewed', 'sent')", name="ck_moms_status"),
        Index("idx_moms_status", "status"),
        Index("idx_moms_client_id", "client_id"),
    )


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"),
        unique=True, nullable=False)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    brief_text: Mapped[str] = mapped_column(Text, nullable=False)
    triage_flags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    llm_call_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_briefs_session_id", "session_id"),)


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"))
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open",
                                         server_default="open")
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'completed', 'missed', 'rolled_over')",
            name="ck_action_items_status"),
        Index("idx_action_items_client_status", "client_id", "status"),
    )


class CheckIn(Base):
    __tablename__ = "check_ins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sentiment_flag: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_check_ins_client_created", "client_id", "created_at"),)


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column()
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_artifact_s3_key: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_consents_client_purpose", "client_id", "purpose"),)


class HcStyleSnippet(Base):
    __tablename__ = "hc_style_snippets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    snippet_type: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    hc_modified_text: Mapped[Optional[str]] = mapped_column(Text)
    context_summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column()
    retired_at: Mapped[Optional[datetime]] = mapped_column()
    relevance_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "snippet_type IN ('edit', 'exchange', 'pattern')",
            name="ck_snippet_type"),
        Index("idx_snippets_hc_user_id", "hc_user_id"),
        Index("idx_snippets_client_id", "client_id"),
        Index("idx_snippets_last_used", "hc_user_id", "last_used_at"),
    )


class DietChart(Base):
    __tablename__ = "diet_charts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(),
                                                  onupdate=func.now())
    archived_at: Mapped[Optional[datetime]] = mapped_column()

    __table_args__ = (Index("idx_diet_charts_hc_user_id", "hc_user_id"),)


class PrepRecipe(Base):
    __tablename__ = "prep_recipes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    ingredients: Mapped[dict] = mapped_column(JSONB, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    archived_at: Mapped[Optional[datetime]] = mapped_column()

    __table_args__ = (Index("idx_prep_recipes_hc_user_id", "hc_user_id"),)


class DietChartRecipe(Base):
    __tablename__ = "diet_chart_recipes"

    diet_chart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("diet_charts.id", ondelete="CASCADE"),
        primary_key=True, nullable=False)
    prep_recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prep_recipes.id", ondelete="CASCADE"),
        primary_key=True, nullable=False)


class ContentAssignment(Base):
    __tablename__ = "content_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    hc_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"))
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_content_assignments_client", "client_id", "assigned_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                           default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_table: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    target_hc_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_audit_log_target", "target_hc_user_id", "created_at"),
    )
```

- [ ] **Step 4: Run import test to confirm it passes**

```bash
cd backend
uv run pytest tests/unit/test_models_import.py -v
```
Expected: `test_all_models_importable PASSED`

- [ ] **Step 5: Commit**

```bash
cd ..
git add backend/src/db/ backend/tests/unit/test_models_import.py
git commit -m "feat(db): SQLAlchemy 2.0 models for all 16 tables"
```

---

### Task P1.2: Async session factory

**Files:**
- Create: `backend/src/db/session.py`

- [ ] **Step 1: Create session.py**

```python
# backend/src/db/session.py
"""Async SQLAlchemy session factory. Per ADR-0001 Consequence #3: async-only."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings

# Engine is created lazily — tests override DATABASE_URL before first access
_engine = None
_session_factory = None


def get_engine():  # type: ignore[return]
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL not configured")
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_env == "dev",
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for DB sessions."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/db/session.py
git commit -m "feat(db): async session factory with asyncpg"
```

---

### Task P1.3: Alembic init + first migration

**Files:**
- Create: `backend/src/db/migrations/env.py`
- Create: `backend/src/db/migrations/script.py.mako`
- Create: `backend/src/db/migrations/versions/0001_initial_schema.py`
- Create: `backend/alembic.ini`

- [ ] **Step 1: Init Alembic**

```bash
cd backend
uv run alembic init src/db/migrations
```
Expected: creates `alembic.ini` and `src/db/migrations/` with `env.py` and `script.py.mako`.

- [ ] **Step 2: Edit alembic.ini to set script_location**

In `backend/alembic.ini`, set:
```ini
script_location = src/db/migrations
sqlalchemy.url = 
```
(Leave `sqlalchemy.url` empty — we set it from env in `env.py`.)

- [ ] **Step 3: Edit migrations/env.py**

Replace the generated `env.py` with:

```python
# backend/src/db/migrations/env.py
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL env var required for migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(url=get_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(get_url())
    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn, target_metadata=target_metadata)
        )
        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Generate the initial migration**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  uv run alembic revision --autogenerate -m "initial_schema"
```
Expected: creates `src/db/migrations/versions/<hash>_initial_schema.py`

Rename it to `0001_initial_schema.py`:
```bash
mv src/db/migrations/versions/*_initial_schema.py src/db/migrations/versions/0001_initial_schema.py
```

- [ ] **Step 5: Review generated migration**

Open `0001_initial_schema.py` and verify:
- All 16 tables are in `upgrade()`
- `moms` and `briefs` tables do NOT have `llm_call_id` FK constraints at this point (we add them later — they're plain columns)
- `downgrade()` drops tables in reverse order

**IMPORTANT**: After the `llm_calls` table creation in `upgrade()`, manually add the deferred FKs:

```python
# In upgrade(), after all tables are created, add:
op.create_foreign_key(
    "fk_moms_llm_call_id", "moms", "llm_calls", ["llm_call_id"], ["id"])
op.create_foreign_key(
    "fk_briefs_llm_call_id", "briefs", "llm_calls", ["llm_call_id"], ["id"])

# In downgrade(), before dropping moms/briefs, add:
op.drop_constraint("fk_moms_llm_call_id", "moms", type_="foreignkey")
op.drop_constraint("fk_briefs_llm_call_id", "briefs", type_="foreignkey")
```

- [ ] **Step 6: Run upgrade and verify**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  uv run alembic upgrade head
```
Expected: runs migration without errors.

```bash
docker compose exec postgres psql -U postgres -d parivarthan_dev -c "\dt"
```
Expected: 16 tables listed.

- [ ] **Step 7: Test downgrade (reversibility)**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  uv run alembic downgrade base
```
Expected: all tables dropped.

Then re-upgrade:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  uv run alembic upgrade head
```

- [ ] **Step 8: Commit**

```bash
cd ..
git add backend/alembic.ini backend/src/db/migrations/
git commit -m "feat(db): Alembic init + initial schema migration (16 tables)"
```

---

### Task P1.4: Integration tests — roundtrip and cascade

**Files:**
- Modify: `backend/tests/conftest.py` — add DB fixtures
- Create: `backend/tests/integration/test_models_roundtrip.py`
- Create: `backend/tests/integration/test_cascade_delete.py`

- [ ] **Step 1: Expand conftest.py with DB fixtures**

```python
# backend/tests/conftest.py
import asyncio
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Base

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test",
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()
```

- [ ] **Step 2: Write roundtrip test**

```python
# backend/tests/integration/test_models_roundtrip.py
"""Verify every table can be written and read back. P1 acceptance criterion."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AuditLog, AuthRefreshToken, CheckIn, Client, Consent,
    ContentAssignment, DietChart, DietChartRecipe, HcStyleSnippet,
    LlmCall, Mom, PrepRecipe, Session, User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
async def hc_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"hc-{uuid.uuid4()}@test.com",
        google_sub=f"google-{uuid.uuid4()}",
        display_name="Test HC",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def client_record(db_session: AsyncSession, hc_user: User) -> Client:
    client = Client(hc_user_id=hc_user.id, full_name="Test Client")
    db_session.add(client)
    await db_session.flush()
    return client


@pytest.mark.asyncio
async def test_user_roundtrip(db_session: AsyncSession):
    user = User(email=f"rt-{uuid.uuid4()}@test.com",
                google_sub=f"g-{uuid.uuid4()}", display_name="Round Trip")
    db_session.add(user)
    await db_session.commit()
    result = await db_session.get(User, user.id)
    assert result is not None
    assert result.display_name == "Round Trip"


@pytest.mark.asyncio
async def test_auth_refresh_token_roundtrip(db_session: AsyncSession, hc_user: User):
    from datetime import timedelta
    token = AuthRefreshToken(
        user_id=hc_user.id,
        token_hash="abc123deadbeef",
        expires_at=_now() + timedelta(days=30),
    )
    db_session.add(token)
    await db_session.commit()
    result = await db_session.get(AuthRefreshToken, token.id)
    assert result is not None
    assert result.token_hash == "abc123deadbeef"


@pytest.mark.asyncio
async def test_client_roundtrip(db_session: AsyncSession, hc_user: User):
    client = Client(hc_user_id=hc_user.id, full_name="Alice")
    db_session.add(client)
    await db_session.commit()
    result = await db_session.get(Client, client.id)
    assert result is not None
    assert result.full_name == "Alice"


@pytest.mark.asyncio
async def test_session_roundtrip(db_session: AsyncSession,
                                  hc_user: User, client_record: Client):
    session = Session(hc_user_id=hc_user.id, client_id=client_record.id,
                      session_number=1, scheduled_at=_now())
    db_session.add(session)
    await db_session.commit()
    result = await db_session.get(Session, session.id)
    assert result is not None
    assert result.session_number == 1


@pytest.mark.asyncio
async def test_llm_call_roundtrip(db_session: AsyncSession, hc_user: User):
    call = LlmCall(
        hc_user_id=hc_user.id,
        use_case="mom_generation",
        model_requested="meta-llama/llama-3.3-70b-instruct:free",
        input_tokens=100, output_tokens=200, latency_ms=1500,
    )
    db_session.add(call)
    await db_session.commit()
    result = await db_session.get(LlmCall, call.id)
    assert result is not None
    assert result.model_requested == "meta-llama/llama-3.3-70b-instruct:free"


@pytest.mark.asyncio
async def test_hc_style_snippet_roundtrip(db_session: AsyncSession,
                                           hc_user: User, client_record: Client):
    snippet = HcStyleSnippet(
        hc_user_id=hc_user.id,
        client_id=client_record.id,
        snippet_type="edit",
        original_text="Drink more water",
        hc_modified_text="Aim for 2.5L water/day, track in app",
    )
    db_session.add(snippet)
    await db_session.commit()
    result = await db_session.get(HcStyleSnippet, snippet.id)
    assert result is not None
    assert result.hc_modified_text == "Aim for 2.5L water/day, track in app"
```

- [ ] **Step 3: Write cascade delete test**

```python
# backend/tests/integration/test_cascade_delete.py
"""Verify ON DELETE CASCADE works for client-scoped tables. P1 acceptance criterion."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    ActionItem, CheckIn, Client, Consent, HcStyleSnippet,
    Mom, Session, User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_cascade_delete_client_removes_snippets(db_session: AsyncSession):
    user = User(email=f"cascade-{uuid.uuid4()}@test.com",
                google_sub=f"g-cascade-{uuid.uuid4()}")
    db_session.add(user)
    await db_session.flush()

    client = Client(hc_user_id=user.id, full_name="To Delete")
    db_session.add(client)
    await db_session.flush()
    client_id = client.id

    snippets = [
        HcStyleSnippet(hc_user_id=user.id, client_id=client_id,
                       snippet_type="edit", original_text=f"text {i}",
                       hc_modified_text=f"modified {i}")
        for i in range(3)
    ]
    db_session.add_all(snippets)
    await db_session.commit()

    # Verify snippets exist
    rows = (await db_session.execute(
        select(HcStyleSnippet).where(HcStyleSnippet.client_id == client_id)
    )).scalars().all()
    assert len(rows) == 3

    # Delete client — should cascade
    await db_session.delete(client)
    await db_session.commit()

    # Verify snippets gone
    rows_after = (await db_session.execute(
        select(HcStyleSnippet).where(HcStyleSnippet.client_id == client_id)
    )).scalars().all()
    assert len(rows_after) == 0


@pytest.mark.asyncio
async def test_cascade_delete_client_removes_moms_and_action_items(db_session: AsyncSession):
    user = User(email=f"cascade2-{uuid.uuid4()}@test.com",
                google_sub=f"g-cascade2-{uuid.uuid4()}")
    db_session.add(user)
    await db_session.flush()

    client = Client(hc_user_id=user.id, full_name="Cascade Client 2")
    db_session.add(client)
    await db_session.flush()
    client_id = client.id

    session = Session(hc_user_id=user.id, client_id=client_id,
                      session_number=1, scheduled_at=_now())
    db_session.add(session)
    await db_session.flush()

    mom = Mom(session_id=session.id, hc_user_id=user.id, client_id=client_id,
              draft_text="AI draft text")
    action = ActionItem(client_id=client_id, hc_user_id=user.id,
                        description="Drink water")
    check_in = CheckIn(client_id=client_id, hc_user_id=user.id,
                       payload={"mood": "good"})
    consent = Consent(client_id=client_id, hc_user_id=user.id,
                      purpose="service", granted=True, granted_at=_now(),
                      source="in_app")
    db_session.add_all([mom, action, check_in, consent])
    await db_session.commit()

    await db_session.delete(client)
    await db_session.commit()

    assert (await db_session.execute(
        select(Mom).where(Mom.client_id == client_id))).scalars().first() is None
    assert (await db_session.execute(
        select(ActionItem).where(ActionItem.client_id == client_id))).scalars().first() is None
    assert (await db_session.execute(
        select(CheckIn).where(CheckIn.client_id == client_id))).scalars().first() is None
    assert (await db_session.execute(
        select(Consent).where(Consent.client_id == client_id))).scalars().first() is None
```

- [ ] **Step 4: Run all integration tests**

```bash
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test \
  uv run pytest tests/integration/ -v
```
Expected: all roundtrip and cascade tests PASS.

- [ ] **Step 5: Verify async-only (no sync Session usage)**

```bash
grep -r "from sqlalchemy.orm import Session" backend/src/
grep -r "Session(" backend/src/ | grep -v "AsyncSession"
```
Expected: no output from either grep.

- [ ] **Step 6: Commit**

```bash
cd ..
git add backend/tests/
git commit -m "test(db): roundtrip and cascade delete integration tests for all tables"
```

---

## P1 verification

- [ ] `alembic upgrade head` runs clean against local Postgres
- [ ] `\dt` in psql shows all 16 expected tables
- [ ] `alembic downgrade base` works without errors
- [ ] `uv run pytest tests/integration/test_models_roundtrip.py -v` — all pass
- [ ] `uv run pytest tests/integration/test_cascade_delete.py -v` — all pass
- [ ] `grep -r "Session(" backend/src | grep -v AsyncSession` — returns empty

**STOP. Wait for SoJo to verify P1 before starting P2.**

---

## P2 — Auth Service

---

### Task P2.1: JWT utilities (ES256 sign + verify)

**Files:**
- Create: `backend/src/auth/__init__.py`
- Create: `backend/src/auth/jwt_utils.py`
- Create: `backend/tests/unit/test_jwt_utils.py`

- [ ] **Step 1: Generate ES256 test keys**

```bash
cd backend
openssl ecparam -name prime256v1 -genkey -noout -out /tmp/test_priv.pem
openssl ec -in /tmp/test_priv.pem -pubout -out /tmp/test_pub.pem
cat /tmp/test_priv.pem
cat /tmp/test_pub.pem
```
Copy the output — you'll embed them as test fixtures.

- [ ] **Step 2: Write failing JWT unit tests**

```python
# backend/tests/unit/test_jwt_utils.py
"""Unit tests for ES256 JWT sign/verify. Per ADR-0005 §2 and §3."""
import time
import uuid
import pytest
from src.auth.jwt_utils import (
    create_access_token, decode_access_token, TokenClaims, AuthError
)

# Minimal ES256 key pair for tests only (NOT production keys)
TEST_PRIVATE_KEY = """-----BEGIN EC PRIVATE KEY-----
<paste private key here from openssl output>
-----END EC PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
<paste public key here from openssl output>
-----END PUBLIC KEY-----"""


def test_create_and_decode_access_token():
    user_id = uuid.uuid4()
    hc_id = uuid.uuid4()
    token = create_access_token(
        sub=str(user_id),
        role="hc",
        hc_id=str(hc_id),
        private_key=TEST_PRIVATE_KEY,
    )
    assert isinstance(token, str)
    claims = decode_access_token(token, public_key=TEST_PUBLIC_KEY)
    assert claims.sub == str(user_id)
    assert claims.role == "hc"
    assert claims.hc_id == str(hc_id)
    assert claims.iss == "https://api.parivarthan.com"


def test_expired_token_raises():
    token = create_access_token(
        sub=str(uuid.uuid4()), role="hc", hc_id=str(uuid.uuid4()),
        private_key=TEST_PRIVATE_KEY, ttl_seconds=-1,  # already expired
    )
    with pytest.raises(AuthError, match="expired"):
        decode_access_token(token, public_key=TEST_PUBLIC_KEY)


def test_wrong_key_raises():
    import subprocess, tempfile, os
    result = subprocess.run(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout",
         "-out", "/tmp/other_priv.pem"], capture_output=True)
    subprocess.run(["openssl", "ec", "-in", "/tmp/other_priv.pem", "-pubout",
                    "-out", "/tmp/other_pub.pem"], capture_output=True)
    with open("/tmp/other_pub.pem") as f:
        other_pub = f.read()
    token = create_access_token(
        sub=str(uuid.uuid4()), role="hc", hc_id=str(uuid.uuid4()),
        private_key=TEST_PRIVATE_KEY,
    )
    with pytest.raises(AuthError):
        decode_access_token(token, public_key=other_pub)


def test_client_role_hc_id_is_hc_not_self():
    client_id = uuid.uuid4()
    hc_id = uuid.uuid4()
    token = create_access_token(
        sub=str(client_id), role="client", hc_id=str(hc_id),
        private_key=TEST_PRIVATE_KEY,
    )
    claims = decode_access_token(token, public_key=TEST_PUBLIC_KEY)
    assert claims.role == "client"
    assert claims.hc_id == str(hc_id)
    assert claims.sub == str(client_id)
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd backend && uv run pytest tests/unit/test_jwt_utils.py -v
```
Expected: `ImportError: cannot import name 'create_access_token'`

- [ ] **Step 4: Implement jwt_utils.py**

```bash
mkdir -p src/auth && touch src/auth/__init__.py
```

```python
# backend/src/auth/jwt_utils.py
"""ES256 JWT sign/verify. Per ADR-0005 §2 and §3."""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt

_ALGORITHM = "ES256"
_ISSUER = "https://api.parivarthan.com"
_AUDIENCE = "parivarthan-api"
_ACCESS_TTL_SECONDS = 15 * 60  # 15 minutes


class AuthError(Exception):
    """Raised on any JWT validation failure."""


@dataclass
class TokenClaims:
    sub: str
    role: str
    hc_id: str | None
    jti: str
    iat: int
    exp: int
    iss: str = _ISSUER


def create_access_token(
    *,
    sub: str,
    role: str,
    hc_id: str | None,
    private_key: str,
    ttl_seconds: int = _ACCESS_TTL_SECONDS,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": sub,
        "role": role,
        "hc_id": hc_id,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, private_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, *, public_key: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token, public_key, algorithms=[_ALGORITHM],
            audience=_AUDIENCE, issuer=_ISSUER,
        )
    except ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except JWTError as exc:
        raise AuthError(f"invalid token: {exc}") from exc

    return TokenClaims(
        sub=payload["sub"],
        role=payload["role"],
        hc_id=payload.get("hc_id"),
        jti=payload["jti"],
        iat=payload["iat"],
        exp=payload["exp"],
        iss=payload["iss"],
    )
```

- [ ] **Step 5: Fill in the test key values**

Open `tests/unit/test_jwt_utils.py` and replace the placeholder PEM strings with the actual output from the `openssl` commands in Step 1.

- [ ] **Step 6: Run tests to confirm pass**

```bash
cd backend && uv run pytest tests/unit/test_jwt_utils.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd ..
git add backend/src/auth/ backend/tests/unit/test_jwt_utils.py
git commit -m "feat(auth): ES256 JWT sign/verify utilities"
```

---

### Task P2.2: Refresh token rotation + storage

**Files:**
- Create: `backend/src/auth/refresh.py`

- [ ] **Step 1: Create refresh.py**

```python
# backend/src/auth/refresh.py
"""Refresh token lifecycle: issue, rotate, revoke. Per ADR-0005 §5."""
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AuthRefreshToken

_REFRESH_TTL_DAYS = 30


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_raw_token() -> str:
    return os.urandom(32).hex()


async def issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_agent: str | None = None,
    ip: str | None = None,
) -> str:
    raw = _generate_raw_token()
    token = AuthRefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=_REFRESH_TTL_DAYS),
        user_agent=user_agent,
        ip_at_issue=ip,
    )
    db.add(token)
    await db.flush()
    return raw


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, uuid.UUID]:
    """
    Returns (new_raw_token, user_id) on success.
    Raises ValueError on invalid/expired/revoked token.
    If presented token already has a successor → replay detected → revoke all sessions.
    """
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if token is None:
        raise ValueError("refresh token not found")

    now = datetime.now(timezone.utc)

    if token.expires_at.replace(tzinfo=timezone.utc) < now:
        raise ValueError("refresh token expired")

    if token.revoked_at is not None:
        raise ValueError("refresh token revoked")

    if token.successor_id is not None:
        # Replay attack: legitimate user has already rotated; revoke ALL for this user
        await _revoke_all_for_user(db, token.user_id)
        raise ValueError("refresh token replay detected — all sessions revoked")

    # Issue new token
    new_raw = _generate_raw_token()
    new_token = AuthRefreshToken(
        user_id=token.user_id,
        token_hash=_hash_token(new_raw),
        expires_at=now + timedelta(days=_REFRESH_TTL_DAYS),
        user_agent=user_agent,
        ip_at_issue=ip,
    )
    db.add(new_token)
    await db.flush()

    # Mark old token as consumed (set successor)
    token.successor_id = new_token.id
    token.revoked_at = now
    await db.flush()

    return new_raw, token.user_id


async def revoke_token(db: AsyncSession, raw_token: str) -> None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token and token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        await db.flush()


async def _revoke_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AuthRefreshToken)
        .where(AuthRefreshToken.user_id == user_id,
               AuthRefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.flush()
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/auth/refresh.py
git commit -m "feat(auth): refresh token issue/rotate/revoke with replay detection"
```

---

### Task P2.3: HTTP client factory + Google OAuth flow

**Files:**
- Create: `backend/src/auth/oauth.py`

- [ ] **Step 1: Create oauth.py**

```python
# backend/src/auth/oauth.py
"""Google OAuth 2.0 Authorization Code + PKCE flow. Per ADR-0005 §1."""
import base64
import hashlib
import os
import urllib.parse
from dataclasses import dataclass

from ..lib.http import make_http_client

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_SCOPES = "openid email profile"


@dataclass
class GoogleUserInfo:
    sub: str       # Google's stable user ID
    email: str
    name: str
    picture: str | None


def generate_pkce_pair() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge)."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": _SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_userinfo(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> GoogleUserInfo:
    async with make_http_client() as client:
        token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        })
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        info_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        info_resp.raise_for_status()
        data = info_resp.json()

    return GoogleUserInfo(
        sub=data["sub"],
        email=data["email"],
        name=data.get("name", ""),
        picture=data.get("picture"),
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/auth/oauth.py
git commit -m "feat(auth): Google OAuth PKCE flow"
```

---

### Task P2.4: FastAPI auth dependencies

**Files:**
- Create: `backend/src/auth/dependencies.py`

- [ ] **Step 1: Create dependencies.py**

```python
# backend/src/auth/dependencies.py
"""FastAPI dependencies: require_role(), current_tenant(). Per ADR-0005 §7."""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings
from .jwt_utils import AuthError, TokenClaims, decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    claims: TokenClaims


def _get_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenClaims:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing authentication token")
    try:
        claims = decode_access_token(
            credentials.credentials, public_key=settings.jwt_public_key)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=str(exc)) from exc
    return claims


def require_role(*roles: str):
    """FastAPI dependency factory. Usage: Depends(require_role('hc'))"""
    def _check(claims: Annotated[TokenClaims, Depends(_get_claims)]) -> TokenClaims:
        if claims.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Insufficient role")
        return claims
    return _check


def current_tenant(
    claims: Annotated[TokenClaims, Depends(_get_claims)],
) -> str:
    """Returns the hc_id from the JWT. All domain queries must filter by this."""
    if claims.hc_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="No tenant context in token")
    return claims.hc_id
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/auth/dependencies.py
git commit -m "feat(auth): require_role() and current_tenant() FastAPI dependencies"
```

---

### Task P2.5: Auth router + endpoints

**Files:**
- Create: `backend/src/auth/router.py`
- Modify: `backend/src/main.py` — register auth router

- [ ] **Step 1: Create router.py**

```python
# backend/src/auth/router.py
"""Auth endpoints per ADR-0005 §11."""
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import User
from ..db.session import get_db
from .dependencies import current_tenant, require_role
from .jwt_utils import TokenClaims, create_access_token
from .oauth import build_authorization_url, exchange_code_for_userinfo, generate_pkce_pair
from .refresh import issue_refresh_token, revoke_token, rotate_refresh_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory state store for OAuth (Workers KV preferred in prod — acceptable for MVP)
_state_store: dict[str, dict] = {}

_COOKIE_NAME = "refresh_token"
_CSRF_COOKIE = "csrf_token"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.app_env != "dev",
        samesite="lax",
        path="/api/auth",
        max_age=30 * 24 * 3600,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/api/auth")


@router.get("/google/start")
async def google_start() -> dict:
    state = str(uuid.uuid4())
    verifier, challenge = generate_pkce_pair()
    _state_store[state] = {"verifier": verifier}
    redirect_uri = f"{settings.api_base_url}/api/auth/google/callback"
    auth_url = build_authorization_url(
        client_id=settings.google_client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=challenge,
    )
    return {"auth_url": auth_url}


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> TokenResponse:
    stored = _state_store.pop(state, None)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid or expired state")

    redirect_uri = f"{settings.api_base_url}/api/auth/google/callback"
    user_info = await exchange_code_for_userinfo(
        code=code,
        code_verifier=stored["verifier"],
        redirect_uri=redirect_uri,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

    # Upsert user
    result = await db.execute(select(User).where(User.google_sub == user_info.sub))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=user_info.email, google_sub=user_info.sub,
                    display_name=user_info.name, photo_url=user_info.picture)
        db.add(user)
        await db.flush()

    hc_id = str(user.id)
    access_token = create_access_token(
        sub=str(user.id), role="hc", hc_id=hc_id,
        private_key=settings.jwt_private_key,
    )
    raw_refresh = await issue_refresh_token(
        db, user.id,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/refresh")
async def refresh_token_endpoint(
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
) -> TokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="No refresh token")
    try:
        new_raw, user_id = await rotate_refresh_token(
            db, refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
        )
    except ValueError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=str(exc)) from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found")
    await db.commit()

    access_token = create_access_token(
        sub=str(user.id), role="hc", hc_id=str(user.id),
        private_key=settings.jwt_private_key,
    )
    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
) -> dict:
    if refresh_token:
        await revoke_token(db, refresh_token)
        await db.commit()
    _clear_refresh_cookie(response)
    return {"status": "logged_out"}
```

- [ ] **Step 2: Register auth router in main.py**

Add to `backend/src/main.py` (after the existing imports):

```python
from .auth.router import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/auth/router.py backend/src/main.py
git commit -m "feat(auth): Google OAuth callback, refresh rotation, logout endpoints"
```

---

### Task P2.6: Auth integration tests

**Files:**
- Create: `backend/tests/integration/test_auth.py`

- [ ] **Step 1: Write auth integration tests**

```python
# backend/tests/integration/test_auth.py
"""Auth flow integration tests. Per ADR-0005 P2 acceptance criteria."""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AuthRefreshToken, User
from src.auth.jwt_utils import decode_access_token, AuthError
from src.config import settings

# Test keys — same pair as test_jwt_utils.py
TEST_PRIVATE_KEY = """<same private key>"""
TEST_PUBLIC_KEY = """<same public key>"""


@pytest.fixture(autouse=True)
def patch_jwt_keys(monkeypatch):
    monkeypatch.setattr(settings, "jwt_private_key", TEST_PRIVATE_KEY)
    monkeypatch.setattr(settings, "jwt_public_key", TEST_PUBLIC_KEY)


@pytest.mark.asyncio
async def test_protected_endpoint_no_token():
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/clients/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_expired_token():
    from src.main import app
    from src.auth.jwt_utils import create_access_token
    expired = create_access_token(
        sub=str(uuid.uuid4()), role="hc", hc_id=str(uuid.uuid4()),
        private_key=TEST_PRIVATE_KEY, ttl_seconds=-1,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/clients/",
                                    headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(db_session: AsyncSession):
    """Rotate once → new token works; old token rejected."""
    from src.auth.refresh import issue_refresh_token, rotate_refresh_token

    user = User(email=f"refresh-{uuid.uuid4()}@test.com",
                google_sub=f"g-refresh-{uuid.uuid4()}")
    db_session.add(user)
    await db_session.flush()

    raw = await issue_refresh_token(db_session, user.id)
    new_raw, user_id = await rotate_refresh_token(db_session, raw)
    assert user_id == user.id

    # Old token should be rejected
    with pytest.raises(ValueError, match="revoked"):
        await rotate_refresh_token(db_session, raw)


@pytest.mark.asyncio
async def test_refresh_token_replay_revokes_all(db_session: AsyncSession):
    """Present old token after rotation → all sessions revoked (replay detection)."""
    from src.auth.refresh import issue_refresh_token, rotate_refresh_token

    user = User(email=f"replay-{uuid.uuid4()}@test.com",
                google_sub=f"g-replay-{uuid.uuid4()}")
    db_session.add(user)
    await db_session.flush()

    raw = await issue_refresh_token(db_session, user.id)
    await rotate_refresh_token(db_session, raw)  # legitimate rotation

    # Attacker presents the original token again (replay)
    with pytest.raises(ValueError, match="replay"):
        await rotate_refresh_token(db_session, raw)

    # All refresh tokens for user should now be revoked
    tokens = (await db_session.execute(
        select(AuthRefreshToken)
        .where(AuthRefreshToken.user_id == user.id,
               AuthRefreshToken.revoked_at.is_(None))
    )).scalars().all()
    assert len(tokens) == 0


@pytest.mark.asyncio
async def test_logout_revokes_token(db_session: AsyncSession):
    from src.auth.refresh import issue_refresh_token, revoke_token

    user = User(email=f"logout-{uuid.uuid4()}@test.com",
                google_sub=f"g-logout-{uuid.uuid4()}")
    db_session.add(user)
    await db_session.flush()

    raw = await issue_refresh_token(db_session, user.id)
    await revoke_token(db_session, raw)
    await db_session.flush()

    token_hash = __import__("hashlib").sha256(raw.encode()).hexdigest()
    result = await db_session.execute(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one()
    assert token.revoked_at is not None
```

- [ ] **Step 2: Run auth integration tests**

```bash
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test \
  uv run pytest tests/integration/test_auth.py -v
```
Expected: all tests PASS (except `test_protected_endpoint_*` which require the `/api/clients/` route — that comes in P3; skip those with `pytest.mark.skip` if P2 testing fails on missing routes).

- [ ] **Step 3: Commit**

```bash
cd ..
git add backend/tests/integration/test_auth.py
git commit -m "test(auth): refresh rotation, replay detection, logout integration tests"
```

---

## P2 verification

- [ ] HC sign-in flow: `GET /api/auth/google/start` returns `auth_url`
- [ ] Access token decoded at jwt.io shows `sub`, `role`, `hc_id`, `iss`, `exp` per ADR-0005 §3
- [ ] `POST /health` with no JWT → 401
- [ ] `POST /health` with expired JWT → 401
- [ ] Refresh rotation: old token rejected on second use
- [ ] Logout: `revoked_at` set in DB
- [ ] Replay detection: all sessions revoked when stale token reused
- [ ] `grep -r "httpx.AsyncClient(" backend/src | grep -v http.py` → empty (all httpx usage goes through factory)

**STOP. Session ends at P2. Update SESSION_LOG.md before closing.**

---

## Session log entry (write at end of session)

Add to `docs/SESSION_LOG.md`:

```markdown
## 2026-04-30 — P0 / P1 / P2: Scaffold, Data Layer, Auth

**Done**:
- P0: git init, pyproject.toml, wrangler.toml, docker-compose, env files, FastAPI health check, telemetry scaffolding (scrub/logger/sentry), http factory
- P1: 16-table SQLAlchemy models, async session factory, Alembic initial migration, roundtrip + cascade delete tests
- P2: ES256 JWT utilities, Google OAuth PKCE flow, refresh token rotation with replay detection, require_role + current_tenant dependencies, auth endpoints

**Decided**:
- ADR-0003 flipped to Accepted; llm_calls schema reconciled (model_requested/model_served/prompt_version/request_id added)
- auth_refresh_tokens added to data model diagram (was missing)
- retired_at added to hc_style_snippets
- circular FK (moms/briefs → llm_calls) handled via deferred op.create_foreign_key()

**Pending / next session**:
- P3: Domain CRUD endpoints (clients, sessions, moms, action items, check-ins)
- Install Postgres MCP (read-only) per starter_prompt instructions

**Context the next session needs**:
- Run P0/P1/P2 verification checklists first; fix any failures before P3
- P3 source docs: diagrams/0002-data-model.md, domain/glossary.md, domain/actors.md
```

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-04-30 | Initial plan written. | Session start: P0 → P1 → P2 per starter_prompt_01.md. |
