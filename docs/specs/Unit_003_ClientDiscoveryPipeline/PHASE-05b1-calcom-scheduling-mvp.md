# PHASE-05b1: Cal.com scheduling MVP

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. **Do not begin implementation until §6's account-side prerequisites are done — Task 0 in particular (confirming Cal.com's metadata→webhook passthrough actually works live) determines whether Tasks 3-4 below need to change shape. This doc is written and ready, not yet cleared to execute.**

**Unit**: Unit_003_ClientDiscoveryPipeline
**Status**: Draft — written and ready, execution gated on §6 (SoJo/the test HC's Cal.com account setup, in particular Task 0's live metadata-passthrough verification)
**Verification date**: TBD
**Implements**: `SPEC-0001-client-discovery-pipeline.md` §Stage 4 (scheduling handoff — the round-trip half; the redirect-only half already shipped in `PHASE-05a1`), §Open questions → the `leads.scheduled_at`/`meeting_link` dead-columns entry (superseding that entry's 2026-08-27 "stays inside PHASE-05" resolution — see SPEC-0001's own Changelog for the correction), §Decisions log D-3 (payment/scheduling stay decoupled — unchanged by this phase; this phase only makes the *scheduling* half of that decoupled pair real, it doesn't touch payment)
**ADRs implemented**: None — same convention as `PHASE-05a1`/`PHASE-05a2` (scheduling-architecture decisions recorded in SPEC-0001's own Decisions log, not a separate ADR); this phase should add a new decision entry there once it ships, recording why Cal.com (each-HC-owns-their-account) was chosen over Cal.com's paid Platform API and why a native build was deferred (see §1)
**Naming note**: third of a 2×2 track/iteration scheme under the "05" umbrella — track B (scheduling) × iteration 1 (this file, Cal.com MVP). `PHASE-05a1`/`PHASE-05a2` are the unrelated payment track (A). `PHASE-05b2` is track B iteration 2 (a future native scheduling platform) — a deliberately lightweight placeholder, not a committed plan; see that file.

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific I haven't provided. Ready?

## 1. Scope

This phase replaces `PHASE-05a1`'s bare "redirect to a flat, HC-pasted external `scheduling_link` string" with a real round-trip: each HC signs up for their own free individual Cal.com account (mirroring this spec's existing D-2 posture for Razorpay — each HC owns their own account, Tapas is never in the booking-data path), Tapas constructs a per-Lead booking link carrying the Lead's identity as Cal.com metadata, and a new webhook receiver captures `BOOKING_CREATED` events to write `leads.scheduled_at`/`meeting_link` and feed them into `generate_lead_brief` (which currently accepts no appointment inputs at all — SPEC-0001's own flagged gap, owned by this phase now).

Cal.com's free/individual plan is genuinely unlimited on event types, calendar connections, and webhooks for a single account — no volume cap was found while researching this. Cal.com's own multi-tenant "Platform API" (for managing many HCs' bookings centrally from one Tapas-side integration) is a separate, paid tier starting around $299/month — explicitly **out of scope** for this MVP phase. Each-HC-owns-their-account is the deliberate, cheaper posture for a single-pilot-HC stage; see `PHASE-05b2` for when this may need to change.

**Not in scope**: `PHASE-05a1`/`PHASE-05a2`'s payment work (untouched — D-3's payment/scheduling decoupling is preserved; this phase only makes the scheduling half real). Cal.com's paid Platform API / any multi-tenant Cal.com integration. A native, Tapas-built booking UI (that is `PHASE-05b2`, deliberately unscoped for now). Redesigning the HC-facing Stage 1 setup UI where `scheduling_link` is configured — the field's *meaning* changes (see §3) but the settings surface itself is not otherwise redesigned. Any change to `PHASE-05a1`'s email copy — the Lead-facing "Book your consultation" link continues to point at the same `pay_link`/payment page; only what the paid-confirmation CTA links to afterward changes.

## 2. Deliverables planned

