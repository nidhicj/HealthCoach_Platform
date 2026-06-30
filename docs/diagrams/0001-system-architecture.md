# System Architecture (Diagram + Description)

> **MERGE-REQUIRED**: existing diagram in repo from prior session contained n8n + outdated hosting. This is a fresh description aligned with ADR-0001/0002/0003. The actual visual diagram lives on Miro (link in References); this markdown is the textual companion.

---

## Architecture at a glance

```
┌───────────────────────────────────────────────────────────────────────┐
│                          CLIENT (HC's browser)                        │
│   All fetch() calls are same-origin → /api/* (no cross-origin reqs)  │
└──────────────────────────────────┬────────────────────────────────────┘
                                   │ HTTPS (same-origin)
                                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│               GCP Cloud Run — asia-south1 (Mumbai)                    │
│               hc-platform-frontend  (Next.js 16)                      │
│                                                                       │
│  ┌─ BFF Proxy — app/api/[...path]/route.ts ────────────────────────┐  │
│  │   Catches all /api/* from browser; proxies server-to-server     │  │
│  │   to hc-platform-backend. For OAuth callback (302 + Set-Cookie) │  │
│  │   re-emits cookie on the frontend domain so it is first-party   │  │
│  │   in Chrome, Firefox (dFPI), and Safari (ITP).                  │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
└──────────────────────────────────┼───────────────────────────────────┘
                                   │ HTTPS (server-to-server, no browser)
                                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│               GCP Cloud Run — asia-south1 (Mumbai)                    │
│               hc-platform-backend  (FastAPI, Python 3.12)             │
│                                                                       │
│  · /api/auth/*  · /api/clients  · /api/sessions  · /internal/*       │
│  Scales to zero; free tier at MVP; same Docker image as local dev     │
└────────┬──────────────────────┬───────────────────┬───────────────────┘
         │                      │                   │
         │ DB queries            │ R2 read/write     │ HTTPS (httpx async)
         ▼                      ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│ Supabase         │  │ Cloudflare R2    │  │  OpenRouter (gateway)    │
│ Postgres         │  │ (global CDN,     │  │  ↓                       │
│ ap-south-1       │  │ zero egress)     │  │  Llama 3.3 → Gemma 3 →   │
│ Mumbai (free)    │  │                  │  │  GPT-OSS → Nemotron      │
│                  │  │ Session notes,   │  │  (pinned chain, free)    │
│ users, clients,  │  │ MOM exports,     │  │                          │
│ sessions, moms,  │  │ client file lib, │  │  DeepSeek R1 (escape     │
│ briefs, snippets,│  │ consent PDFs     │  │  hatch, app-invoked)     │
│ llm_calls,       │  │                  │  │                          │
│ consents...      │  │                  │  │                          │
└──────────────────┘  └──────────────────┘  └──────────────────────────┘

EXTERNAL SCHEDULER (GitHub Actions cron — every 4 days: Supabase keep-alive)
                     (GitHub Actions cron — daily: snippet retirement, scheduled tasks)
   │
   └─→ HTTPS POST → hc-platform-backend /internal/* (X-Scheduler-Token auth)
       (calls backend directly — no browser/cookie involved, no need for BFF proxy)

OBSERVABILITY
   Sentry (errors) ← FastAPI + frontend
   GCP Cloud Logging → structured JSON logs from Cloud Run
   llm_calls table → SQL-queryable cost & quality dashboard (Supabase SQL editor)

ZOOM (HC's existing tool, unchanged)
   Zoom hosts session
   ↓
   Zoom AI Companion generates summary
   ↓
   HC uploads summary file via client file library → stored in R2, fed to LLM
```

---

## Component summary

