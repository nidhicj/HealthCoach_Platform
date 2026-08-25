# PHASE-05b: Razorpay OAuth Technology Partner migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. **Do not begin implementation until §6's prerequisites are confirmed complete — Task 0 in particular determines the actual shape of Tasks 4-5 below. This doc is written and ready, not yet cleared to execute.**

**Unit**: Unit_003_ClientDiscoveryPipeline
**Status**: Draft — written and ready, execution gated on §6 (SoJo's Razorpay Technology Partner setup, in particular Task 0's webhook-routing finding)
**Verification date**: TBD
**Implements**: `SPEC-0001-client-discovery-pipeline.md` §Decisions log D-1/D-2 (unchanged by this phase — Tapas remains never merchant of record, money still settles directly to the HC's own Razorpay-linked account), extends the `hc_payment_accounts` connection mechanism PHASE-05 shipped without changing what it's *for*
**ADRs implemented**: None — same convention as PHASE-05 (payment-architecture decisions recorded in SPEC-0001's own Decisions log, not a separate ADR); this phase should add a new decision entry there once it ships (see §3)
**Naming note**: lettered sub-phase, mirroring `Unit_004_OneStopSpot`'s existing `PHASE-01c`/`01d`/`01e`/`01f` precedent — this is a continuation/replacement of PHASE-05's connection mechanism, not a new pipeline stage, so it doesn't get its own top-level phase number.

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific I haven't provided. Ready?

## 1. Scope

PHASE-05 shipped a working, secure, fully-reviewed HC↔Razorpay connection flow — but it asks the HC to do real technical work: find their `key_id`/`key_secret` in Razorpay's dashboard, create a webhook, choose a `webhook_secret`, and paste all three into Tapas. That's a lot to ask of a non-technical health coach, and it's not something Tapas can take responsibility for going smoothly on the HC's end.

This phase replaces that manual paste-in flow with Razorpay's OAuth-based **Technology Partner** integration: the HC clicks "Connect with Razorpay," authorizes on Razorpay's own consent screen, and Tapas receives an access token it can use on their behalf — no credential the HC has to locate, copy, or paste. **This does not change the underlying architecture**: money still settles directly into the HC's own Razorpay-linked bank account, Tapas still never touches or holds funds, D-1/D-2 are unchanged. This is a UX/onboarding improvement to the *connection step*, not a shift toward Tapas becoming a payment aggregator (see the research this plan is based on — Razorpay's "Aggregator Partner" tier is the heavier, licensing-adjacent model; this phase deliberately uses "Technology Partner" instead, which Razorpay's own docs frame as "providing only technology infrastructure... does not handle funds").

**Not in scope**: anything that changes who holds the money or how much Tapas charges (still nothing — no revenue model decision is bundled into this). Migrating already-connected PHASE-05 HCs off the old key-based flow (see §3 — old and new coexist; forced migration is a separate, later decision). Building this for any product other than Unit_003's Client Discovery Pipeline (though the OAuth mechanism, once built, is a candidate for `Unit_004_OneStopSpot` F4 to reuse — same shared-capability note as `hc_payment_accounts` itself).

## 2. Deliverables planned

- `backend/src/db/models/payments.py` (modified) — `HcPaymentAccount.credentials` becomes a discriminated shape (`auth_type: "api_key" | "oauth"`), not a schema-breaking rewrite of PHASE-05's existing rows
- Migration: no column changes needed if `credentials` stays a JSON blob (just a new internal shape) — confirm during Task 1 whether any new top-level columns are actually needed (e.g. `auth_type` as its own indexed column vs. nested in the JSON) before assuming JSON-only is sufent
- `backend/src/lib/razorpay_client.py` (modified) — auth-aware request construction (Basic Auth for `api_key` rows, Bearer token for `oauth` rows), new functions for the OAuth code exchange and token refresh
- `backend/src/api/payment_accounts.py` (modified) — new `GET /api/hc/payment-account/oauth/start` (redirect to Razorpay) and `GET /api/hc/payment-account/oauth/callback` (code exchange, token storage) endpoints, alongside the existing manual-entry endpoints (both stay live)
- A background token-refresh mechanism, reusing this repo's existing `POST /internal/scheduled-tasks` convention (`backend/src/api/scheduler.py`) rather than inventing new job infrastructure
- Webhook handling changes — **exact shape depends on Task 0's finding, see §6 and the two branches sketched in Task 4 below**
- `frontend/src/app/(app)/settings/(hub)/payments/page.tsx` (modified) — a "Connect with Razorpay" button as the primary path, manual entry demoted to a secondary/advanced option, connection-status display aware of `auth_type` and token health
- `backend/src/api/payment_accounts.py`'s revocation handling — subscribe to `account.app.authorization_revoked` and mark the HC's connection disconnected when the HC revokes access from their own Razorpay account

## 3. Decisions to carry into implementation

- **Coexistence, not replacement, on day one.** PHASE-05's manual key-paste flow stays fully functional. This phase adds OAuth as the new, recommended path — it does not force already-connected HCs to reconnect, and does not remove the manual form. Whether to eventually deprecate manual entry is a later decision, not this phase's to make.
- **`razorpay_client.py`'s functions must become auth-mode-aware, not duplicated.** `create_order()` and `verify_webhook_signature()` (if per-account verification survives Task 0's finding) need to accept either a `{key_id, key_secret}` pair or an `access_token`, not become two parallel code paths — same function, different auth construction, matching this codebase's existing "one function, branch on shape" style rather than premature duplication.
- **Token refresh reuses the existing scheduler convention.** `backend/src/api/scheduler.py`'s `POST /internal/scheduled-tasks` (authenticated via `X-Scheduler-Token`/`SCHEDULER_SECRET`, dispatching named tasks via `X-Scheduled-Task`) is the established pattern for background work in this codebase (see `check_in_reminders`). A new `razorpay_token_refresh` named task fits this exactly — do not build a separate cron/job mechanism.
- **Access tokens: 90-day TTL. Refresh tokens: 180-day TTL** (per Razorpay's own OAuth docs, confirmed while researching this phase). The refresh job needs to run comfortably inside the 90-day window (e.g. daily, refreshing any token within N days of expiry) — refreshing on a schedule, not lazily on first-use-after-expiry, since a lazy approach would mean the first API call after expiry fails before the refresh has a chance to run.
- **If a refresh token itself lapses (180 days with no successful refresh — e.g. the refresh job was broken for a long stretch, or Razorpay-side revocation), the HC must re-authorize via the OAuth flow again.** This is a real, if rare, failure mode — the connection-status UI must be able to represent "reconnection needed," not just "connected" / "not connected," and the HC-facing copy for this state needs to be as low-alarm as the rest of this phase's UX goal (e.g. "Please reconnect your Razorpay account" with a one-click re-authorize button, not a scary error).
- **New Decisions-log entry for SPEC-0001 once this ships**: record why Technology Partner OAuth was chosen over both the manual flow (too much HC effort) and Aggregator Partner/Route (would make Tapas a licensed payment aggregator, the exact posture D-2 exists to avoid) — this reasoning currently only lives in this conversation's history, not in the spec.

## 4. Source docs to consult before implementing

- `docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` — D-1/D-2/D-8, the `hc_payment_accounts` connection-flow prose (PHASE-05 elaborated this; this phase supersedes part of it, not all of it)
- `docs/specs/Unit_003_ClientDiscoveryPipeline/PHASE-05-payment-and-scheduling-handoff.md` — the shipped connection flow, webhook verification algorithm, and every judgment call recorded in its §6-9 that this phase either preserves or changes
- `backend/src/api/scheduler.py` — the existing scheduled-task convention this phase's token-refresh job must follow
- `backend/src/db/encrypted_json.py`, `backend/src/db/models/payments.py`, `backend/src/lib/razorpay_client.py`, `backend/src/api/payment_accounts.py`, `backend/src/api/payments.py` — the exact PHASE-05 code this phase modifies; read all of it before touching any of it, same discipline PHASE-05 itself applied to PHASE-04's code
- Razorpay's own Technology Partner OAuth documentation (`razorpay.com/docs/partners/technology-partners/`) — this plan's technical details were researched via Razorpay's public docs during this session, but the single most load-bearing fact (webhook routing — see §6 Task 0) was **not** confirmed from documentation and must be confirmed directly in Razorpay's sandbox before Task 4 can be finalized

## 5. Verification

- Every acceptance criterion PHASE-05 already has for the manual flow must still pass unmodified — this phase adds a path, it must not regress the existing one.
- A real sandbox OAuth round trip: a test sub-merchant account authorizes via the real Razorpay OAuth consent screen (not mocked), Tapas receives and stores a real token pair, makes a real API call (order creation) using the token, and the token refresh job is proven to actually refresh a token nearing expiry (not just unit-tested against a mocked clock).
- Whichever webhook model Task 0 confirms, a real webhook delivered from Razorpay's own servers through it, exactly as rigorously as PHASE-05's own Task 8 required for the original flow — this phase inherits that same "first real-money-adjacent code, no mock-only verification" bar.
- A manual walkthrough of the revocation path: HC revokes access from their own Razorpay account, Tapas's connection status correctly flips to disconnected without the HC needing to do anything in Tapas.

---

## 6. What SoJo needs to go acquire before this phase can be implemented

This is the section explicitly asked for — everything below is on SoJo's side, not something an implementer subagent can do (it requires a real Razorpay account holder making real decisions and real sandbox tests). **Task 0 in particular blocks finalizing Tasks 4-5's exact design — everything else can be scoped in parallel, but don't let an implementer start Task 4 until Task 0's answer is in hand.**

- [ ] **Sign up as a Razorpay Technology Partner.** razorpay.com/partners → create a Partner account → "switch to Technology Partner." This is self-serve per Razorpay's own docs, not a sales-gated process, but confirm that's still true when you get there — this was researched via public docs, not verified by actually doing it.
- [ ] **Complete Tapas's own business KYC with Razorpay.** This is a one-time, company-level KYC (Tapas as an entity), separate from and unrelated to any individual HC's own KYC on their own account. Check Razorpay's current document checklist directly when you reach this step — this plan doesn't guess at the exact list, since it varies by business type and Razorpay's requirements can change.
- [ ] **Register an OAuth application in the Partner Dashboard.** This produces a `client_id`/`client_secret` pair for the *partner application itself* — a different concept from PHASE-05's old per-HC `key_id`/`key_secret`. Whitelist the redirect URI(s) Tapas will use (production domain + whatever local-dev tunnel URL you're using for testing, same tunnel-setup need PHASE-05's own manual verification already required).
- [ ] **Task 0 — resolve the webhook-routing model, in the sandbox, before this phase's implementation tasks are finalized.** Connect at least two separate sandbox sub-merchant accounts via the OAuth flow and determine: does Razorpay deliver `payment.captured` events for *all* connected sub-merchants to **one webhook URL configured once on the Partner Dashboard** (tagged with `razorpay_account_id` so Tapas can tell which HC each event is for — this is how Stripe Connect works, and the likely-but-unconfirmed outcome here too), or does **each connected sub-merchant still need its own webhook configured** (closer to what PHASE-05 already does, just with a token instead of a manually-chosen secret)? This single fact determines whether Task 4 below is a small change (one webhook, once) or a moderate one (still per-account, but token-based). Document the answer plainly (a screenshot of two sandbox test payments' webhook deliveries and where they landed is enough) and hand it back before implementation starts.
- [ ] **Confirm there's no hidden cost to the Technology Partner program itself**, beyond Razorpay's normal per-transaction gateway fee. Nothing in the public docs mentioned a partner-program fee, but "not mentioned" isn't the same as "confirmed free" — ask Razorpay directly (their integrations contact, referenced in their own docs) rather than assume.
- [ ] **Do at least one full sandbox OAuth round trip yourself** — connect a test sub-merchant, make a test API call using the resulting access token, let (or force) a token refresh happen, and confirm the mechanics genuinely work as documented before an implementer builds against them. This plan's technical detail (the exact `/authorize` and `/token` endpoint shapes, the 90-day/180-day token lifetimes) came from Razorpay's public docs, not a live test — worth a real sanity check given how much of Task 1-3 depends on it being accurate.

## Implementation Plan

**Not dispatched yet — this section is written so it's ready the moment §6 is cleared, not because implementation should start now.** Ordered task breakdown, to be executed via `superpowers:subagent-driven-development` once §6's checklist is done, mirroring PHASE-05's own execution discipline (pre-flight scan before Task 1, task-scoped reviews, a final whole-phase review before this phase is considered done).

### Task 1 — `hc_payment_accounts` schema: support both auth modes

Extend `HcPaymentAccount.credentials`'s stored shape to a discriminated union: existing PHASE-05 rows keep `{"auth_type": "api_key", "key_id": ..., "key_secret": ..., "webhook_secret": ...}` (a migration step to backfill `auth_type: "api_key"` onto every existing row, not a breaking schema change — still one `EncryptedJSON` column, same encryption mechanism, no new encryption key needed). New OAuth rows get `{"auth_type": "oauth", "access_token": ..., "refresh_token": ..., "public_token": ..., "razorpay_account_id": ..., "token_expires_at": ...}`. Confirm during this task whether `auth_type` and `token_expires_at` should also be promoted to real (non-JSON) columns for queryability (the refresh job needs to efficiently find "tokens expiring soon" — a JSON-nested timestamp may not index well; this is a real implementation decision to make deliberately, not default to JSON-only for consistency with PHASE-05's shape when the access pattern is genuinely different).

