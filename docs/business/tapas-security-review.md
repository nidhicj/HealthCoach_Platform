# Tapas — Code-Level Security Review

> **Audience**: engineers. This is a technical companion to `docs/business/tapas-product-overview.md`, deliberately kept separate — no business/market content here, only security findings.
>
> **Written**: 2026-07-30. **Scope, as constrained by SoJo**: the *current agreed-upon state* across all 4 active worktrees (branches `feature/unit-003-client-discovery-pipeline`, `feature/unit-004-one-stop-spot`, `feature/unit-005-macro-calculator`, `feature/unit-006-platform-foundations`) — superseded decisions and abandoned trial-and-error approaches (e.g. Unit_004 SPEC-0001's struck-through D-5/D-7/D-8/D-9) are explicitly excluded. Where a unit has no code yet, the "finding" is a design-level threat model against its spec, not a code audit — labeled as such throughout.

---

## 1. Scope note — what's actually built vs. design-only, per worktree

| Worktree | What has code | What's design-only |
|---|---|---|
| `tapas_unit004` (this branch) | Unit_001 (auth, sessions, MOM/briefs, action items, check-ins, LLM service), Unit_002 (supplements), shipped Unit_004 slices (file uploads, action-items email, diet-chart send/versioning, calendar/meeting-link, client portal foundation) | Unit_004's remaining F2 (check-ins lifecycle, messaging), F3 (logged meals), F4 (payments) |
| `tapas_unit003` | Nothing unit-specific — `backend/src/api/*.py` listing is identical to the shared baseline; no `leads.py` exists | All of Unit_003 (lead-intake pipeline) |
| `tapas_unit005` | Nothing unit-specific — no `macro_calculator.py` exists; commit history is rename/merge/chore only | All of Unit_005 (macro formula engine) |
| `tapas_unit006` | Nothing unit-specific — no `settings.py` exists; one docs-only commit adding the spec | All of Unit_006 (settings/profile, deletion, consent, admin, monetization) |

This was verified directly (file listings + `git log`), not assumed from spec status labels. Only `tapas_unit004` gets a real code audit below; the other three get design-level threat models in §3.

---

## 2. Confirmed findings — current shipped code (`tapas_unit004`)

### 2.1 Auth / session

**[High] No rate limiting anywhere in the API.** `backend/src/main.py` registers only CORS and a request-id/logging middleware — no throttling on any route. `/api/auth/*` login and refresh endpoints are exposed to unlimited-rate credential-stuffing and token-guessing. This confirms, at the application layer, a gap already flagged at the infra layer in `docs/diagrams/0001-system-architecture.md` (WAF/rate-limiting placeholder, still not configured). Two separate layers with the same open gap.
**Fix before any real pilot traffic.**

**[High] `_not_empty_in_prod` validator is dead code.** `backend/src/config.py:43-46` — the field validator unconditionally `return v`s without checking anything, despite its name implying an enforcement check. `jwt_private_key`, `jwt_public_key`, and `database_url` all default to `""` with nothing stopping a misconfigured deploy (e.g. a missing GCP secret) from starting the app with an **empty JWT signing key**.
**Fix**: make the validator actually raise when `app_env == "prod"` and the value is empty.

**[Low] No absolute refresh-token session ceiling.** `backend/src/auth/refresh.py` — the rotation design itself is sound (256-bit random token, SHA-256 hash at rest, single-use chain with revoke-all-on-reuse replay detection). The gap is that a token chain refreshed periodically before each 30-day expiry can persist indefinitely, with no maximum session age enforced.

**No finding — tenant isolation.** `current_tenant()`/`require_role()` in `auth/dependencies.py` derive `hc_id` from server-verified JWT claims only, never client input. Spot-checked against `files.py` and `clients.py` query patterns — the codebase's own "cross-tenant access returns 404, never 403" convention is applied consistently everywhere sampled.

**No finding — CORS.** `main.py:38-44` scopes `allow_origins` to a single configured `frontend_url` with `allow_credentials=True`. No wildcard. Correctly configured.

**Good pattern, worth reusing deliberately.** `ClientInviteToken` (`db/models/auth.py`, `auth/router.py:239,376`) — raw token never persisted, only its SHA-256 hash; single-use enforced via `used_at`. Unit_003's spec already says it will reuse this exact pattern for lead upload tokens — sound, if built as documented (see §3).

### 2.1a Data erasure — added 2026-07-30, verified directly in code

**[High] No client-deletion pathway exists anywhere.** `backend/src/api/clients.py` registers `POST`, `POST /invite`, `GET`, `GET /{id}`, `PATCH`, `GET /{id}/ast` — **no `DELETE` route at all**. This matters specifically because `docs/domain/compliance-india.md`'s MVP consent scope commits, in writing, to clients: *"Erasure right — client may request deletion at any time; we will execute within 30 days; deletion is hard delete (not soft)."* The DB side of this is correctly built — every client-scoped FK across `files.py`, `content.py`, `llm.py`, `compliance.py`, `coaching.py`, `sessions.py` uses `ondelete="CASCADE"`, matching compliance-india.md's "IN for prototype (non-negotiable)" architectural hook. But the hook has nothing to trigger it: there is no endpoint, operator tool, or documented manual procedure that actually invokes a client delete today. **This is distinct from Unit_006 D-5's "real deletion" gap** (that one is about `users.deleted_at` / HC-level account deletion, still unresolved) — this is the client-level erasure-rights commitment, and it has no pathway at all, not even a soft one. Add before any real client's data enters the system, since the 30-day commitment is already being made in writing.

### 2.2 File upload (`backend/src/api/files.py`, `backend/src/lib/s3.py`)

**[Medium] Size limit is checked after the full body is already buffered.** `files.py:80-100` — `MAX_FILE_SIZE_BYTES` is enforced only after `content = await file.read()` has already read the entire multipart body into memory. There's no `Content-Length` pre-check or streaming cap, so the stated 25MB limit doesn't actually bound memory usage per request — a memory-exhaustion DoS vector.

**[Medium] MIME validation is header-only.** Same file — the allowlist checks the client-supplied `Content-Type` header only, with no magic-byte/content sniffing. A file can be mislabeled and pass validation. Currently lower-impact since these files feed LLM text extraction rather than being served back to a browser, but it compounds with the prompt-injection finding below.

**No finding — path traversal.** `s3.py:18-19` (`_sanitize`) correctly strips `/` from filenames before building R2 keys — a `../../` sequence degrades to inert text within one key segment, not a directory escape. Verified safe.

### 2.3 LLM prompt injection (`backend/src/llm_service/prompts.py`)

**[Medium, structural] No sanitization/escaping layer in prompt assembly.** Session notes, uploaded-file extracted text, and HC free text are interpolated directly into prompt templates with no delimiter defense anywhere in the pipeline. A malicious or adversarial input (a client-submitted message, or a doctored uploaded document) could contain injected instructions aimed at the AI drafter. The coach-reviewed gate is real mitigation for what reaches the *client*, but doesn't protect the *HC's own trust* in a draft they don't fully re-read against the source material.

### 2.4 Encryption consistency

**[Low, hygiene not a vulnerability] Two parallel encryption schemes coexist.** `EncryptedJSON`/Fernet (calendar credentials, client demographics) vs. pgcrypto/`pgp_sym` (llm_calls prompt/completion text). Both are legitimate on their own, but doubling the key-management surface (two rotation procedures, two failure modes) isn't justified by anything found in the reviewed ADRs. Worth consolidating or explicitly documenting why both exist.

---

## 3. Predictive findings — not yet built

These project likely vulnerability classes onto features that don't have code yet, based on patterns already present (or absent) in the shipped codebase. None of these are current bugs — they're what to design against *before* writing the code.

**Unit_004 F4 — Payments (Razorpay, spec D-27).** No webhook-handling code exists anywhere in the codebase today to model from — this will be the platform's *first* inbound webhook. Predict two easy-to-skip-under-deadline-pressure gaps: (1) signature verification (Razorpay's `X-Razorpay-Signature` HMAC) and (2) replay/idempotency handling (a webhook delivered twice must not double-mark a payment; a delayed replay after a manual status correction must not silently override it). Also predict a **third parallel key-management scheme** for the HC's own Razorpay API keys unless it's explicitly built onto the existing `EncryptedJSON` pattern (§2.4) rather than inventing a new one.