| Component                  | Tech                                                   | Where                                            | Notes                                                                                                                                  |
| -------------------------- | ------------------------------------------------------ | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend (BFF)             | Next.js 16 App Router, TypeScript, Tailwind, shadcn/ui | GCP Cloud Run`asia-south1` (Mumbai)            | Serves HC UI;`app/api/[...path]/route.ts` proxies all `/api/*` server-to-server to the backend — cookie always on frontend domain |
| Backend                    | FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2     | GCP Cloud Run`asia-south1` (Mumbai) — primary | Containerised Docker; scales to zero; full Python ecosystem                                                                            |
| Backend fallback           | Same FastAPI Docker image                              | DigitalOcean Bangalore Droplet                   | Activated on ADR-0001 Cloud Run hosting triggers                                                                                       |
| Database                   | Postgres (managed)                                     | Supabase free tier,`ap-south-1` (Mumbai)       | 500 MB free; keep-alive via GH Actions cron; upgrade path: Supabase Pro $25/mo                                                         |
| Object storage             | S3-compatible                                          | Cloudflare R2 (global, zero egress)              | Session notes mirror, client file library, consent PDFs. No India-region pin at MVP.                                                   |
| LLM gateway                | OpenRouter (HTTP, OpenAI-compatible)                   | Cloud Run → OpenRouter → upstream providers    | Pinned free-model chain via`models` array                                                                                            |
| Scheduler                  | GitHub Actions cron                                    | External                                         | Hits Cloud Run`/api/jobs/*` endpoints; also runs Supabase keep-alive                                                                 |
| Auth                       | Backend-issued JWT, Google OAuth                       | Cloud Run                                        | Owned implementation; standard httpx (no platform-specific workarounds needed)                                                         |
| Observability              | Sentry + GCP Cloud Logging +`llm_calls` table        | Mixed                                            | Sentry for errors, Cloud Logging for structured app logs, Supabase for LLM telemetry                                                   |
| Edge protection (frontend) | Cloudflare platform features                           | Cloudflare dashboard                             | Rate limit, WAF, cache rules, DDoS — for Cloudflare Pages layer                                                                       |

---

## Request flow examples

### Example 1: HC signs in (OAuth flow)

1. HC clicks "Sign in with Google" → browser `fetch("/api/auth/google/start")` (same-origin)
2. Frontend BFF Route Handler: server-to-server `GET {backend}/api/auth/google/start` → returns `{auth_url}`
3. Browser: `window.location = auth_url` → navigates to Google OAuth
4. HC approves → Google redirects browser to `{frontend_url}/api/auth/google/callback?code=...`
5. Frontend BFF Route Handler: server-to-server `GET {backend}/api/auth/google/callback?code=...` with `redirect: 'manual'`
6. Backend: validates PKCE, creates/updates user, issues refresh token → responds 302 + `Set-Cookie`
7. Route Handler: copies `Set-Cookie` to redirect response → browser sees cookie on `hc-platform-frontend-*.run.app` ← key: cookie now first-party
8. Browser: follows 302 to `/auth/callback`, sends cookie with next request (same-origin, works in Chrome + Firefox + Safari)
9. `/auth/callback` page: `POST /api/auth/refresh` → Route Handler → backend validates cookie → returns `{access_token}`
10. Dashboard loads

### Example 2: HC reviews MOM after a session

1. HC's browser: `GET /api/sessions/{id}/mom` (with JWT Bearer, same-origin)
2. Frontend BFF Route Handler: server-to-server request to `{backend}/api/sessions/{id}/mom`
3. Backend (FastAPI): JWT validation, tenant scope check (`hc_user_id` matches)
4. Backend: queries Supabase for session + draft MOM
5. Returns JSON through Route Handler to browser
6. Frontend: renders MOM with edit affordances
7. HC edits, hits Send → `POST /api/sessions/{id}/mom/send` through same BFF path
8. Backend: diffs original draft vs. final, writes diff as snippet (if material)
9. Backend: marks MOM as `sent`, writes `llm_calls` row

### Example 3: Pre-session brief generation (scheduled job)

1. External scheduler (GitHub Actions cron): HTTPS POST directly to `{backend_url}/internal/scheduled-tasks` — bypasses BFF (server-to-server, no cookie, X-Scheduler-Token auth)
2. Backend: enumerates upcoming sessions in next 24h
3. For each: fetches client history, recent check-ins, open action items, top-N snippets
4. Assembles prompt, calls OpenRouter with `models` array
5. OpenRouter: tries Llama 3.3 70B first; on throttle/error, falls through chain
6. Receives response, validates against Pydantic schema
7. On validation failure: re-prompt with stricter format hint (1 retry)
8. Writes draft brief to Supabase, writes `llm_calls` row with telemetry