- `backend/src/db/models/scheduling.py` (new) — `HcSchedulingAccount` model, one row per HC, mirroring `payments.py`'s `HcPaymentAccount` shape and concern-based-file precedent
- Migration: create `hc_scheduling_accounts`
- `backend/src/config.py` — new `scheduling_credentials_encryption_key: str = ""` setting, matching the existing `razorpay_credentials_encryption_key` pattern
- `backend/src/api/scheduling.py` (new) — `POST /api/scheduling/webhook` (Cal.com webhook receiver) plus whichever connection surface Task 2 lands on for the HC's webhook secret
- `backend/src/api/payments.py` (modified) — `GET /api/leads/:id/payment`'s `scheduling_link` field changes from a flat pass-through of `hc_leadgen_config.scheduling_link` to a per-Lead-constructed URL (`?metadata[lead_id]=<uuid>` appended)
- `backend/src/llm_service/__init__.py` (modified) — `generate_lead_brief` gains `scheduled_at`/`meeting_link` inputs, threaded into the brief prompt
- Frontend: no new Lead-facing page — the existing paid-confirmation state on `/pay/[leadId]` already renders `scheduling_link` as an external CTA (`PHASE-05a1` Task 7); this phase only changes what URL that CTA points to
- Settings: a place for the HC to paste their Cal.com webhook secret (exact placement decided at Task 2)

## 3. Decisions to carry into implementation

These are already made/researched (see the conversation that produced this plan) — implementers should not re-derive or re-research them, only implement them correctly:

- **Each HC owns their own free Cal.com account** — mirrors D-2's existing Razorpay posture. Cal.com's multi-tenant Platform API (paid, ~$299/mo+) is out of scope; revisit only if/when scaling past one pilot HC makes the per-account model genuinely unworkable (see `PHASE-05b2`).
- **Location default: Cal.com's own "Cal Video"** — zero extra OAuth needed, the HC picks it directly inside Cal.com's own Event Type settings. **Alternative, not required**: connect Google Meet via a *Cal.com-side* Google OAuth grant (the HC granting Cal.com — not Tapas — access, `calendar.events`+`calendar.readonly` scopes), configured entirely inside Cal.com's own UI. **Do not confuse this with `Unit_004_OneStopSpot`'s own Google Calendar OAuth connection to Tapas itself** (`backend/src/db/models/calendar.py`'s `GoogleCalendarConnection`, `backend/src/auth/calendar_oauth.py`) — two unrelated OAuth grants, to two different applications, for two different purposes. This phase's code never touches Unit_004's calendar OAuth machinery.
- **Per-Lead link construction, not a flat pass-through**: Cal.com's documented mechanism for attaching arbitrary metadata to a booking is a query param on the booking link — `?metadata[lead_id]=<uuid>` — carried back into the `BOOKING_CREATED` webhook payload as `payload.metadata.lead_id`. `GET /api/leads/:id/payment` must construct this per-Lead, not return the HC's stored `scheduling_link` verbatim (today's `PHASE-05a1` behavior — `backend/src/api/payments.py`'s `scheduling_link` field, currently `config.scheduling_link if lead.payment_status == "paid" else None`).
- **Webhook signature verification mirrors `razorpay_client.verify_webhook_signature` almost exactly**: Cal.com's `X-Cal-Signature-256` header is an HMAC-SHA256 hex digest over the raw pre-JSON-parse request body, keyed with the HC's webhook secret. Mirror `backend/src/lib/razorpay_client.py`'s function in full — pure function, raw bytes in, `hmac.compare_digest` for constant-time comparison, no I/O. Do not invent a second verification style for this second webhook receiver.
- **`hc_scheduling_accounts`'s webhook secret uses the existing `EncryptedJSON` mechanism**, parameterized with the new `scheduling_credentials_encryption_key` — same reuse discipline `PHASE-05a1` already established for `hc_payment_accounts.credentials` (`backend/src/db/encrypted_json.py`, `backend/src/db/models/payments.py` is the pattern to mirror). Do not invent a new encryption mechanism.
- **Tenant-safety discipline mirrors the Razorpay webhook exactly**: on `BOOKING_CREATED`, cross-check that the Lead resolved via `payload.metadata.lead_id` actually belongs to the HC whose secret verified the signature, before writing anything. The signature check selects *which* HC's webhook this is; the Lead/HC ownership match is a second, non-negotiable check — the same two-step discipline `PHASE-05a1`'s webhook handler already applies for Razorpay's `notes.hc_user_id`.
- **`generate_lead_brief`'s gap is real and owned by this phase**: `backend/src/llm_service/__init__.py::generate_lead_brief` currently takes no appointment inputs at all (confirmed by reading its signature — `db`, `lead_id`, `hc_user_id`, `blood_report_text`, `request_id`). This phase must extend it to accept and use `scheduled_at`/`meeting_link` once populated, closing SPEC-0001's Open-questions gap for real.
- **Must be verified live, not trusted from docs alone**: there is a documented (GitHub) history of Cal.com's metadata-query-param → webhook-payload passthrough not always working reliably across versions. Task 0 below (a real live test booking, confirmed before finalizing Tasks 3/4's exact design) mirrors the exact discipline `PHASE-05a2`'s own Task 0 already applies to its own unverified webhook-routing assumption — do not skip it or treat this plan's description of the mechanism as confirmed.