**Unit_004 F2/F3 — Check-ins, messaging, meal-photo logging.** Messaging (D-25) explicitly reuses "the same private-storage approach already planned for meal photos" — both will likely route through the existing `s3.py`/`files.py`. Predict the two file-upload gaps in §2.2 (post-buffer size check, header-only MIME validation) get **inherited silently** unless fixed once at the shared layer before F3 ships — meal photos are specced as *mandatory* per entry (D-26), meaning materially higher upload volume/exposure than today's session files.

**Unit_003 — Lead-intake pipeline.** Lead upload tokens are specced to copy the `ClientInviteToken` pattern — sound, low-risk, *if* built as documented. The bigger predictable risk is structural: blood-report PII (lab values, potentially diagnosable conditions) is the most sensitive data category in the entire product, reached via a token-gated link with **no account behind it at all** — the token alone is the full authentication factor. The spec doesn't yet address TLS-only delivery or explicit link-expiry enforcement details for the email carrying that link. Separately: PDF text extraction for the pre-consultation brief makes lab-report PDFs a new LLM-injection input surface (same class as §2.3, higher stakes given clinical content).

**Unit_005 — Macro formula engine.** The differentiator feature is HC-authored arithmetic expressions with "chained intermediate values." **If implemented via `eval()`/`exec()` or an unsandboxed expression evaluator rather than a restricted parser** (e.g. `asteval`, a proper grammar-based evaluator), this becomes a code-injection vector — HC input is not anonymous/public, but it's still untrusted input reaching a compute layer. The spec doesn't mention evaluator choice yet — flag this explicitly before implementation starts, not after.