---

## Migration paths (per ADR-0002)

| Trigger fires                                              | Response                                             |
| ---------------------------------------------------------- | ---------------------------------------------------- |
| Cloud Run cold start p95 > 3s (sustained)                  | Add`min-instances: 1` on Cloud Run (~$10/mo extra) |
| Cloud Run monthly cost > $25                               | Migrate backend to DO Bangalore flat-rate droplet    |
| GCP Cloud Run outages > 2/30d                              | Migrate backend to DO Bangalore                      |
| Supabase DB approaching 450 MB                             | Upgrade to Supabase Pro ($25/mo)                     |
| Supabase MAU approaching 45 K                              | Upgrade to Supabase Pro ($25/mo)                     |
| Free-model LLM quality fails (per ADR-0001 triggers 7–10) | Switch model IDs to paid Claude via OpenRouter       |

---

## What's NOT in this architecture

- **n8n**: removed. All automation is Python in the FastAPI app.
- **Anthropic SDK direct**: replaced with OpenRouter HTTP integration.
- **APScheduler**: not used. External scheduler (GitHub Actions) keeps background-job concerns outside the web process.
- **Vercel**: not used. Frontend is on Cloud Run.
- **Cloudflare Pages**: eliminated Jun 2026 — Next.js 16 App Router with dynamic routes cannot statically export. Replaced by Cloud Run.
- **Cloudflare Python Workers**: eliminated Jun 2026 — FastAPI not supported. Replaced by Cloud Run.
- **Cloudflare WAF / rate limiting on frontend**: not configured (CF Pages removed). Cloud Run does not include a WAF layer. Deferred to custom domain stage — add GCP Cloud Armor or CF as reverse proxy when domain is set up.
- **AWS RDS Mumbai**: replaced by Supabase free tier (same India region, zero provisioning cost at MVP).
- **AWS S3 Mumbai**: replaced by Cloudflare R2 (zero egress cost) — see ADR-0001 changelog 2026-05-05.
- **Redis at MVP**: no, not needed. Added when PKCE state store or Celery introduced at scale.
- **In-app client login**: deferred (clients don't directly use the platform at MVP).
- **Cross-origin direct browser→backend calls**: eliminated Jun 2026. All browser API calls go through the Next.js BFF Route Handler (same-origin). The backend is not directly reachable by the browser at any point in the production auth or data flow.

---

## References

- `decisions/0001-stack-selection.md`
- `decisions/0002-runtime-topology.md`
- `decisions/0003-llm-strategy.md`
- `decisions/0004-repo-structure.md`
- `diagrams/0002-data-model.md`
- Miro board: https://miro.com/app/board/uXjVIM847Lg=/

---

## Changelog

| Date       | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-06-24 | Frontend moved from Cloudflare Pages to GCP Cloud Run (was documented in 2026-06-19 changelog but ASCII diagram still showed CF Pages — corrected now). Added BFF proxy pattern: Next.js`app/api/[...path]/route.ts` catches all `/api/*` from browser and proxies server-to-server to the backend. Reason: `run.app` is in the Public Suffix List; frontend and backend are cross-site; Firefox (dFPI) and Safari (ITP) block third-party cookies. Proxy makes all browser calls same-origin so refresh cookie is first-party. Updated: ASCII diagram, component table, request flow examples (added OAuth sign-in flow, updated MOM review and scheduler examples), "What's NOT here." ADR-0005 amended same date. |
| 2026-06-19 | Hosting updated: CF Python Workers → GCP Cloud Run`asia-south1`. DB updated: AWS RDS Mumbai → Supabase free tier (Mumbai). Object storage was already R2 (May 2026). Migration paths table rewritten for Cloud Run triggers. Component table updated. "What's NOT here" updated. ASCII diagram redrawn.                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 2026-04-28 | Fresh description aligned with current ADRs. MERGE-REQUIRED — old repo version had n8n.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
