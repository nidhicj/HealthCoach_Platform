# PHASE-05: Payment + scheduling handoff

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task.

**Unit**: Unit_003_ClientDiscoveryPipeline
**Status**: Draft
**Verification date**: TBD — fill in after implementation and verification
**Implements**: `SPEC-0001-client-discovery-pipeline.md` §Stage 4 (Lead pays, scheduling handoff), §Decisions log D-1/D-2/D-3/D-8, §Data (`hc_payment_accounts`, `leads.payment_status`/`payment_reference`/`paid_at`/`scheduled_at`/`meeting_link`, `lead_upload_tokens.expires_at` now nullable), §API surface (payment endpoints), §Acceptance criteria → "Payment", "Scheduling handoff", the new upload-token acceptance rows added 2026-08-25
**ADRs implemented**: None. This repo's established convention (see `Unit_004_OneStopSpot`'s identical D-27) is to record payment-architecture decisions in the owning spec's own Decisions log, not a separate ADR — D-1/D-2/D-3/D-8 are that record for this unit.

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific I haven't provided. Ready?

## 1. Scope

This phase builds the platform's first payment integration — native Razorpay, test mode, each HC connecting their own account (D-1/D-2), fully decoupled from scheduling with no slot-hold (D-3) — and implements D-8's redesign of Stage 3's Lead-facing "next steps" email: one email, sent once, with two buttons present from the start (book & pay; upload results), the second gated server-side by payment status rather than withheld in a second email.

