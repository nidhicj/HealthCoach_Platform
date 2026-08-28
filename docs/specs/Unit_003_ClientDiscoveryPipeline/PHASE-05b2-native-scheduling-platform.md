# PHASE-05b2: Native scheduling platform (future direction — placeholder)

**Unit**: Unit_003_ClientDiscoveryPipeline
**Status**: Not started — deliberately unscoped placeholder; revisit and re-derive the actual approach when this is picked up, do not treat any option below as decided.
**Verification date**: N/A — no implementation exists or is scoped
**Implements**: `SPEC-0001-client-discovery-pipeline.md`'s "Out of scope (future)" entry — "Native calendar / scheduling (replacing the external scheduling handoff) — owned by a separate workstream, not this spec." This file is that workstream's placeholder, not an activation of it.
**ADRs implemented**: None
**Naming note**: fourth of a 2×2 track/iteration scheme under the "05" umbrella — track B (scheduling) × iteration 2 (this file, future native platform). Unlike `PHASE-05a1`/`PHASE-05a2`/`PHASE-05b1`, this file is intentionally NOT a ready-to-execute plan — see Status above and §5 below.

---

## 1. Why this exists

Captured here as durable context for whichever future session picks this up, so the reasoning doesn't have to be rediscovered from scratch — not a commitment to any specifics below.

Once Tapas scales past one pilot HC, the likely long-term direction is to stop depending on an external scheduling tool (Cal.com, `PHASE-05b1`) and build native booking UX instead. This is grounded in how comparable real businesses appear to operate, researched during the conversation that produced this file:

- **Therapist marketplaces Headway and Alma** build native booking UX themselves and only read external calendars (Google/Outlook) for conflict-avoidance — they don't depend on Calendly/Cal.com-style tools long-term.
- **SimplePractice** (a single-practice tool, 225k+ practitioners) builds scheduling fully native too — partly because generic consumer scheduling tools like Calendly are not built/certified for handling health-adjacent data. This is a HIPAA-specific finding in the US, not a legal conclusion transferable to India's DPDP regime as-is — but the underlying principle (keep health-adjacent data off generic consumer scheduling tools) is worth carrying forward as a flagged consideration when this phase is actually designed, not asserted as settled law here.

## 2. The one concrete, already-known blocker

`Unit_004_OneStopSpot`'s SPEC-0001 (D-30, elaborated in `PHASE-01e-calendar-integration.md`) documents that while its Google OAuth app remains in Google's "Testing" publishing status (true today — no verified domain/privacy policy yet), Google issues refresh tokens that expire after 7 days for test users, requiring weekly reconnect. Any native booking flow that depends on a live Google Calendar connection inherits this exact limitation. Real OAuth app verification (a privacy policy, domain ownership, possibly a Google review) would need to be solved before a native booking flow built on this pattern is production-viable — this is the first concrete thing that would need solving here, independent of anything else about this phase's design.

## 3. Reuse candidates already in the codebase (study before designing, do not assume directly reusable)

- `backend/src/db/models/calendar.py` (`GoogleCalendarConnection`)
- `backend/src/auth/calendar_oauth.py`
- `backend/src/api/calendar.py` (`_get_valid_access_token`, `GET`/`POST /api/calendar/events`)

These were built by `Unit_004_OneStopSpot` for a different purpose: an HC manually linking an existing Session to a Google Calendar event they pick themselves — no public/anonymous Lead-facing self-serve booking involved anywhere in that flow. Not directly reusable for this phase's actual need (a Lead with no platform account booking a slot against an HC's live availability), but the OAuth-connection/token-refresh code pattern is a real, worked precedent to study before designing this phase for real — particularly `_get_valid_access_token`'s refresh-on-expiry/revoke-on-failure logic and its `structlog` observability convention.

## 4. A noted alternative, not decided, worth revisiting at design time

Cal.com is open-source and self-hostable. A mature Tapas could self-host its own Cal.com instance for full branding/control, avoiding both per-HC external accounts (`PHASE-05b1`'s posture) and Cal.com's ~$299/mo hosted Platform tier — at the cost of real DevOps/maintenance burden this codebase doesn't currently carry for any comparable piece of infrastructure. Whether a fully native build (on Google Calendar `freebusy`+`events.insert`) or a self-hosted-Cal.com approach ends up being the actual future direction should be re-evaluated fresh when this phase is picked up — neither is decided here.

## 5. Explicitly not included in this file

Per instruction, this file does not contain a Deliverables list, a Task breakdown, or a Scope/Not-in-scope split the way `PHASE-05a1`/`PHASE-05a2`/`PHASE-05b1` have — this is a Scope/Context/Open-considerations placeholder, not a ready-to-execute plan. Do not add one without a fresh design conversation; nothing above should be read as locked in.