**Unit_006 — Platform Foundations.**
- *(a)* Real account/data deletion (D-5): `users.deleted_at` exists but is soft-delete only. DPDP requires actual erasure — already flagged as unresolved in the spec itself, restated here because it's a compliance-grade gap, not merely a feature gap.
- *(b)* Operator/admin visibility (`is_operator` flag): standard risk of a binary admin flag with no enforced audit trail. The spec mentions `audit_log` as a requirement but it isn't built — every operator action needs to write an audit row from day one, or the gap compounds silently once admin visibility ships.
- *(c)* Monetization (Tapas billing HCs) will be a **second** payment-adjacent surface after Razorpay. Predict pressure to reuse F4's integration code — a reasonable predictive risk-reducer, but only *if* the webhook/signature work from F4 is done properly once, rather than needing to be re-solved twice.

---

## 4. Prioritized remediation list

| Priority | Item | Where |
|---|---|---|
| Critical | None found in currently-shipped code | — |
| High | No rate limiting on `/api/auth/*` — add before any real pilot traffic | `backend/src/main.py` |
| High | `_not_empty_in_prod` validator is dead code — fix before it masks a real prod misconfiguration | `backend/src/config.py:43-46` |
| High | No client-deletion endpoint exists — the DB cascade hooks are correctly wired but nothing triggers them, despite a written 30-day erasure commitment in `compliance-india.md` | `backend/src/api/clients.py` |
| Medium | File upload size check happens post-buffering, not pre-read — fix at the shared layer before F3 increases volume | `backend/src/api/files.py:80-100` |
| Medium | MIME validation is header-only, no content sniffing — same shared layer, same urgency | `backend/src/api/files.py` |
| Medium | No injection-defense layer in LLM prompt assembly — design this before Unit_003 adds clinical PDF text as a new untrusted input | `backend/src/llm_service/prompts.py` |
| Medium | Razorpay webhook signature verification + idempotency must be designed in from the start of F4, not retrofitted | Unit_004 F4 (not yet built) |
| Low | Two parallel encryption schemes (Fernet vs. pgcrypto) — consolidate or document the rationale | Cross-cutting |
| Low | No absolute refresh-token session ceiling | `backend/src/auth/refresh.py` |
| Low | Unit_005's formula evaluator choice needs an explicit "not `eval()`" decision recorded before implementation | Unit_005 (not yet built) |

---

## 5. Not independently verified

- Production `app_env` value at runtime.
- Whether Cloud Run's or Cloudflare's front door provides any rate-limiting/WAF coverage outside application code — the session log states this is not configured, but that wasn't re-verified against live infra in this pass.
- Rotation cadence (as opposed to mere existence) of Fernet keys (`google_calendar_encryption_key` and others) — the earlier GCP billing review only checked Secret Manager version *count*, not rotation practice.