Concretely: a new `hc_payment_accounts` table (per-HC Razorpay credentials, encrypted), a settings connection flow with a live credential sanity check, a thin Razorpay HTTP client (Order creation, credential verification, webhook signature verification), a per-HC-verified webhook receiver, five new `leads` columns, a modification to already-shipped PHASE-04 code (`leads.py`'s Send action now issues the upload token and calls a rewritten email function), a payment-status gate added ahead of the already-shipped PHASE-03 upload-token validation, a Lead-facing payment page, and a settings connection UI.

**Not in scope**: OTP hardening of the upload link (D-6, PHASE-06) — this phase adds a new gate *ahead of* the existing plain-token upload flow, but doesn't touch the flow's own file-upload mechanics. The two-part B1/B2 brief restructuring (PHASE-06). The actual scheduling mechanism (external, out of scope per D-3 — this phase only gates access to the HC's already-configured `scheduling_link`; nobody has to build a calendar). A webhook reconciliation job for missed webhooks (SPEC-0001 Open questions — deferred until before PHASE-05 is *production-ready*, not before test-mode development can proceed). Refunds, disputes, recurring billing (SPEC-0001 Non-goals). A `PaymentProvider` interface abstracting Razorpay behind a swappable gateway — no second provider exists or is planned; building one now would be exactly the kind of premature abstraction CLAUDE.md warns against. The Lead list/detail page and `/api/leads/:id/remind` (tracked separately in SPEC-0001 Open questions, a real but distinct gap this phase does not close).

## 2. Deliverables planned

- `backend/src/db/models/payments.py` (new) — `HcPaymentAccount` model
- Migration: create `hc_payment_accounts`
- Migration: add `leads.payment_status`/`payment_reference`/`paid_at`/`scheduled_at`/`meeting_link`; alter `lead_upload_tokens.expires_at` to nullable
- `backend/src/lib/razorpay_client.py` (new) — `create_order()`, `verify_credentials()`, `verify_webhook_signature()`
- `backend/src/config.py` — four new settings fields (`razorpay_test_key_id`, `razorpay_test_key_secret`, `razorpay_test_webhook_secret`, `razorpay_credentials_encryption_key`)
- `backend/src/api/payment_accounts.py` (new) — `GET`/`POST /api/hc/payment-account*`
- `backend/src/api/leads.py` (modified) — `send_test_recommendation` now mints the upload token and calls the rewritten email
- `backend/src/lib/email.py` (modified) — `send_finalized_test_recommendation_email` rewritten (D-8 two-step copy, two real links)
- `backend/src/api/payments.py` (new) — `GET`/`POST /api/leads/:id/payment*`, `POST /api/payments/webhook`
- `backend/src/api/upload.py` (modified) — payment-status gate added to `_resolve_token`/`get_upload_token_state`
- `frontend/src/lib/api/payments.ts` (new) — Zod client
- `frontend/src/app/(public)/pay/[leadId]/page.tsx` (new) — Lead-facing payment page
- Settings hub — new "Payments" entry (connection form), placement flagged for SoJo confirmation (see Task 7)
- Dev-seed step reading `RAZORPAY_TEST_*` env vars into a local `hc_payment_accounts` row

## 3. Decisions to carry into implementation

These are already made (SPEC-0001's Decisions log D-1/D-2/D-3/D-8, plus decisions made while writing this plan) — implementers should not re-litigate them, only implement them correctly:

- **D-1/D-2**: Razorpay, test mode. Tapas never merchant of record — each HC's own `key_id`/`key_secret` authenticate every API call made on their behalf; Tapas's backend never uses a platform-level Razorpay account for anything in this flow.
- **D-3**: payment and scheduling stay fully decoupled. No slot-hold. Payment success just hands the Lead to `scheduling_link` — nothing about *that* handoff is built here.
- **D-8**: one email (already shipped copy structure is in SPEC-0001 Stage 3 step 8 / Stage 4 / Stage 5 — read it, don't re-derive it), `lead_upload_tokens` issued at Send-time with `expires_at = NULL`, activated (`expires_at = NOW() + 14 days`) only by the webhook on payment success.
- **`EncryptedJSON` reuse, not a new encryption mechanism**: `hc_payment_accounts.credentials` uses the existing `backend/src/db/encrypted_json.py` `TypeDecorator` (the same one `DEMOGRAPHICS_ENCRYPTION_KEY` already uses), parameterized with a new `razorpay_credentials_encryption_key` settings key. Do not invent a second encryption pattern, and do not reuse `pgp_sym_encrypt`/`llm_calls`' raw-SQL pattern — that one exists because prompt/completion text is rarely read back into application logic; Razorpay credentials must be read back on every order creation and every webhook, which is exactly what `EncryptedJSON` was built for.
- **`httpx` via `make_http_client()`, not a `razorpay` SDK dependency**: this codebase already has an established outbound-HTTP pattern (`backend/src/lib/http.py`, used by `calendar.py`, `oauth.py`, `s3.py`, `llm_service/client.py`). Razorpay's REST API is simple enough (Basic Auth + JSON) that adding a new third-party SDK dependency isn't justified. Use `httpx.AsyncClient(auth=(key_id, key_secret))` for API calls.
- **Two distinct fields, don't conflate them**: `leads.status = 'payment_pending'` is set the moment an Order is created (Lead is mid-checkout) — this is about the Lead's pipeline position. `leads.payment_status` stays `'unpaid'` until the webhook actually confirms `payment.captured` — this is about whether money has moved. A Lead can sit at `status='payment_pending'`, `payment_status='unpaid'` indefinitely if they abandon checkout; that's a normal, retry-safe state (D-3), not a bug.
- **Per-HC webhook signature verification — the one piece of this design that must not be simplified.** Each HC's Razorpay account has its own `webhook_secret` (they choose it when creating the webhook in their own dashboard, pointing at this platform's single receiver URL). `POST /api/payments/webhook` therefore cannot verify against one shared secret. The algorithm, already researched and recorded in SPEC-0001's Data section (`hc_payment_accounts` — do not re-derive this from scratch, read it there first):
  1. Read the **raw request body bytes** before any JSON parsing (needed for HMAC — a re-serialized/re-parsed body will not reproduce the same bytes Razorpay signed, this exact class of bug is a documented real-world source of signature mismatches).
  2. Parse the JSON (still untrusted). Extract `hc_user_id` from the payload's `notes` (set at Order-creation time, Task 5 — confirm the exact JSON path for a `payment.captured` event against Razorpay's real docs during implementation, don't guess the nesting).
  3. Look up that `hc_user_id`'s stored `webhook_secret`. No match / not connected → reject 400 immediately, do not attempt verification against any other secret.
  4. Recompute HMAC-SHA256 hex over the raw body using that HC's `webhook_secret`; compare to the `X-Razorpay-Signature` header with `hmac.compare_digest` (constant-time). Mismatch → reject 400, do not process the payload.
  5. Only past step 4 is the payload trusted. The `notes` lookup in step 2 only selects *which* secret to try — it is never itself the authorization check; an attacker who fabricates `notes.hc_user_id` still cannot produce a valid signature without knowing the real secret.
- **`amount_paise = consultation_fee_inr * 100` — flagged here because it is the single easiest way to ship a catastrophic bug in this phase.** `hc_leadgen_config.consultation_fee_inr` is whole rupees (INTEGER). Razorpay's Orders API takes the smallest currency unit (paise) — sending rupees directly either fails Razorpay's minimum-amount check or, worse, charges 1/100th of the intended fee. Task 5 has a named test asserting this conversion explicitly; do not let that test get diluted into a generic "order creation works" assertion.
- **Task numbering below is already dispatch-safe** (unlike PHASE-04, which needed a documented reordering) — each task only depends on tasks with a lower number. Dispatch in written order unless a real blocker emerges; if one does, rule on it and log the reordering the same way PHASE-04's ledger did.

## 4. Source docs to consult before implementing

- `docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` — §Stage 4/5, §Decisions log D-1/D-2/D-3/D-8, §Data (`hc_payment_accounts` — read the connection-flow and webhook-verification prose there in full, it is the authoritative design, not a summary of it), §API surface, §Edge cases (payment + upload-token rows), §Acceptance criteria (Payment, Scheduling handoff, and the upload-token rows added 2026-08-25)
- `docs/specs/Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` §F4 (lines ~260-303) and D-27 — the sibling design this phase must not diverge from without a documented reason (self-onboarding, encrypted-at-rest, no partial-payment tracking, no refund flow). `hc_payment_accounts` is a candidate shared table for whoever builds F4 next — keep it unit-agnostic in naming and shape.
- `backend/src/db/encrypted_json.py` — read directly, this is the mechanism Task 1 reuses
- `backend/src/api/clients.py` — the invite-token creation pattern Task 4 mirrors in full, including "invalidate existing unused tokens before minting a new one" (needed here too — see Task 4's note on why).
- `backend/src/api/upload.py` — `_resolve_token()` and `get_upload_token_state()`, the functions Task 6 modifies; read the existing four-state (`not_found`/`expired`/`used`/`valid`) design and its check ordering before adding a fifth
- `backend/src/lib/http.py` — `make_http_client()`, Task 1's HTTP client factory
- `backend/src/api/leads.py` — `send_test_recommendation`, the function Task 4 modifies (already-shipped PHASE-04 code — read it whole before editing)
- `backend/src/lib/email.py` — existing conventions (`html.escape()` on every interpolated value, brand CSS, short distinct subjects) and the current `send_finalized_test_recommendation_email` Task 4 rewrites
- Razorpay's own current API documentation — this plan's webhook/notes/auth details were confirmed via web search while writing this plan (HMAC-SHA256 over raw body keyed with a dashboard-configured webhook secret, separate from API key_secret; `notes` supports up to 15 key-value pairs; Basic Auth via `key_id:key_secret`), but exact JSON payload shapes for specific event types were not fully verified against a live sandbox — confirm those directly against Razorpay's docs during Task 5/6 rather than trusting this plan's phrasing as gospel

## 5. Verification

Verification should cover, at minimum, every checkbox under SPEC-0001's §Acceptance criteria → "Payment", "Scheduling handoff", and the upload-token rows added 2026-08-25, plus:

- Full backend + frontend suite green
- The `amount_paise` conversion has its own named, obvious test — not folded into a generic "order creation succeeds" test
- Webhook signature verification tested against a real computed HMAC (a test fixture secret, not a mocked `True`) for both the success and wrong-signature-rejected paths, plus the unknown-`hc_user_id` and duplicate-delivery paths
- **A real Razorpay test-mode round trip**, not mocks alone: real Order creation, real hosted Checkout (mock UPI/card success and an induced failure/decline), and a real webhook delivered from Razorpay's own servers to a reachable endpoint (local dev will need a tunnel — check `docs/decisions/` for an existing tunneling convention from other external-callback work, e.g. the Google Calendar OAuth integration, before introducing a new one). This is the platform's first real-money-adjacent code; mock-only verification is not sufficient for this phase specifically, even though it is for most others.
- Manual browser walkthrough: HC sends a panel → Lead receives the D-8 email with both buttons → clicks "Upload your results" first and sees the gated "complete your booking first" state → clicks "Book your consultation," pays, is handed off to `scheduling_link` → reopens the *same* upload link and it now works

---

## Implementation Plan

Ordered task breakdown, executed via `superpowers:subagent-driven-development` — one fresh implementer + reviewer per task, matching PHASE-01–04's execution discipline this session.

### Task 1 — `hc_payment_accounts` model + migration + settings + `backend/src/lib/razorpay_client.py`

Model (new file `backend/src/db/models/payments.py`, mirroring `llm.py`'s precedent of a concern-based file rather than cramming into `leadgen.py`): `HcPaymentAccount` — `id` UUID PK, `hc_user_id` UUID FK → `users.id` UNIQUE, `credentials: Mapped[dict | None]` using `EncryptedJSON(settings_key="razorpay_credentials_encryption_key")` (storing `{"key_id": ..., "key_secret": ..., "webhook_secret": ...}`), `connected_at: Mapped[datetime | None]`, `created_at`, `updated_at`. Migration: new table, continuing the single linear head from `1f2a6c9d4e17`.

Settings (`backend/src/config.py`): add `razorpay_test_key_id: str = ""`, `razorpay_test_key_secret: str = ""`, `razorpay_test_webhook_secret: str = ""`, `razorpay_credentials_encryption_key: str = ""` — matching the existing `llm_call_encryption_key`/`demographics_encryption_key` pattern exactly (same file, same style).

`backend/src/lib/razorpay_client.py` (new) — three functions, no class/interface wrapper (see §3 — no `PaymentProvider` abstraction):

- `async def create_order(*, key_id: str, key_secret: str, amount_paise: int, notes: dict[str, str]) -> dict` — `POST https://api.razorpay.com/v1/orders` via `make_http_client()`, `auth=(key_id, key_secret)`, JSON body `{"amount": amount_paise, "currency": "INR", "notes": notes}`. Raise on a non-2xx response (let the caller in Task 5 decide the Lead-facing error). Returns the parsed response dict (contains `id`, the order ID).
- `async def verify_credentials(*, key_id: str, key_secret: str) -> bool` — one cheap authenticated read call to confirm the pair is valid (pick a low-cost endpoint, e.g. listing orders with `count=1`); `401`/`403` → `False`; let genuine network/5xx errors propagate rather than silently returning `False` for those too, so `POST /api/hc/payment-account/connect` (Task 2) can distinguish "your key is wrong" from "Razorpay is unreachable right now." Document whichever exact call you pick and why in your task report.
- `def verify_webhook_signature(*, raw_body: bytes, signature: str, webhook_secret: str) -> bool` — HMAC-SHA256 hex digest over `raw_body`, keyed with `webhook_secret`, compared to `signature` via `hmac.compare_digest`. Pure function, no I/O — trivially unit-testable with a hand-computed fixture signature.

Tests: `create_order` sends the exact body shape (mock the HTTP call, assert on the request), `verify_credentials` true/false/error-propagation paths, `verify_webhook_signature` correct-signature/wrong-signature/wrong-secret cases against a hand-computed HMAC fixture (not a round-trip through `create_order` — this function must be verifiable in total isolation).

### Task 2 — `GET`/`POST /api/hc/payment-account*`

New file `backend/src/api/payment_accounts.py`. `require_role('hc')` + `current_tenant()`, mirroring `leads.py`'s existing pattern.

`GET /api/hc/payment-account` → `{connected: bool}` (derived from `connected_at is not None`). Never returns the credentials themselves — not even to their own owning HC — this is write-only from the API's perspective once stored.

`POST /api/hc/payment-account/connect` — body `{key_id: str, key_secret: str, webhook_secret: str}` (all required, non-blank). Calls `razorpay_client.verify_credentials()` (Task 1) with the pasted `key_id`/`key_secret`. **Two distinct failure modes, both must return a structured error, neither may 500**: (a) `verify_credentials()` returns `False` (bad key) → 422 `{"error": "invalid_credentials", "message": "Could not verify these Razorpay credentials — check they're correct and in test mode."}`; (b) `verify_credentials()` raises (Task 1's function deliberately lets network/5xx errors propagate rather than swallowing them into `False`) → catch this here and return a distinct 502/503-style structured error, e.g. `{"error": "razorpay_unreachable", "message": "Couldn't reach Razorpay to verify these credentials — please try again."}`, so the HC isn't told their real key_id/key_secret is wrong when the actual problem was a transient network failure. On success: upsert the HC's `hc_payment_accounts` row (`credentials` = all three fields, `connected_at = now()`), return `{connected: true}`. Reconnecting (calling this a second time) overwrites the stored credentials and updates `updated_at` — no separate "disconnect" flow needed at this scope.

Register `payment_accounts_router` in `backend/src/main.py`.

Tests: connect success (mock `verify_credentials` → `True`, row created, `connected_at` set), connect failure — bad credentials (mock → `False`, structured 422, no row / row not marked connected), connect failure — Razorpay unreachable (mock `verify_credentials` to raise, structured 502/503 error distinct from the 422 case, not a 500), reconnect overwrites cleanly, `GET` before and after connect, cross-tenant isolation (an HC never sees another HC's `connected: true`/`false` — trivially true here since the lookup is always `current_tenant()`-scoped, but write the test anyway), unauthenticated → 401, client-role JWT → 403/404 per this codebase's convention.

### Task 3 — `leads` payment/scheduling columns + `lead_upload_tokens.expires_at` nullable

Migration 1: add to `leads` — `payment_status TEXT NOT NULL DEFAULT 'unpaid'`, `payment_reference TEXT`, `paid_at TIMESTAMPTZ`, `scheduled_at TIMESTAMPTZ`, `meeting_link TEXT`. Matches SPEC-0001's Data section exactly — copy the column list from there, don't re-derive it.

Migration 2: alter `lead_upload_tokens.expires_at` — `DROP NOT NULL`. This table already has rows in any environment where PHASE-03/04 have been exercised (none in production yet, per this session's own verification, but treat the migration as if it mattered): the upgrade is safe (loosening a constraint never breaks existing NOT-NULL data), but write the downgrade carefully — re-adding `NOT NULL` on a column that may by then contain real `NULL` rows (any Lead sent but not yet paid) will fail outright; either the downgrade documents this as a one-way migration in practice (acceptable, note it explicitly in the migration's docstring) or backfills a sentinel before re-adding the constraint. Pick one and say which in your task report — do not leave the downgrade silently broken.

Model updates in `backend/src/db/models/leadgen.py`: `Lead` gains the five new `Mapped` fields (defaults matching the migration). `LeadUploadToken.expires_at` becomes `Mapped[datetime | None]`. This is a type change on an already-shipped model — confirm `backend/src/api/upload.py`'s existing `_resolve_token()` still typechecks (it will; the actual *behavior* change for a `None` `expires_at` is Task 6's job, not this one — this task only needs the schema and types to be correct and consistent, not the new gating logic).

Tests: migration round-trips cleanly (upgrade/downgrade, matching this session's established migration-review bar), new `Lead` fields default correctly on insert, `LeadUploadToken` accepts `expires_at=None`.

### Task 4 — Issue the upload token at Send-time + rewrite the Lead-facing email (D-8)

**This task modifies already-shipped PHASE-04 code** (`backend/src/api/leads.py`'s `send_test_recommendation`) — read it whole before editing, it is tested and reviewed working code.

After the existing logic that finalizes `leads.test_recommendation`/`leads.status = 'tests_recommended'`: mint the Lead's upload token, mirroring `clients.py`'s invite-token pattern exactly (`raw_token = os.urandom(32).hex()`, `token_hash = hashlib.sha256(raw_token.encode()).hexdigest()`), creating a `LeadUploadToken(lead_id=lead.id, token_hash=token_hash, expires_at=None)`. Fold this into the endpoint's existing commit rather than adding a second commit boundary if that's straightforward; use your judgment if it isn't.

**Re-send idempotency**: PHASE-04 already made Send idempotent (calling it twice re-finalizes and re-emails, by design). A raw token, once minted, cannot be recovered from its stored hash — so a second Send cannot resend the *same* link even if it wanted to. Resolution: **mint a fresh token on every Send, and invalidate any of this Lead's prior unused tokens first** — mirroring `clients.py`'s "invalidate existing unused tokens before minting a new one" step after all (an earlier draft of this plan said not to mirror that step, reasoning the old link was harmless since it can't be resent; that reasoning was wrong — see below). Concretely: before minting, `UPDATE`/mark `used_at = now()` on any `LeadUploadToken` row for this `lead_id` where `used_at IS NULL`, then insert the new row as before.

**Why invalidation is required, not optional**: Task 6's webhook activates payment by setting `expires_at` on "the Lead's `LeadUploadToken` row." If re-Sends left multiple unused rows alive, a webhook firing after payment would have no unambiguous single row to activate — and if it activated all unused rows instead, the Lead would end up with more than one simultaneously-valid, OTP-reachable upload link. That's not harmless: a Lead who uploads via one link, then later opens a second still-valid link from an older email, would hit `used_at IS NULL` on that second row and be allowed to upload again — duplicate `lead_files` rows, a second brief-generation trigger. Invalidating old unused tokens at mint-time keeps "the Lead's live token" unambiguous for Task 6, exactly as `clients.py`'s own precedent already does for the same reason on client invites.

Rewrite `send_finalized_test_recommendation_email` in `backend/src/lib/email.py`. New signature needs (at minimum) `to`, `lead_name`, `hc_name`, `test_list`, `pay_link` (`f"{frontend_url}/pay/{lead_id}"`), `upload_link` (`f"{frontend_url}/upload/{raw_token}"`). New subject: `f"Your next steps with {hc_name}"`. New body, two numbered steps, both with a real button (approved copy, adapt formatting to this file's existing HTML/CSS conventions, do not change the substance):

> Hi {lead_name},
>
> Thank you for connecting with {hc_name}. To continue working with them, here's what's next:
>
> **Step 1 of 2 — Book your first consultation**
> Choose a time that works for you and complete payment to confirm your slot.
> [ Book your consultation ] → `{pay_link}`
>
> **Step 2 of 2 — Upload your blood test results**
> {hc_name} recommends: {test list}
> Please leave enough time before your consultation to get these done. Once your consultation is booked, use the button below to upload your results — this same link will work once Step 1 is complete.
> [ Upload your results ] → `{upload_link}`
>
> {hc_name} will be in touch with next steps.

Both links are always real and clickable from the moment this email is sent — Step 2's gating happens server-side on the upload page (Task 6), not by withholding the link. Do not add any conditional logic to the email itself about payment state; it doesn't know or need to know.

Tests: Send mints a token (row exists, `expires_at IS NULL`, `used_at IS NULL`), email is called with both links correctly constructed from the lead id / raw token, a second Send for the same lead invalidates the first token (`used_at` now set on the old row) and mints a fresh one (only the new row has `used_at IS NULL`) and the email reflects the new link, existing PHASE-04 Send tests (status transition, idempotent re-send, HC-edit-wins-over-draft) still pass unmodified — flag in your report if any needed adjustment and why.

### Task 5 — `GET`/`POST /api/leads/:id/payment` (Lead-facing, public)

**New file** `backend/src/api/payments.py`, its own `APIRouter(prefix="/api/leads", tags=["payments"])` — **do not add these routes to `leads.py`'s existing router**, even though the URL prefix overlaps. `leads.py`'s router is HC-authenticated throughout; these routes are deliberately public (a Lead with no account must be able to hit them). Keeping them in a separate file/router with no auth dependency makes that boundary visible in the code, not just in your head. `POST /api/payments/webhook` (Task 6) belongs in this same file — same file, second router (`prefix="/api/payments"`), same reasoning.

`GET /api/leads/:id/payment` — look up `Lead` by raw `id` (no tenant scoping; deliberately reachable by anyone holding the Lead's UUID, matching this codebase's existing precedent for public per-entity links like `/api/upload/:token`). Missing/invalid lead → generic 404, no detail leaked. Look up `HcLeadgenConfig` for `consultation_fee_inr` and the HC's name. Response: `{hc_name, consultation_fee_inr, payment_status, scheduling_link}` — `scheduling_link` present only when `payment_status == 'paid'` (don't hand out the scheduling destination to someone who hasn't paid).

`POST /api/leads/:id/payment/order` — look up `Lead`, then `hc_payment_accounts` for the owning HC; if no row or `connected_at IS NULL`, return the structured error SPEC-0001's edge-case table already specifies ("consultation payment not yet available," not a 500). **If `leads.payment_reference` is already set and `payment_status` is still `unpaid`, return the existing order rather than creating a new Razorpay Order** — avoids littering the HC's Razorpay dashboard with duplicate abandoned orders every time the Lead reloads the page. Otherwise: **compute `amount_paise = hc_leadgen_config.consultation_fee_inr * 100`** (see §3 — this conversion is the single most important line in this task), call `razorpay_client.create_order(key_id=..., key_secret=..., amount_paise=..., notes={"hc_user_id": str(hc_user_id), "lead_id": str(lead_id)})`. **This call can raise** (Task 1's `create_order` deliberately propagates non-2xx responses rather than swallowing them) — this is a public, Lead-facing endpoint, so wrap the call and return a structured error (not 500) on failure, matching this codebase's established non-raising-at-the-boundary discipline for public endpoints (`intake.py`'s and `leads.py`'s own call sites around LLM generation are the precedent to follow, even though this is a different kind of external call). On success: store `leads.payment_reference = order["id"]`, `leads.status = "payment_pending"` (leave `payment_status` as `"unpaid"` — only the webhook, Task 6, sets it to `"paid"`). Return `{order_id, key_id, amount_paise}` — `key_id` only, never `key_secret`, which must never leave the backend.

Tests: order creation success (mock `razorpay_client.create_order`, assert the exact `amount_paise` sent for a known rupee fee — this is the named test §5 requires), order creation failure (mock `create_order` to raise → structured error, not a 500), no-connected-account structured error, reload-returns-existing-order idempotency, GET context before/after payment (scheduling_link hidden/shown correctly), 404 for an unknown lead id.

### Task 6 — `POST /api/payments/webhook` + payment-status gate on upload-token validation

In `payments.py` (Task 5's file): `POST /api/payments/webhook`. Takes `request: Request` directly (not a parsed Pydantic body) — you need the **raw bytes** via `await request.body()` before any JSON parsing, for HMAC verification. Parse JSON afterward (still untrusted). Extract `hc_user_id` from the payload's `notes` — confirm the exact JSON path for a `payment.captured` event against Razorpay's real webhook payload documentation during implementation; do not guess the nesting from this plan's phrasing alone.

Look up `hc_payment_accounts` for that `hc_user_id`; missing/not connected → reject 400 immediately (log as a suspicious event — this could be a forged webhook attempt, not just a data anomaly). Otherwise call `razorpay_client.verify_webhook_signature(raw_body=..., signature=request.headers.get("X-Razorpay-Signature", ""), webhook_secret=account.credentials["webhook_secret"])` — mismatch → reject 400, do not process the payload past this point. Follow the full algorithm in §3 exactly; this is the one part of this phase that must not be simplified or short-circuited for convenience.

Idempotency: look up the `Lead` by `payment_reference == order_id` (from the now-verified payload) and cross-check `hc_user_id` matches for extra tenant safety. If already `payment_status == 'paid'`, return 200 no-op (Razorpay retries on non-2xx; a duplicate `payment.captured` delivery for an already-processed payment must be a safe no-op, not an error or a double-write).

On genuine first-time success: `leads.payment_status = 'paid'`, `payment_reference` confirmed, `paid_at = now()`. **Also look up this Lead's currently-unused `LeadUploadToken` row (`used_at IS NULL` — unambiguous because Task 4 invalidates any prior unused ones on every Send) and set `expires_at = now() + 14 days`** — this is the D-8 mechanism that actually unlocks Step 2's button. It is easy to implement the `payment_status` update and forget this half; both must happen in the same handler. If somehow zero or more than one such row exists (a data anomaly Task 4's invalidation should prevent, but this handler shouldn't crash on it), log it as unexpected and don't raise — the payment itself still succeeded and must not fail the webhook response over it. Return 200 on every reached branch past signature verification, including edge-case bookkeeping paths — never make Razorpay retry a webhook that was already correctly handled.

**Upload-token payment gate** (modifies `backend/src/api/upload.py`): add a new check inside `_resolve_token()`, positioned **before** the existing `if upload_token.expires_at < datetime.now(UTC):` comparison. Look up the token's `Lead`; if `lead.payment_status != 'paid'`, return a new state — extend `UploadTokenStateOut`'s `Literal["not_found", "expired", "used", "valid"]` to include `"payment_pending"`, returned here. **This ordering is load-bearing, not stylistic**: with `expires_at` now nullable (Task 3), the existing comparison `upload_token.expires_at < datetime.now(UTC)` raises `TypeError` on `None` — for any unpaid Lead's token, `expires_at` genuinely is `None`, so the new payment check must return before that line is ever reached for such a token. Update `get_upload_token_state()`'s docstring/message constants to include the new state's copy, matching SPEC-0001's edge-case table wording ("Please complete your consultation booking first — then come back to this same link to upload your results."). Locate and update whatever frontend component renders `UploadTokenStateOut.state` (built in PHASE-03 — find it under `frontend/src/app/(public)/upload/[token]/` or wherever that phase actually placed it) to render the new state.

Tests: webhook success with a real computed HMAC against a fixture secret (not a mocked `True`) — `payment_status` flips, `paid_at` set, `LeadUploadToken.expires_at` set to a value ~14 days out; wrong signature → 400, no state change; unknown `hc_user_id` in `notes` → 400; duplicate delivery of an already-`paid` payment → 200 no-op, no double-write; `GET /api/upload/:token` for a `payment_pending` Lead's token → `"payment_pending"` state, no crash (this is the test that would have caught the `None < datetime` `TypeError` if the ordering were wrong — write it explicitly, don't just trust the ordering by inspection); `GET /api/upload/:token` after payment succeeds → falls through correctly into the existing valid/expired logic using the now-set `expires_at`.

### Task 7 — Frontend: payment page + settings connection UI + dev-seed step

`frontend/src/lib/api/payments.ts` (new) — Zod schemas + wrappers for `GET`/`POST /api/leads/:id/payment*`, matching Task 5/6's actual shipped contract exactly (read the real backend code, don't guess field names — same discipline PHASE-04's Task 6 followed for `leads.ts`).

`frontend/src/app/(public)/pay/[leadId]/page.tsx` (new — check where PHASE-03 actually placed `/upload/[token]/page.tsx` and mirror that route-group convention exactly, this plan's guessed path may not match). Fetch payment context on load. If `payment_status == 'paid'`: show a confirmation state with `scheduling_link` as an external CTA. Else: show HC name + fee + a "Pay" button. On click: `POST .../payment/order`, then load Razorpay's Checkout.js (`https://checkout.razorpay.com/v1/checkout.js` — a third-party script load; check this repo for an existing CSP or script-loading convention before adding it, flag if none exists rather than silently assuming it's fine), open `new Razorpay({key: key_id, order_id, amount: amount_paise, ...}).open()`. **Do not treat the client-side success callback as authoritative** — per D-3/this plan's own emphasis, only the webhook actually advances `payment_status`. On the client callback firing, poll `GET .../payment` every few seconds (with a reasonable timeout and a "still confirming, this can take a moment" message) until `payment_status` flips to `'paid'`, then show the scheduling CTA. On the client-side failure/dismiss handler, show the retry-safe "payment didn't go through, try again" state from SPEC-0001's edge-case table — nothing was held (D-3), so this is just re-showing the Pay button.

Settings connection UI — **nav placement needs SoJo's confirmation, same as PHASE-04's Task 6 was told for its own screen; do not silently pick a spot and move on if there's any ambiguity by the time you reach this task.** Recommended default if unconfirmed: a new "Payments" entry in the existing Settings hub (`SETTINGS_SECTIONS` in `frontend/src/app/(app)/settings/(hub)/layout.tsx`) — not nested under `/settings/onboarding`, since per SPEC-0001's Shared surfaces convention this needs to be reachable by `Unit_004_OneStopSpot`'s future F4 work too, and a hub-level entry is the more shareable placement than a leadgen-specific route. Form: three fields (Key ID, Key Secret, Webhook Secret) posting to `POST /api/hc/payment-account/connect`, plus a connected/not-connected indicator reading `GET /api/hc/payment-account`. If the placement can't be confirmed during this task, build it at the recommended default and flag it explicitly as provisional in your task report — exactly the situation SPEC-0001's Shared surfaces section describes and asks not to repeat silently.

Dev-seed step: a small one-off script (check for an existing `backend/scripts/` dev-seeding convention first and match it rather than inventing a new one) that reads `RAZORPAY_TEST_KEY_ID`/`RAZORPAY_TEST_KEY_SECRET`/`RAZORPAY_TEST_WEBHOOK_SECRET` from settings and upserts a `hc_payment_accounts` row for the current local dev HC — so SoJo can test the full flow end to end after populating `.env` without first clicking through the connection form by hand. Document clearly (in the script and in your task report) that this is a local-dev-only convenience; production credentials only ever arrive through the real connection flow.

Verification: `npx tsc --noEmit` (0 new errors beyond this repo's documented baseline), `npm run build`.

### Task 8 — Whole-flow integration test + manual Razorpay test-mode verification

Integration test exercising the full chain in one flow: submit questionnaire → Send (assert `LeadUploadToken` minted with `expires_at IS NULL`, email sent with both links correctly constructed) → `GET` payment context → `POST` order (mocked `razorpay_client`, **assert the exact `amount_paise` value** for a known configured fee — this is the named test §5 requires, not folded into a generic assertion) → simulate the webhook with a **real computed HMAC signature** against a fixture `webhook_secret` → assert `payment_status = 'paid'`, `paid_at` set, `LeadUploadToken.expires_at` now set → `GET /api/upload/:token` for that same token now returns `"valid"` (would have returned `"payment_pending"` before the webhook).

Also: a dedicated wrong-signature-rejected test in this same whole-flow context (not just Task 6's isolated unit test) — confirm a forged webhook cannot advance a real Lead's state end to end.

**Manual verification — this phase's bar is higher than PHASE-04's, and deliberately so: this is the first real-money-adjacent code in the platform.** Using SoJo's real Razorpay test-mode credentials (from `.env`, seeded into the local dev HC via Task 7's dev-seed step): a real Order creation, a real hosted Checkout flow (Razorpay's documented test UPI/card instruments) for both a success and an induced-decline path, and a real webhook delivered from Razorpay's own servers to a reachable local endpoint — this needs a tunnel (check `docs/decisions/` for whether this repo already has a tunneling convention from other external-callback work, e.g. the Google Calendar OAuth integration, before introducing a new tool for it). Confirm the full browser walkthrough from §5: send a panel, receive the D-8 email, click Step 2 first and see the gated state, complete Step 1, get handed off to `scheduling_link`, reopen the *same* Step 2 link and see it now work.

**Verification, end to end**: every checkbox under SPEC-0001's Payment/Scheduling-handoff/upload-token acceptance criteria, full backend + frontend suite green, the real Razorpay round trip completed (not simulated), manual walkthrough completed.
