# ADR-0006: Observability

**Status**: Accepted
**Date**: 2026-04-29
**Decision driver**: SoJo (architect-authored draft for SoJo review)
**Supersedes**: n/a
**Relates to**: ADR-0001 (locks Sentry + structured logs + `llm_calls` at high level), ADR-0003 (defines `llm_calls` schema), ADR-0005 (auth events are part of the observability surface)

---

## Context

ADR-0001 settled the high-level posture: **Sentry + structured logs + custom `llm_calls` telemetry**. It did not settle the strategy — what we log, what we redact, how we correlate, what alerts fire when, what dashboards exist. This ADR settles those.

Three things must be observable from day one:

1. **Errors and exceptions** — anything that crashes a request, an LLM call, a job, or a migration.
2. **Behavior** — who hit which endpoint, how long it took, what JWT identified them, what tenant they belonged to.
3. **LLM calls** — the cost-and-quality dimension that uniquely defines this product. Per ADR-0003, every LLM call writes a row to `llm_calls`.

Constraints already locked:

- Cloudflare Workers runtime → Cloudflare Workers Logs is the native log destination
- Sentry is the chosen error platform per ADR-0001
- `llm_calls` schema is defined in ADR-0003 §4 and `diagrams/0002-data-model.md`
- DPDP Act 2023 → personal data must not appear in third-party log services. Sentry's free tier hosts data outside India; therefore PII redaction is non-negotiable, not optional.
- The product handles health-related conversations → snippet content and transcript content are sensitive and must never enter logs

What's at stake if this is done wrong: silent errors (you ship a broken feature and the pilot HC encounters it before you do), uncaught LLM cost regressions (a model migration doubles your spend and you find out next month), DPDP exposure (PII ends up in Sentry breadcrumbs), inability to debug (an HC reports a problem and there's no trace to follow).

---

## Options considered

### Option A: Sentry (errors) + Cloudflare Workers Logs (structured logs) + `llm_calls` (custom telemetry)

The ADR-0001 default. Three separate systems each doing what they're best at.

- **Pros**: Sentry's free tier (5K errors/month, 90-day retention) is more than enough for pilot; Cloudflare Workers Logs is already there with no extra cost; `llm_calls` is the only place LLM-specific data should live (cost in INR, validation flag, fallback count — none of that fits a generic log line cleanly).
- **Cons**: three systems to query when debugging. Cross-references happen via `request_id` correlation, which works but takes discipline.
- **Cost**: ₹0/mo at pilot scale. Sentry paid tier kicks in past 5K errors/mo (₹2,000–4,000/mo region) — well past pilot.

### Option B: Datadog or Grafana Cloud (unified)

One platform for traces, logs, errors, metrics.

- **Pros**: one query interface; powerful correlation; good dashboards out of the box.
- **Cons**: cost is the killer — Datadog starts at $15/host/month for APM, log ingestion adds up fast at any volume. Grafana Cloud free tier is more generous but requires more setup. At pilot scale, both are overkill. At 50+ HC scale, worth re-evaluating.
- **Cost**: ₹2,000–10,000/mo even at pilot scale, depending on log volume.

### Option C: Cloudflare-only

Cloudflare Workers Logs + Cloudflare Logpush + custom dashboards in Cloudflare Analytics.

- **Pros**: single vendor, native, no PII-leaves-India concern.
- **Cons**: error tracking inside CF Logs is text-grep (no fingerprinting, no occurrences-over-time UI, no notification rules out of the box). You'd build a worse Sentry yourself.
- **Cost**: ₹0/mo extra. Real cost is the dashboards you'd have to build.

### Option D: Self-hosted (PostgreSQL + Grafana + Loki)

Roll your own.

- **Pros**: full control, India-region.
- **Cons**: operationally heavy for one person.
- **Cost**: server time to maintain — too high.

---

## Decision

**Option A.** Sentry for errors; Cloudflare Workers Logs for structured request/job logs; `llm_calls` table for LLM-specific telemetry. Everything correlated by `request_id`.

Specifics below. Claude Code implements per this ADR; deviations require ADR amendment.

### 1. Errors → Sentry

**Backend SDK**: `sentry-sdk[fastapi]`. Initialize in `backend/src/telemetry/sentry.py` with:

- `dsn`: from env var `SENTRY_DSN`
- `environment`: `production` | `staging` | `dev` from `APP_ENV`
- `release`: git SHA, injected at deploy time
- `traces_sample_rate`: 0.0 at MVP (we use Cloudflare Logs for performance; Sentry tracing adds cost without proportional value at this stage)
- `profiles_sample_rate`: 0.0
- `send_default_pii`: **False** — non-negotiable
- `before_send`: a function that scrubs the event payload (see §3 below)
- `before_breadcrumb`: same scrubbing applied to breadcrumbs