## 4. Source docs to consult before implementing

- `docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md` — §Stage 4, §Open questions (`leads.scheduled_at`/`meeting_link` entry, now owned by this phase), §Decisions log D-2/D-3
- `docs/specs/Unit_003_ClientDiscoveryPipeline/PHASE-05a1-payment-and-scheduling-handoff.md` — the shipped payment flow and bare redirect handoff this phase extends; read its §3 webhook-verification algorithm in full
- `backend/src/lib/razorpay_client.py` — `verify_webhook_signature`, the exact pattern this phase's Cal.com signature verification mirrors
- `backend/src/db/encrypted_json.py`, `backend/src/db/models/payments.py` — the `EncryptedJSON` mechanism and `HcPaymentAccount`'s shape, the pattern `HcSchedulingAccount` mirrors
- `backend/src/api/payments.py` — `GET /api/leads/:id/payment`'s current `scheduling_link` field (flat pass-through), the code this phase changes
- `backend/src/llm_service/__init__.py` — `generate_lead_brief`'s current signature (no appointment inputs), the gap this phase closes
- `backend/src/db/models/leadgen.py` — `HcLeadgenConfig.scheduling_link`, `Lead.scheduled_at`/`meeting_link` (already-added-but-dead columns from `PHASE-05a1` Task 3)
- Cal.com's own current webhook and booking-metadata documentation — this plan's mechanism (`X-Cal-Signature-256`, `?metadata[]` query params, `BOOKING_CREATED`) was researched while writing this plan, but per §3's flag, the metadata→payload passthrough specifically must be confirmed live (Task 0), not trusted from docs alone

## 5. Verification

Mirrors `PHASE-05a1`'s own bar (SPEC-0001's Payment/Scheduling-handoff acceptance criteria), plus:

- A real Cal.com test booking through a real webhook delivery via a real tunnel (same ngrok-or-equivalent local-dev need `PHASE-05a1`/`PHASE-05a2`'s Razorpay work already established) — not mocks alone. This is the platform's second webhook receiver and its first non-payment one; mock-only verification is not sufficient here, the same standard `PHASE-05a1` set for itself.
- Real Lead correlation confirmed end to end: a real booking's `metadata.lead_id` resolved to the correct Lead, cross-checked against the correct HC.
- `leads.scheduled_at`/`meeting_link` populated from a real webhook payload, confirmed by direct DB read, not just against a mocked payload shape.
- A real `generate_lead_brief` call, with a real uploaded blood report, confirmed to include the populated appointment details in the generated brief text.
- Webhook signature verification tested against a real computed HMAC fixture (success + wrong-signature-rejected paths), mirroring `PHASE-05a1`'s own named test for `verify_webhook_signature`.
- Full backend + frontend suite green.

---

## 6. What SoJo (or the test HC) needs to go acquire before this phase can be implemented

- [ ] **Sign up for a free individual Cal.com account** (the test HC's own account, not a Tapas-owned one — mirrors D-2's per-HC-ownership posture).
- [ ] **Create an Event Type** (e.g. "Consultation") — this produces the actual booking URL that becomes the new `scheduling_link` value Tapas builds per-Lead links from.
- [ ] **Pick a location for the Event Type.** Default recommendation: Cal.com's own built-in "Cal Video" (zero extra OAuth). Alternative: connect Google Meet via a Cal.com-side Google OAuth grant (`calendar.events`+`calendar.readonly` scopes) — independent of, and not to be confused with, Unit_004_OneStopSpot's own Google Calendar OAuth connection to Tapas.
- [ ] **In Cal.com Settings → Developer → Webhooks: create a webhook.** Subscriber URL = Tapas's new `POST /api/scheduling/webhook` endpoint (needs an ngrok tunnel for local dev — same tunneling need `PHASE-05a1`/`PHASE-05a2`'s Razorpay work already established). Pick a secret (becomes `hc_scheduling_accounts`'s stored secret). Trigger = `BOOKING_CREATED` at minimum.
- [ ] **Task 0 — confirm live, in a real sandbox test booking, that Cal.com's `?metadata[lead_id]=<uuid>` mechanism actually survives into the `BOOKING_CREATED` webhook payload as `payload.metadata.lead_id`, before Task 3/4's design is finalized.** There is a documented history of this passthrough not always working reliably across Cal.com versions — this single fact determines whether Tasks 3-4 are correct as written or need a different Lead-correlation mechanism (e.g. a custom booking question, if metadata proves unreliable). Document the answer plainly (a real test booking + the actual received webhook payload, not a doc citation) and hand it back before implementation starts — mirrors `PHASE-05a2`'s own Task 0 discipline exactly.

## Implementation Plan

**Not dispatched yet — written so it's ready the moment §6 is cleared, not because implementation should start now.** Ordered task breakdown, to be executed via `superpowers:subagent-driven-development` once §6's checklist (especially Task 0) is done, mirroring `PHASE-05a1`/`PHASE-05a2`'s own execution discipline.

### Task 0 — Confirm Cal.com's metadata→webhook passthrough live (blocks Task 3/4 design)

Not code — a real sandbox test using the test HC's actual Cal.com account (§6): create a booking against the Event Type's link with `?metadata[lead_id]=<a-test-uuid>` appended, confirm the resulting `BOOKING_CREATED` webhook delivery (via the §6 tunnel) actually contains `payload.metadata.lead_id` equal to that UUID. If it does not survive, this finding determines the real Lead-correlation mechanism for Tasks 3-4 — do not proceed with Tasks 3-4 as currently scoped until confirmed either way.

### Task 1 — `hc_scheduling_accounts` model + migration

New file `backend/src/db/models/scheduling.py`, mirroring `payments.py`'s `HcPaymentAccount` shape and concern-based-file precedent: `HcSchedulingAccount` — `id` UUID PK, `hc_user_id` UUID FK → `users.id` UNIQUE, `credentials: Mapped[dict | None]` using `EncryptedJSON(settings_key="scheduling_credentials_encryption_key")` (storing at minimum `{"webhook_secret": ...}`), `connected_at: Mapped[datetime | None]`, `created_at`, `updated_at`. Migration: new table.

Settings (`backend/src/config.py`): add `scheduling_credentials_encryption_key: str = ""`, matching the existing `razorpay_credentials_encryption_key` pattern exactly.

Tests: model round-trips encrypted credentials (mirror `test_model_hc_payment_accounts.py`'s pattern).

### Task 2 — Connection surface for the HC's webhook secret

Decide and implement where the HC pastes their Cal.com webhook secret. Two real options — pick one and document why in your task report: (a) extend the existing Stage 1 `/settings/onboarding` Setup tab, alongside `scheduling_link`, with a new "Webhook secret" field; (b) a new minimal settings surface mirroring `PHASE-05a1` Task 2's `/api/hc/payment-account*` shape (`GET`/`POST /api/hc/scheduling-account`). This plan recommends (a) as the smaller change — `scheduling_link` and the webhook secret are configured together, by the same HC, at the same point in setup — but confirm placement with SoJo before building, per SPEC-0001's Shared-surfaces convention.

Tests: connect/read round trip, cross-tenant isolation, unauthenticated → 401.

### Task 3 — Per-Lead scheduling link construction (modifies `backend/src/api/payments.py`)

`GET /api/leads/:id/payment`'s `scheduling_link` field changes from `config.scheduling_link if lead.payment_status == "paid" else None` (today's flat pass-through) to a per-Lead-constructed URL: `f"{config.scheduling_link}?metadata[lead_id]={lead.id}"` (confirm exact query-param encoding against Cal.com's real documented format, and against Task 0's live finding, before finalizing). Still withheld until `payment_status == "paid"`, unchanged from `PHASE-05a1`'s existing gating.

Tests: constructed URL contains the correct Lead id in the correct query-param shape; still withheld pre-payment (regression test against `PHASE-05a1`'s existing behavior).

### Task 4 — `POST /api/scheduling/webhook`

New file `backend/src/api/scheduling.py`. Takes `request: Request` directly (not a parsed Pydantic body), same raw-bytes-before-parsing reason `PHASE-05a1`'s Razorpay webhook does. Verify `X-Cal-Signature-256` via a new function mirroring `backend/src/lib/razorpay_client.py::verify_webhook_signature` in full. Resolve the HC via whatever Task 2's connection surface establishes; resolve the Lead via `payload.metadata.lead_id` (or Task 0's actual finding); cross-check the Lead belongs to the signature-verified HC before writing anything. On `BOOKING_CREATED`: write `leads.scheduled_at` (payload start-time field) and `leads.meeting_link` (payload location field — Cal Video's join link, or the connected Google Meet link, per §6's choice). Idempotency: duplicate delivery for an already-scheduled Lead is a safe no-op, mirroring the Razorpay webhook's `payment_status == 'paid'` no-op precedent.

Tests: webhook success with a real computed HMAC against a fixture secret; wrong-signature → 400; unknown HC → 400; cross-tenant Lead mismatch rejected; duplicate delivery → no-op.

### Task 5 — Thread `scheduled_at`/`meeting_link` into `generate_lead_brief`

Extend `generate_lead_brief`'s signature (`backend/src/llm_service/__init__.py`) to accept `scheduled_at: datetime | None`/`meeting_link: str | None`, threaded into whatever prompt template it loads (confirm the exact prompt file and how other optional fields are conditionally templated). Closes SPEC-0001's Open-questions entry for real.

Tests: brief generation with populated appointment fields includes them in the rendered prompt/output; brief generation with `None` values (Lead hasn't scheduled yet — a real, expected state, not an error) still succeeds, omitting the appointment section gracefully.

### Task 6 — Whole-flow integration test + manual Cal.com verification

Integration test: Send → pay → `GET /api/leads/:id/payment` returns the per-Lead-constructed scheduling link → simulate `BOOKING_CREATED` webhook with a real computed HMAC → assert `leads.scheduled_at`/`meeting_link` populated → upload flow → `generate_lead_brief` call includes the appointment details.

**Manual verification — mirrors `PHASE-05a1`'s "first real-money/real-external-dependency-adjacent code" bar**: a real Cal.com test booking through the real per-Lead link, a real webhook delivered through a real tunnel, real Lead correlation confirmed, real `scheduled_at`/`meeting_link`/brief population confirmed end to end — not just unit-tested against a mocked payload.