### Task 2 — OAuth start + callback endpoints

`GET /api/hc/payment-account/oauth/start` (HC-authenticated) — builds the Razorpay `/authorize` redirect URL with `client_id`, `redirect_uri`, `scope=read_write`, and a `state` value that ties the callback back to the requesting HC (CSRF protection, and the mechanism for knowing *which* Tapas HC this OAuth flow belongs to once the callback returns — Razorpay's `state` param is exactly this). `GET /api/hc/payment-account/oauth/callback` (public — Razorpay redirects here directly, not through an authenticated Tapas session) — validates `state`, exchanges the `code` for a token set via Razorpay's `/token` endpoint, stores the result via Task 1's new shape, sets `connected_at`. Both endpoints coexist with the existing `POST /api/hc/payment-account/connect` manual form — do not remove or gate it.

### Task 3 — token refresh job + auth-aware `razorpay_client.py`

New named task `razorpay_token_refresh` in `backend/src/api/scheduler.py`'s existing `POST /internal/scheduled-tasks` dispatch (same `X-Scheduler-Token` auth, same pattern as `check_in_reminders`) — finds `oauth`-mode `hc_payment_accounts` rows with `token_expires_at` inside a refresh window, calls Razorpay's refresh endpoint, updates the stored token pair. `razorpay_client.py`'s `create_order()` (and any other authenticated call) becomes auth-mode-aware: `api_key` rows use `httpx`'s `auth=(key_id, key_secret)` as today; `oauth` rows use `headers={"Authorization": f"Bearer {access_token}"}`. One function, branching on shape — not two parallel implementations.

### Task 4 — webhook handling (design depends on §6 Task 0's finding — do not start until that's confirmed)

**Branch A (single platform-level webhook, if confirmed)**: Tapas registers one webhook URL on the Partner Dashboard (a one-time setup step, not per-HC). The webhook handler verifies signature using ONE partner-level secret (configured once, stored in settings — not per-HC `hc_payment_accounts.credentials`), and resolves which HC an event belongs to via `razorpay_account_id` in the payload (looked up directly, not via the `notes.hc_user_id` mechanism PHASE-05 built — that mechanism was specifically a workaround for per-HC secrets; it may no longer be needed at all). This would be a genuine simplification of PHASE-05's most carefully-built piece — confirm the `razorpay_account_id`-based Lead-matching path is at least as safe (still cross-check against `hc_payment_accounts` before trusting anything, same non-negotiable "verify before trust" discipline as before).

**Branch B (still per-account, if that's what Task 0 finds)**: keep PHASE-05's per-account webhook verification design, but the HC no longer chooses/pastes a `webhook_secret` manually — either Razorpay auto-provisions one accessible via the partner API during the OAuth connect flow (best case, confirm if this exists), or this phase still needs *some* per-account webhook registration step, which would only be a partial improvement over PHASE-05 (API keys removed, webhook setup not fully removed) — worth surfacing honestly to SoJo rather than overselling this phase's benefit if Task 0 comes back this way.

Either branch: `POST /api/payments/webhook`'s idempotency, tenant cross-checks, and the payment-status/token-activation writes (`leads.payment_status`, `LeadUploadToken.expires_at`) stay conceptually the same as PHASE-05 — only the signature-verification and HC-resolution steps change.

### Task 5 — Frontend: "Connect with Razorpay" + connection-status UI

`frontend/src/app/(app)/settings/(hub)/payments/page.tsx` — a primary "Connect with Razorpay" button (redirects to Task 2's `/oauth/start`), the existing manual-entry form demoted to a labeled secondary/advanced option (for HCs who, for whatever reason, prefer or need it — do not remove it). Connection-status display distinguishes: not connected / connected via OAuth (healthy) / connected via API key (PHASE-05's original path, still valid) / needs reconnection (refresh token lapsed, per §3's decision) — with a low-alarm, one-click "reconnect" affordance for that last state, not a scary error banner. Handle the OAuth callback's redirect-back-to-settings-page UX (success/failure states).

### Task 6 — Revocation handling + whole-flow integration test

Subscribe to `account.app.authorization_revoked` (or the equivalent event confirmed during Task 0's sandbox testing) and mark the HC's `hc_payment_accounts` row disconnected when it fires — the HC should never have to do anything in Tapas to reflect a revocation they made on Razorpay's side. Whole-flow integration test mirroring PHASE-05's own Task 8: OAuth connect (real sandbox round trip or the closest faithful simulation the test suite can manage) → order creation using the token → webhook (whichever branch Task 4 implemented) → payment_status flips → upload unlocked. Manual verification: the full revocation round trip, and a real token-refresh cycle observed end to end, not just unit-tested.