**Frontend SDK**: `@sentry/nextjs`. Same DSN with separate project, or two projects under one org — separate projects preferred so frontend errors don't drown backend errors. Same `send_default_pii=False` and scrubbing rules.

**What gets sent**: unhandled exceptions, explicit `sentry_sdk.capture_exception()` calls, and `sentry_sdk.capture_message()` for security events (refresh token replay detected, JWT signature mismatch from a known-good user, etc.).

**What doesn't get sent**: 4xx client errors (these are logs, not errors — a 401 isn't a bug). 404 on legitimate not-found is a log, not a Sentry event.

### 2. Structured logs → Cloudflare Workers Logs

**Format**: JSON, one object per log line. Required fields on every line:

```json
{
  "ts": "2026-04-29T08:14:22.481Z",
  "level": "info | warn | error",
  "request_id": "<uuid>",
  "user_id": "<uuid> | null",
  "hc_id": "<uuid> | null",
  "role": "hc | client | admin | anon",
  "event": "auth.refresh.success | api.session.create | llm.call.start | ...",
  "ms": <duration_ms>,
  "ip": "<obfuscated, see §3>",
  "ua": "<truncated to 200 chars>",
  "extra": { /* event-specific fields, scrubbed */ }
}
```

**Levels**:

- `info`: every request (start + end), every successful auth event, every LLM call start/end, every job run.
- `warn`: recoverable problems — LLM validation failure that succeeded on retry, refresh token expired (not an error), rate-limit-near events.
- `error`: anything that fails a request or a job.

**`event` namespacing**: dot-separated, lowercase. Convention: `<area>.<noun>.<verb>` (e.g., `auth.refresh.success`, `llm.call.fail`, `mom.draft.generate`). Enforced by code review; a future linter can validate.

**Implementation**: `backend/src/telemetry/log.py` exports a `get_logger(request_id, user_id, hc_id, role)` function that returns a logger with those fields bound. FastAPI middleware creates one logger per request and stashes it in request state. Workers' built-in `console.log` outputs go to Workers Logs as JSON when `console.log(JSON.stringify(obj))` is used — Python equivalent is `print(json.dumps(obj))` from inside the Worker. Use `structlog` or a thin wrapper for ergonomics.

### 3. PII redaction (non-negotiable)

Personal data that **must never** appear in Sentry or Cloudflare Logs:

| Field                                                       | Why it's PII                            | How to handle                                                                                                                                                                    |
| ----------------------------------------------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Email address                                               | Direct identifier                       | Replace with `<email_redacted>` in any logged value; in Sentry breadcrumbs, scrub via `before_breadcrumb`                                                                    |
| Phone number                                                | Direct identifier                       | Same                                                                                                                                                                             |
| Full name                                                   | Direct identifier                       | Same                                                                                                                                                                             |
| `users.id` (UUID)                                         | Indirect — but only meaningful with DB | OK to log (it's an opaque UUID; resolving to a person requires DB access which is auth-gated)                                                                                    |
| `hc_id` (UUID)                                            | Same                                    | OK to log                                                                                                                                                                        |
| Session transcript content                                  | Health disclosures                      | **Never** logged. Prompt and completion text are stored in `llm_calls.prompt_text` and `llm_calls.completion_text` per §5 below — pseudonymized at assembly (clients referenced by `clients.code`, e.g. `CP0001`, never by name/email/phone), encrypted at rest via `pgcrypto`, and never written to any log line in any form (not even truncated previews)  |
| Snippet content (`hc_style_snippets.original_text`, etc.) | HC's voice, may contain client info     | Never logged. References by `id` only                                                                                                                                          |
| MOM content                                                 | Health summary                          | Never logged. References by `id` only                                                                                                                                          |
| JWT tokens (any)                                            | Credential                              | Never logged. Header values containing `Authorization` are stripped                                                                                                            |
| Refresh tokens (any form)                                   | Credential                              | Never logged                                                                                                                                                                     |
| IP address                                                  | Personal data under DPDP                | Logged in**truncated** form: IPv4 → `/24` (last octet zeroed); IPv6 → `/48` (zero remaining bits). Enough for geographic debugging, not enough for re-identification |
| User-Agent                                                  | Low-risk; useful for debugging          | Logged; truncated to 200 chars                                                                                                                                                   |

**Implementation**: a single function `scrub(event_or_log)` in `backend/src/telemetry/scrub.py` applied to:

- Sentry's `before_send` and `before_breadcrumb`
- A wrapper around the JSON logger that runs every log line through `scrub` before emission

The function uses (a) a denylist of known-PII keys (`email`, `phone`, `name`, `password`, `token`, `secret`, `authorization`, `cookie`, `transcript`, `mom_content`, `snippet_content`, `original_text`, `hc_modified_text`, `prompt_text`, `completion_text`), (b) a regex for email-like patterns, (c) a regex for things that look like JWTs (`eyJ...`), (d) IP truncation.

**Verification (per build-plan P8 acceptance criteria)**:

- Force a deliberate exception in dev that includes a logged user's email → confirm email does not appear in Sentry event
- `grep -r "snippet" cloudflare_logs.json` returns empty over a sample window

### 4. Request correlation: `X-Request-ID`

Every inbound request gets a `request_id` (UUID v4). FastAPI middleware:

1. Reads `X-Request-ID` from inbound headers; if absent, generates one
2. Sets `request.state.request_id`
3. Adds it to every log line for this request via the bound logger
4. Sets it on Sentry's scope (`sentry_sdk.set_tag("request_id", ...)`)
5. Writes it to `llm_calls.request_id` for any LLM call made during the request
6. Echoes it in the response header `X-Request-ID` so the frontend can include it in any user-reported bug

Frontend captures the response header and includes it in any error report or feedback form. Same UUID stitches Sentry → Cloudflare Logs → `llm_calls` together.

### 5. LLM telemetry → `llm_calls` table

Schema is in ADR-0003 §4 and `diagrams/0002-data-model.md`. This ADR specifies **what writes to it and when**.

**Write path**: every LLM call goes through `backend/src/llm/client.py`'s `complete()` function. That function:

1. Captures `started_at`
2. Sets `request_id` from request context
3. Sets `hc_id`, `prompt_version`, `model_id_attempted` (the first model in the chain)
4. Calls OpenRouter via httpx (with `User-Agent` per ADR-0001)
5. On success: captures `model_id_actual` (the model that responded), `input_tokens`, `output_tokens`, `latency_ms`, `inr_cost_estimate`
6. On Pydantic validation failure: sets `validation_failed=true`, retries once with stricter prompt; if that fails, fails the request (and writes a single row with `validation_failed=true`, `output_tokens` from the bad attempt)
7. On chain fallback: increments `fallback_count`, retries with next model
8. Writes the row

**Prompt and completion text storage in `llm_calls`** — amended 2026-05-04 (see Changelog). The original rule ("never write the prompt or response text into `llm_calls`") is superseded. Prompt text and completion text **are** written to `llm_calls.prompt_text` and `llm_calls.completion_text` under three non-negotiable protections:

1. **Pseudonymization at prompt assembly.** Every prompt template references clients by `clients.code` (the per-HC `CP<NNNN>` identifier), never by `clients.full_name`, email, or phone. The prompt-assembly module is the single chokepoint where this is enforced. Templates that interpolate identifying fields are a defect; a unit test asserts no client-name strings (regex: capitalized words matching live `clients.full_name` values) appear in any stored `prompt_text` row. The mapping `code → identity` lives only in the `clients` table, tenant-scoped per ADR-0005.
2. **Column-level encryption at rest.** Both columns use PostgreSQL `pgcrypto` (`pgp_sym_encrypt` / `pgp_sym_decrypt`) with a single platform-wide key referenced by env var `LLM_CALL_ENCRYPTION_KEY`. Backups, replicas, and any disclosure short of the running app cannot read the content without the key. Key rotation is out of scope for P4 — defer.
3. **Tenant scoping on all reads.** Same pattern as P3 domain reads: every query that decrypts `prompt_text` or `completion_text` filters by `hc_id` from the JWT. Cross-tenant decryption is impossible by construction. A failing integration test must demonstrate that HC2 cannot decrypt HC1's `llm_calls` rows.

**Why amended**: the original rule assumed prompt/completion text was recoverable from prompt files (in git) and `moms.draft_text`. In practice, the deployed prompt is template + injected snippets + injected client context, where the injected pieces are not preserved anywhere; and `moms.draft_text` is overwritten by HC edits, destroying the original LLM output. Without storing both, "the AI is acting weird" complaints from HCs are not diagnosable. Product credibility with HCs requires this debuggability; the three protections above keep DPDP scope manageable while preserving it. See ADR-0006 Changelog 2026-05-04 for the full rationale.

**Critical: never log the prompt or completion text** — neither truncated previews nor full text appear in Sentry events, breadcrumbs, or Cloudflare Workers Logs. The `scrub()` denylist (§3) explicitly includes `prompt_text` and `completion_text` keys. The storage protections above apply only to the `llm_calls` table; logs remain content-free.

### 6. Sampling

- **Errors (Sentry)**: 100%. We're at pilot scale; every error matters.
- **Structured logs**: 100% at INFO+ during pilot. Drop to 10% sampling on `info` (keep 100% on `warn`/`error`) when monthly Workers Logs ingest exceeds the free tier — revisit when that triggers.
- **LLM calls**: 100%. There won't be enough volume for sampling to matter for years.

### 7. Alert rules

Configured in Sentry's UI (or Sentry alert rules YAML if we adopt that):

- **Any new error fingerprint**: notify (email to SoJo) within the hour. New = first occurrence of this fingerprint in the environment.
- **Error rate > 5/hour for the same fingerprint**: escalate (email + future PagerDuty hook). Indicates a real issue, not a one-off.
- **Any `kind=llm_validation_failed` warning during pilot**: same-day review. The free-model chain is brittle (per ADR-0001 risk #8); SoJo wants eyes on every validation failure during pilot to catch prompt regressions early.
- **Daily LLM cost in INR > daily budget**: notify. Budget set per environment (default ₹500/day at pilot; tune after first month of data).

The alert rules are configured manually in the Sentry UI at deploy time; the configuration is documented in `docs/ops/incident-response.md` (already in repo per file listing).

### 8. Dashboards: 5 SQL queries against `llm_calls`

These run as ad-hoc queries during pilot; promoted to a real dashboard tool (Grafana? Metabase?) post-pilot. Querying directly against RDS is fine at this volume.

```sql
-- 1. Daily LLM cost in INR (rolling 14 days)
SELECT 
    DATE(created_at) AS day,
    SUM(inr_cost_estimate) AS cost_inr,
    COUNT(*) AS calls
FROM llm_calls
WHERE created_at >= NOW() - INTERVAL '14 days'
GROUP BY day
ORDER BY day DESC;

-- 2. Latency p50/p95 by model (last 7 days)
SELECT 
    model_id_actual,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
    COUNT(*) AS calls
FROM llm_calls
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY model_id_actual
ORDER BY calls DESC;

-- 3. Validation failure rate by prompt version (last 7 days)
SELECT 
    prompt_version,
    COUNT(*) FILTER (WHERE validation_failed) * 100.0 / COUNT(*) AS fail_pct,
    COUNT(*) AS total_calls
FROM llm_calls
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY prompt_version
ORDER BY fail_pct DESC;

-- 4. Fallback distribution (how often does the primary model serve?)
SELECT 
    fallback_count,
    COUNT(*) AS calls,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM llm_calls
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY fallback_count
ORDER BY fallback_count;

-- 5. Per-HC cost and call volume (last 30 days)
SELECT 
    hc_id,
    COUNT(*) AS calls,
    SUM(inr_cost_estimate) AS cost_inr,
    AVG(latency_ms) AS avg_latency_ms
FROM llm_calls
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY hc_id
ORDER BY cost_inr DESC;
```

These are exercised at P8 (acceptance criterion: "Run all 5 dashboard SQL queries against pilot data").

### 9. Retention

| Data                    | Retention                   | Rationale                                                                          |
| ----------------------- | --------------------------- | ---------------------------------------------------------------------------------- |
| Sentry errors           | 90 days (free tier default) | Enough for pilot debug cycles                                                      |
| Cloudflare Workers Logs | 7 days (free tier)          | Enough for daily debug; if we need longer, set up Logpush to S3 Mumbai             |
| `llm_calls`           | 1 year                      | Cost analysis and quality trending across model migrations needs longitudinal data |
| `audit_log`           | 7 years post user-deletion  | DPDP grievance / dispute resolution may require longer; conservative default       |

`llm_calls` and `audit_log` retention are enforced by a scheduled job (P7 phase). At pilot, deletion happens manually until the scheduler exists.

### 10. What this ADR does NOT cover

- Frontend RUM (real user monitoring) beyond error capture — deferred.
- Synthetic uptime monitoring (e.g., `scripts/smoke-test.py` running on a cron) — partially covered by build-plan P9; expand later.
- Distributed tracing — not needed with one backend service. Revisit if we split.
- A/B testing telemetry — out of scope.

---

## Consequences

### Positive

- Three signals (errors, behavior, LLM cost) each in the right place.
- `request_id` correlation makes debugging tractable: an HC reports a bug → SoJo asks for the request ID from the response → traces it across all three systems.
- PII redaction is centralized in one `scrub()` function — easy to review, hard to forget if the scaffolding wires it correctly.
- `llm_calls` queries answer the most important product questions (cost, latency, quality regression) without adding tooling.
- DPDP posture is defensible: PII never leaves India in the logging path because PII never enters the logging path.

### Negative / tradeoffs accepted

- Three systems to query when debugging. Mitigated by `request_id` propagation but real friction.
- No distributed tracing means debugging multi-step LLM workflows (e.g., snippet selection → prompt assembly → LLM call → validation → DB write) requires reading log lines in chronological order. Acceptable at pilot complexity.
- `before_send` scrubbing in Sentry is a single point of failure — a bug there leaks PII. Tested by the verification step at P8 (deliberate exception with PII → confirm scrubbed) and by a unit test that runs sample events through `scrub()` and asserts no PII fields remain.
- Free tier limits will eventually hit. Cloudflare Workers Logs free tier limits are the more likely bottleneck than Sentry — when that happens, evaluate Logpush to S3 vs paid tier.
- Manual alert rule configuration in Sentry UI is not version-controlled. Document in `incident-response.md` as a workaround; revisit if alerts get complex enough to warrant Sentry's alert-rules-as-code feature.

### Things to revisit

- **Sampling**: when monthly log volume exceeds free tier, drop info-level sampling first.
- **Tracing**: when we add a second backend service, evaluate Sentry tracing or Cloudflare Trace Workers.
- **Alert escalation**: post-pilot, hook PagerDuty or equivalent.
- **Dashboard tool**: Metabase or Grafana for the 5 SQL queries when pilot ends.
- **PII scrubbing audit**: 90 days post-launch, do a privileged review of one week of logs and Sentry events specifically looking for PII leaks. Iterate the scrub function.

### Required follow-on actions (after Acceptance)

1. **Update `domain/compliance-india.md`** to reference this ADR's PII redaction approach as the technical implementation of DPDP "data minimization" in observability.
2. **Add a unit test** for `scrub()` that asserts every PII field type (email, phone, JWT, transcript, snippet, IP, `prompt_text`, `completion_text`) is correctly redacted on a fixture event.
3. **Data model changes required (added 2026-05-04 amendment)** — `llm_calls` gains two encrypted columns (`prompt_text`, `completion_text`); `clients` gains a `code` column (per-HC `CP<NNNN>` sequence). Both land in P4 via Alembic migration. Schema delta and rationale are in ADR-0003 §4 (amended same date). Update `diagrams/0002-data-model.md` to reflect the new columns.
4. **Cross-tenant decryption test** (added 2026-05-04 amendment) — an integration test must demonstrate that HC2's JWT cannot decrypt HC1's `llm_calls.prompt_text` / `completion_text`, even given direct API access to those rows. This is the single test that proves the third protection (tenant-scoped reads).

---

## References

- ADR-0001 — Stack selection (locks Sentry + structured logs + `llm_calls`)
- ADR-0003 — LLM strategy (defines `llm_calls` schema in §4)
- ADR-0005 — Auth strategy (security events feed Sentry)
- `domain/compliance-india.md` — DPDP context
- `docs/build-plan.md` Phase 8 — acceptance criteria this ADR enables
- `docs/ops/incident-response.md` — already in repo; alert rules go here
- Sentry FastAPI integration: https://docs.sentry.io/platforms/python/integrations/fastapi/
- Cloudflare Workers Logs: https://developers.cloudflare.com/workers/observability/logs/workers-logs/
- DPDP Act 2023 — "data minimization" and "purpose limitation" obligations

---

## Changelog

| Date       | Change         | Reason                                                     |
| ---------- | -------------- | ---------------------------------------------------------- |
| 2026-04-29 | Initial draft. | Required by build-plan P8; defines observability strategy. |
| 2026-05-04 | Amendment: prompt and completion text **are** stored in `llm_calls.prompt_text` / `llm_calls.completion_text`, with three protections — pseudonymization at assembly (clients referenced by `clients.code`, never by name), column-level encryption via `pgcrypto`, tenant-scoped reads. Supersedes the §5 "never write the prompt or response text into `llm_calls`" rule and resolves the contradiction with §3 line 135. `scrub()` denylist extended with `prompt_text` and `completion_text` (these are stored, never logged). Required follow-on actions updated: data model changes are now required (see ADR-0003 §4 amendment, same date). | SoJo decision after weighing product-credibility-with-HCs against DPDP-scope. The original rule made "AI is acting weird" complaints undiagnosable because (a) deployed prompt = template + dynamic injections that aren't preserved elsewhere, (b) `moms.draft_text` is overwritten by HC edits, destroying the original LLM output. Pseudonymization + encryption + tenant scoping keep DPDP scope acceptable while restoring debuggability. |
