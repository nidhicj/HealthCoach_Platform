# PHASE-01e — Google Calendar/Meet Integration (F6 extension) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan builds directly on PHASE-01d (`meeting_url` free-text field, already shipped) — read that file's Self-review section if you need PHASE-01d's exact current state, but do not re-implement anything from it.

**Goal:** Extend F6 beyond free-text links: the HC connects their Google Calendar, gets a full month/week calendar view inside the session page, and links a specific Google Calendar event (existing, with whatever Meet/Zoom link it already carries — or newly created with a Google Meet link) to a specific Tapas session. HC-side only; no client-facing routes (same boundary as PHASE-01d, blocked on OQ-7).

**Architecture:** Two new server-side concerns, both additive:
1. `google_calendar_connections` table — one encrypted-credentials row per HC who connects Calendar (Google OAuth tokens are **not persisted anywhere today** — confirmed by reading `backend/src/auth/oauth.py`, which discards them after the userinfo call).
2. `sessions.google_calendar_event_id` — one new nullable column. `meeting_url` is untouched; linking an event derives `meeting_url` once, at link time, then it's an ordinary editable field again (no ongoing sync).

No calendar event content (attendee emails, unrelated titles) is ever persisted — the calendar view is fetch-on-demand against Google; only a linked event's `id` + `hangoutLink` get written, once, on explicit link.

**Tech stack:** Same as the rest of Unit_004 — FastAPI/SQLAlchemy async backend, Next.js/TypeScript frontend, Alembic migrations. New frontend dependency: `date-fns` only (date arithmetic for the week view — see Task 9's rationale). No new backend dependency — Google Calendar API calls go through raw `httpx`, mirroring `oauth.py`'s existing pattern (this repo's ADR-0005 deliberately avoids Google's official client libraries).

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Tests hit a real PostgreSQL DB (`parivarthan_test`) — no mocking the DB. Mock **Google's HTTP responses** (via `httpx`'s `MockTransport` or `respx`/monkeypatching `make_http_client`, matching whatever pattern `backend/tests` already uses for `oauth.py`'s tests — check `backend/tests/unit/test_oauth.py` or similar before choosing) — never make real calls to Google in tests.
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before running backend commands.
- OAuth scope for Calendar: exactly `openid email profile https://www.googleapis.com/auth/calendar.events` — least-privilege (not the broader `.../auth/calendar` scope).
- The existing HC login flow (`/api/auth/google/*`) and the Client flow (`/api/auth/client/*`) are **not modified in any way** by this phase. Calendar connection is a new, separate, additive action an already-logged-in HC takes.
- `EncryptedJSON`'s generalization (Task 1) must not change `Client.demographics`'s existing behavior — that's a regression-tested requirement, not a nice-to-have.
- Every real Google API call (list/insert events, token refresh) logs via this repo's existing `structlog` pattern: operation name, hc_id, latency_ms, outcome — mirrors CLAUDE.md's "LLM calls are observable" principle applied to this external API.
- No calendar event content is ever written to the DB except: the linked event's `id` (on `sessions.google_calendar_event_id`) and its `hangoutLink` (copied into the existing `sessions.meeting_url`).
- Follow `test_sessions.py`'s established convention: local `_create_client`/`_create_session`-style helpers per test file. `hc_user`/`hc_headers` ARE legitimate shared fixtures already in `backend/tests/integration/conftest.py` — reuse them, don't re-declare.
- Frontend: match this app's existing design system (Tailwind + custom tokens visible throughout `NotesTab` and the rest of the session page) — no default styling from a UI library.

---

## Task 1: Generalize `EncryptedJSON` to accept a settings key

**Files:**
- Modify: `backend/src/db/encrypted_json.py`
- Test: `backend/tests/unit/` (new or existing file covering `encrypted_json.py` — check for one first)

**Interfaces:**
- Produces: `EncryptedJSON(settings_key: str = "demographics_encryption_key")` — a constructor param, default preserves current behavior exactly.

- [ ] **Step 1.1: Write the failing tests**

Add tests (new file `backend/tests/unit/test_encrypted_json.py` if none exists covering this already):
```python
import pytest
from src.db.encrypted_json import EncryptedJSON

def test_default_settings_key_is_demographics(monkeypatch):
    # existing behavior: default constructor still reads demographics_encryption_key
    col = EncryptedJSON()
    encrypted = col.process_bind_param({"a": 1}, None)
    assert col.process_result_value(encrypted, None) == {"a": 1}

def test_custom_settings_key_round_trips(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_ENCRYPTION_KEY", "")  # falls back to dev key, distinct instance still works
    col = EncryptedJSON(settings_key="google_calendar_encryption_key")
    encrypted = col.process_bind_param({"token": "abc"}, None)
    assert col.process_result_value(encrypted, None) == {"token": "abc"}

def test_cross_key_decrypt_fails_gracefully(monkeypatch):
    # Two real (non-fallback) keys must not decrypt each other's ciphertext.
    from cryptography.fernet import Fernet
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()
    monkeypatch.setenv("DEMOGRAPHICS_ENCRYPTION_KEY", key_a)
    monkeypatch.setenv("GOOGLE_CALENDAR_ENCRYPTION_KEY", key_b)
    from src.config import get_settings
    get_settings.cache_clear()
    col_a = EncryptedJSON()  # demographics key
    encrypted = col_a.process_bind_param({"secret": "x"}, None)
    col_b = EncryptedJSON(settings_key="google_calendar_encryption_key")
    assert col_b.process_result_value(encrypted, None) is None  # graceful, not a crash
    get_settings.cache_clear()
```
Adjust exact fixture/monkeypatch mechanics to match whatever `test_jwt_utils.py`/existing unit tests already do for env-var-driven settings (check before assuming `get_settings.cache_clear()` is the right call — `conftest.py` at the integration layer already does this same pattern at import time, confirm it's accessible/correct for a unit test context too).

- [ ] **Step 1.2: Run — confirm failure** (`EncryptedJSON()` currently takes no args)

- [ ] **Step 1.3: Implement**

```python
def _fernet(settings_key: str) -> Fernet:
    from src.config import get_settings
    raw = getattr(get_settings(), settings_key)
    key = raw.encode() if raw else _DEV_FALLBACK_KEY
    return Fernet(key)


class EncryptedJSON(TypeDecorator):
    """Store a Python dict as Fernet-encrypted JSON in a TEXT column."""

    impl = Text
    cache_ok = True

    def __init__(self, settings_key: str = "demographics_encryption_key", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._settings_key = settings_key

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet(self._settings_key).encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return json.loads(_fernet(self._settings_key).decrypt(value.encode()))
        except Exception:
            logger.warning("encrypted_json_decrypt_failed", settings_key=self._settings_key, exc_info=True)
            return None
```

Add `google_calendar_encryption_key: str = ""` to `backend/src/config.py`'s settings class, alongside the existing `demographics_encryption_key`.

- [ ] **Step 1.4: Run existing `Client.demographics` tests + new tests — confirm all pass, no regression**

- [ ] **Step 1.5: Commit**
```bash
git add backend/src/db/encrypted_json.py backend/src/config.py backend/tests/unit/test_encrypted_json.py
git commit -m "feat(encryption): generalize EncryptedJSON to accept a settings key"
```

---

## Task 2: `google_calendar_connections` table + model + migration

**Files:**
- Create: `backend/src/db/models/calendar.py`
- Modify: `backend/src/db/models/__init__.py` (export `GoogleCalendarConnection`)
- Create: Alembic migration
- Test: `backend/tests/integration/test_calendar_connections.py` (new)

**Interfaces:**
- Produces: `GoogleCalendarConnection` model — `id`, `hc_user_id` (FK→users, unique), `google_account_email`, `scope_granted`, `credentials` (`EncryptedJSON(settings_key="google_calendar_encryption_key")`, holds `{"access_token": str, "refresh_token": str}`), `access_token_expires_at` (plain `TIMESTAMP(timezone=True)`, not encrypted — needs cheap comparison), `connected_at`, `revoked_at` (nullable), `updated_at`.

- [ ] **Step 2.1: Write the failing test**
```python
@pytest.mark.asyncio
async def test_connection_round_trips_encrypted_credentials(db, hc_user):
    conn = GoogleCalendarConnection(
        hc_user_id=hc_user.id,
        google_account_email="coach@example.com",
        scope_granted="openid email profile https://www.googleapis.com/auth/calendar.events",
        credentials={"access_token": "at-123", "refresh_token": "rt-456"},
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    assert conn.credentials == {"access_token": "at-123", "refresh_token": "rt-456"}
```

- [ ] **Step 2.2: Run — confirm failure** (model doesn't exist)

- [ ] **Step 2.3: Implement the model** (per Interfaces above — mirror `backend/src/db/models/clients.py`'s use of `EncryptedJSON` for import style/conventions)

- [ ] **Step 2.4: Register in `backend/src/db/models/__init__.py`** so Alembic autogenerate and `conftest.py`'s `import src.db.models` pick it up.

- [ ] **Step 2.5: Generate + fill in the migration**
```bash
cd backend && alembic revision -m "add_google_calendar_connections"
```
Use explicit `from sqlalchemy.dialects import postgresql` + `postgresql.UUID(as_uuid=True)` (matches this repo's established convention — PHASE-01c's migration was fixed for missing this exact import). Include a unique constraint on `hc_user_id` and `ondelete="CASCADE"` on the FK.

- [ ] **Step 2.6: Apply migration, run tests, confirm pass**

- [ ] **Step 2.7: Commit**

---

## Task 3: `calendar_oauth.py` — incremental-consent OAuth helpers

**Files:**
- Create: `backend/src/auth/calendar_oauth.py`
- Test: `backend/tests/unit/test_calendar_oauth.py` (new, mirror whatever mocking pattern `backend/tests/unit/test_oauth.py` uses — read it first)

**Interfaces:**
```python
_CALENDAR_SCOPES = "openid email profile https://www.googleapis.com/auth/calendar.events"

@dataclass
class GoogleCalendarTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str

class CalendarReauthRequired(Exception):
    """Raised when Google rejects a refresh_token (revoked/expired)."""

def build_calendar_connect_url(*, client_id: str, redirect_uri: str, state: str, code_challenge: str) -> str: ...
async def exchange_code_for_calendar_tokens(*, code: str, code_verifier: str, redirect_uri: str, client_id: str, client_secret: str) -> GoogleCalendarTokens: ...
async def refresh_calendar_access_token(*, refresh_token: str, client_id: str, client_secret: str) -> tuple[str, int]:  # (new_access_token, expires_in)
```

Mirror `oauth.py`'s `generate_pkce_pair`/`build_authorization_url`/`exchange_code_for_userinfo` structure and its `make_http_client()` usage exactly — same file, adjacent module, same conventions.

- [ ] **Step 3.1: Write failing tests covering:**
  - `build_calendar_connect_url` includes `scope=<url-encoded _CALENDAR_SCOPES>`, `prompt=consent`, `include_granted_scopes=true`.
  - `exchange_code_for_calendar_tokens` happy path returns all four fields from a mocked Google token response.
  - Google response missing `refresh_token` → raises a clear, specific exception (not `KeyError`).
  - `refresh_calendar_access_token` happy path returns `(access_token, expires_in)`.
  - `refresh_calendar_access_token` on a mocked Google `400 invalid_grant` response raises `CalendarReauthRequired`.

- [ ] **Step 3.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 4: `/connect` + `/callback` routes

**Files:**
- Modify: `backend/src/auth/router.py`
- Test: `backend/tests/integration/test_calendar_oauth_routes.py` (new)

**Interfaces:**
- `GET /api/auth/google/calendar/connect` — requires HC auth (reuse whatever dependency the existing `/google/start` route uses for state-store/PKCE stashing, extended to also store `hc_user_id` alongside `verifier` so `/callback` knows which HC to attach the connection to). Returns `{"auth_url": str}`.
- `GET /api/auth/google/calendar/callback` — public route (Google redirects the browser here directly, no bearer token available — the `hc_user_id` must come from the stashed state, not request auth). On success: upsert `GoogleCalendarConnection` (create if none, else update credentials/expiry/scope/revoked_at=None), 302 redirect to `{frontend_url}/settings/calendar?connected=1`. On any failure (bad state, token exchange failure): 302 redirect to `...?connected=0&error=<code>` — a redirect, not a JSON error, since this is a full-page browser navigation (matches how the existing `/google/callback` behaves — read it before implementing to match the exact redirect-building helper/pattern already in use).

- [ ] **Step 4.1: Write failing tests:**
  - `hc_headers` calling `/connect` gets an `auth_url` containing the calendar scope.
  - `client_headers` calling `/connect` is rejected (403/401 — Calendar connect is HC-only; confirm exact status code by checking how other HC-only routes in this file reject Client callers).
  - A valid state + mocked Google token exchange round-trips through `/callback` and creates a `GoogleCalendarConnection` row for the right `hc_user_id`, then redirects with `connected=1`.
  - An invalid/unknown `state` on `/callback` → 400 (or redirects with `connected=0` — match existing `/google/callback` error-handling convention exactly, don't invent a new one).
  - Calling `/callback` a second time for an already-connected HC updates the existing row (not a duplicate — `hc_user_id` is unique).

- [ ] **Step 4.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 5: `GET /api/calendar/status`

**Files:**
- Create: `backend/src/api/calendar.py` (new router, `prefix="/api/calendar"`, all routes require HC auth)
- Modify: wherever routers are registered (e.g. `backend/src/main.py` or `backend/src/api/__init__.py` — check existing router registration pattern for `sessions.py`'s router and mirror it)
- Test: `backend/tests/integration/test_calendar_api.py` (new)

**Interfaces:**
- `GET /api/calendar/status` → `{"connected": bool, "google_account_email": str | None, "connected_at": str | None, "needs_reauth": bool}`

- [ ] **Step 5.1: Write failing tests for three states:** no connection row → `connected: false`; a normal connected row → `connected: true` + email/connected_at populated; a row with `revoked_at` set → `connected: true, needs_reauth: true` (still "connected" in the sense that a grant was once made, but action is needed).

- [ ] **Step 5.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 6: `_get_valid_access_token` helper (refresh-on-expiry, revoke-on-failure, logging)

**Files:**
- Modify: `backend/src/api/calendar.py`
- Test: extend `test_calendar_api.py`

**Interfaces:**
```python
async def _get_valid_access_token(db: AsyncSession, hc_user_id: UUID) -> str:
    """Raises HTTPException(409, detail="calendar_not_connected") or (409, detail="calendar_reauth_required")."""
```

Logic: load the connection; if none or `revoked_at is not None` → 409 with the appropriate `detail` string (frontend branches on this exact string, so keep it stable). If `access_token_expires_at` is in the past (allow a small buffer, e.g. 60s), call `refresh_calendar_access_token`; on success, update `credentials`/`access_token_expires_at`/`updated_at`, commit, return the new token. On `CalendarReauthRequired`, set `revoked_at = now()`, commit, then raise the same 409 `calendar_reauth_required`. Every branch (success, refresh, failure) logs one `structlog` line: `logger.info("google_calendar_api_call", operation=..., hc_id=..., outcome=..., latency_ms=...)`.

- [ ] **Step 6.1: Write failing tests:** no connection → 409 `calendar_not_connected`; `revoked_at` set → 409 `calendar_reauth_required`; expired token triggers a (mocked) refresh call and updates the stored row, returns new token; a refresh that raises `CalendarReauthRequired` sets `revoked_at` on the row and raises 409; assert a log line is emitted for at least one path (check how existing tests in this repo assert on `structlog` output — e.g. `caplog` or a custom capture fixture — before inventing a new mechanism).

- [ ] **Step 6.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 7: `GET /api/calendar/events`

**Files:**
- Modify: `backend/src/api/calendar.py`
- Test: extend `test_calendar_api.py`

**Interfaces:**
- `GET /api/calendar/events?time_min=<iso8601>&time_max=<iso8601>` → `list[{"id": str, "summary": str, "start": str, "end": str, "hangout_link": str | None, "html_link": str, "location": str | None}]`. Proxies Google `GET https://www.googleapis.com/calendar/v3/calendars/primary/events?singleEvents=true&orderBy=startTime&timeMin=...&timeMax=...` via `_get_valid_access_token`'s bearer token.

- [ ] **Step 7.1: Write failing tests:** mocked Google response maps correctly to the flat shape (including an event with no `hangoutLink` → `hangout_link: null`, not a crash); no connection → 409 `calendar_not_connected` (propagated from Task 6's helper); confirm no DB row is written for the fetched events beyond whatever `_get_valid_access_token` itself may update (token refresh only).

- [ ] **Step 7.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 8: Frontend — `calendar.ts` API layer + `date-fns` dependency

**Files:**
- Modify: `frontend/package.json` (add `date-fns`)
- Create: `frontend/src/lib/api/calendar.ts`

**Interfaces:**
```typescript
export const CalendarStatusSchema = z.object({
  connected: z.boolean(),
  google_account_email: z.string().nullable(),
  connected_at: z.string().nullable(),
  needs_reauth: z.boolean(),
});

export const CalendarEventSchema = z.object({
  id: z.string(),
  summary: z.string(),
  start: z.string(),
  end: z.string(),
  hangout_link: z.string().nullable(),
  html_link: z.string(),
  location: z.string().nullable(),
});

export async function getCalendarStatus(): Promise<CalendarStatus>;
export async function getCalendarConnectUrl(): Promise<string>; // GET /api/auth/google/calendar/connect, returns auth_url
export async function listCalendarEvents(timeMin: string, timeMax: string): Promise<CalendarEvent[]>;
export async function createCalendarEvent(input: { summary: string; start: string; end: string; add_meet?: boolean }): Promise<CalendarEvent>;
```
Follow `sessions.ts`'s exact existing pattern: `fetchWithAuth`, `API_URL`, throw on non-ok response, `Schema.parse()` the JSON.

- [ ] **Step 8.1: Write a Vitest unit test** parsing a representative Google-shaped event payload through `CalendarEventSchema`, confirm it validates.
- [ ] **Step 8.2: Implement, run `npx tsc --noEmit` clean, commit.**

---

## Task 9: Frontend — `MonthGrid` component

**Files:**
- Create: `frontend/src/components/calendar/MonthGrid.tsx`

**Interfaces:**
```typescript
function MonthGrid({ month, events, onSelectEvent }: {
  month: Date; // any date within the month to display
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
}): JSX.Element
```
Static 6×7 grid of day cells (use `date-fns`'s `startOfMonth`/`endOfMonth`/`startOfWeek`/`eachDayOfInterval` to compute the 42 cells spanning the leading/trailing days of adjacent months), each cell lists that day's events by `summary` (truncated), clicking an event calls `onSelectEvent`. Match the app's existing Tailwind/token conventions (check `NotesTab`'s existing styling for border/background/heading classes to reuse, not invent new ones).

- [ ] **Step 9.1: Write an RTL test:** given a fixed month and a list of events (including one on the 1st, one on the last day, one not in this month), renders 42 day cells, the right day shows the right event title, clicking it calls `onSelectEvent` with that exact event object.
- [ ] **Step 9.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 10: Frontend — `WeekGrid` component

**Files:**
- Create: `frontend/src/components/calendar/WeekGrid.tsx`

**Interfaces:**
```typescript
function WeekGrid({ weekStart, events, onSelectEvent }: {
  weekStart: Date;
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
}): JSX.Element
```
7 day columns × 24 hourly rows, events positioned by pixel-per-minute using `differenceInMinutes` from a fixed day-start anchor; same-time overlapping events lay out side-by-side (simple equal-width split — not pixel-perfect stacking logic, that's explicitly out of scope per the plan's design rationale).

- [ ] **Step 10.1: Write an RTL test:** given a week range and 2-3 events at different/overlapping times, confirms each event renders in the correct day column at roughly the correct vertical position (test via computed `style.top`/`style.height` values or data attributes, not exact pixel snapshot), overlapping events both render (neither is dropped/hidden), clicking calls `onSelectEvent`.
- [ ] **Step 10.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 11: Frontend — `CalendarView` container

**Files:**
- Create: `frontend/src/components/calendar/CalendarView.tsx`

**Interfaces:**
```typescript
function CalendarView({ onSelectEvent }: { onSelectEvent: (event: CalendarEvent) => void }): JSX.Element
```
On mount, calls `getCalendarStatus()`. Renders one of four states:
1. `!connected` → "Connect Google Calendar" button → `window.location.href = await getCalendarConnectUrl()`.
2. `needs_reauth` → "Reconnect Google Calendar" button, same action, plus a short explanatory line (e.g. "Your Google Calendar connection needs to be renewed.").
3. `connected && !needs_reauth`, no events loaded yet → loading state, then month/week toggle + `MonthGrid`/`WeekGrid` fed from `listCalendarEvents` for the visible range, plus a "+ Create event" button opening `CreateEventForm` (Task 13).
4. Error fetching events (e.g. a 409 that slipped through, or a network error) → inline error message, not a crash.

- [ ] **Step 11.1: Write RTL tests for all four states** (mock `getCalendarStatus`/`listCalendarEvents` per state), asserting the right CTA/grid/message renders for each.
- [ ] **Step 11.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 12: `POST /api/calendar/events` (create event)

**Files:**
- Modify: `backend/src/api/calendar.py`
- Test: extend `test_calendar_api.py`

**Interfaces:**
- `POST /api/calendar/events` `{"summary": str, "start": datetime, "end": datetime, "add_meet": bool = true}` → same shape as one `GET /events` list item. Proxies Google `POST .../calendars/primary/events?conferenceDataVersion=1` (only when `add_meet=true`) with `conferenceData: {"createRequest": {"requestId": <uuid4>}}` in the body when Meet is requested.

- [ ] **Step 12.1: Write failing tests:** mocked `events.insert` response with `hangoutLink` present → endpoint returns it correctly; `add_meet=false` → assert the outgoing mocked request body does NOT contain `conferenceData`/`conferenceDataVersion` query param (inspect the mocked request, not just the response); no connection → 409.
- [ ] **Step 12.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 13: Frontend — `CreateEventForm` component

**Files:**
- Create: `frontend/src/components/calendar/CreateEventForm.tsx`

**Interfaces:**
```typescript
function CreateEventForm({ onCreated, onCancel }: {
  onCreated: (event: CalendarEvent) => void;
  onCancel: () => void;
}): JSX.Element
```
Title input, start/end datetime inputs, "Add Google Meet" checkbox (default checked). On submit, calls `createCalendarEvent`; on success calls `onCreated(event)`; on failure, inline error message (matches this app's existing form-error convention — check `NotesTab`'s `linkError` pattern from PHASE-01d and reuse the same visual treatment).

- [ ] **Step 13.1: Write an RTL test:** filling the form and submitting calls `createCalendarEvent` with the exact expected payload; on success `onCreated` is called with the returned event; on a mocked API failure, an inline error renders and `onCreated` is NOT called.
- [ ] **Step 13.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 14: `sessions.google_calendar_event_id` column + migration + `SessionOut`

**Files:**
- Modify: `backend/src/db/models/sessions.py`
- Modify: `backend/src/api/sessions.py` (`SessionOut` only — NOT `SessionCreate`/`SessionPatch`, this field is never set through those)
- Create: Alembic migration
- Test: `backend/tests/integration/test_sessions.py` (add to existing file)

**Interfaces:**
- `Session.google_calendar_event_id: Mapped[str | None] = mapped_column(Text)` — add right after `meeting_url`.
- `SessionOut.google_calendar_event_id: str | None` — read-only exposure.

- [ ] **Step 14.1: Write a failing integration test:** direct ORM write + read round-trips the field (no endpoint sets it yet — that's Task 15).
- [ ] **Step 14.2: Confirm failure, add the column + migration (mirror PHASE-01d Task 1's migration exactly — plain `sa.Text()`, no dialect import needed), add to `SessionOut`, confirm pass, commit.**

---

## Task 15: `POST /api/sessions/{id}/calendar-link`

**Files:**
- Modify: `backend/src/api/sessions.py`
- Test: `backend/tests/integration/test_sessions.py` or a new `test_calendar_link.py` (either is fine — match whichever keeps `test_sessions.py` from growing unwieldy; use judgment)

**Interfaces:**
```python
class CalendarLinkRequest(BaseModel):
    google_event_id: str | None  # non-null = link this event; null = unlink

@router.post("/{session_id}/calendar-link")
async def link_calendar_event(session_id: UUID, body: CalendarLinkRequest, ...) -> SessionOut: ...
```
Logic: load the session via the existing ownership-check helper (`_get_owned_session` or equivalent — check `sessions.py`'s existing `get_session`/`patch_session` for the exact helper name and reuse it, don't duplicate the ownership query). If `body.google_event_id is None` → clear `google_calendar_event_id`, leave `meeting_url` untouched, save, return. Else → **re-fetch the event server-side** (call the same Google-events-get logic Task 7 uses, scoped to a single event by id — add a small internal helper, don't re-fetch the whole list) using the calling HC's own token; if the fetched event has no `hangout_link`, raise `HTTPException(422, detail="Selected event has no Google Meet link. Add one in Calendar, or create a new event with Meet enabled.")` and do not modify the session; else set `google_calendar_event_id = event.id` and `meeting_url = event.hangout_link`, save, return.

- [ ] **Step 15.1: Write failing tests:**
  - Linking a (mocked) event with a `hangout_link` sets both fields on the session, returns the updated `SessionOut`.
  - Linking a (mocked) event with no `hangout_link` → 422 with the exact message above, session unchanged (assert via a follow-up GET).
  - `{"google_event_id": null}` clears `google_calendar_event_id`, leaves `meeting_url` at whatever it was.
  - A session belonging to another HC → 404 (matches this file's existing cross-tenant test pattern, e.g. `test_get_session_cross_tenant_returns_404`).
- [ ] **Step 15.2: Confirm failure, implement, confirm pass, commit.**

---

## Task 16: Wire `CalendarView` into `NotesTab`'s meeting-link block

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` (`NotesTab`)
- Modify: `frontend/src/lib/api/sessions.ts` (`SessionOutSchema` +`google_calendar_event_id`, + `linkCalendarEvent(sessionId, googleEventId: string | null)`)

**Interfaces:**
- The existing "+ Add meeting link" / "Edit link" block (from PHASE-01d) gains a new option: **"Choose from Google Calendar →"**, opening `CalendarView` (Task 11) in a modal or inline panel (match this app's existing modal/panel convention — check if one already exists elsewhere in the codebase, e.g. the diet-chart send confirm dialog from PHASE-01c, rather than introducing a new pattern). Selecting an event in `CalendarView`, or creating one via `CreateEventForm`, calls `linkCalendarEvent(session.id, event.id)`, then `onSessionChange(updated)` (existing prop, from PHASE-01d Task 3). If `session.google_calendar_event_id` is set, show a small "via Google Calendar" badge next to the existing "Join call →" button, with an "Unlink" action calling `linkCalendarEvent(session.id, null)`.

- [ ] **Step 16.1: Update `SessionOutSchema` + add `linkCalendarEvent` to `sessions.ts`. Run `npx tsc --noEmit`.**
- [ ] **Step 16.2: Wire the UI per Interfaces above.**
- [ ] **Step 16.3: Manual verification checklist** (mirrors PHASE-01d Step 3.3's style — requires the Non-code prerequisite in this Unit's SPEC decision to be done first, i.e. a real Google test-user account connected):
  1. Open a session with no meeting link, click "Choose from Google Calendar →" — see the "Connect Google Calendar" CTA (not yet connected).
  2. Connect — redirected to Google, back to Tapas, `connected: true`.
  3. Reopen the picker — see the calendar grid with real events.
  4. Pick an event that has a Meet link — session now shows "Join call →" + "via Google Calendar" badge.
  5. Pick an event with no Meet link — inline 422 error, nothing changes.
  6. Create a new event with "Add Google Meet" checked — same linked result as picking one.
  7. Click Unlink — badge disappears, `meeting_url` remains as a normal editable free-text field (still holds the last-derived link, editable/clearable like any manual entry).
  8. Simulate an expired/revoked token (e.g. manually set `revoked_at` on the DB row) — picker shows "Reconnect Google Calendar," not a silent error or crash.
- [ ] **Step 16.4: `npx tsc --noEmit` clean; full backend suite green, no regressions (same gate as PHASE-01d Step 1.8/3.2). Commit.**

---

## Self-review

**Spec coverage check** (against this Unit's SPEC-0001, new F6-Calendar-extension decision — to be added alongside D-28 before/during Task 1):

| Requirement | Covered by |
|---|---|
| Full month/week calendar view (not a narrow date-scoped picker) | Tasks 9, 10, 11 |
| Pick an existing event, pulling its Meet/Zoom link | Tasks 7, 15 |
| Create a new event with a Google Meet link | Tasks 12, 13 |
| Link a specific event to a specific session | Task 15 |
| HC-only, no client-facing routes | No client route touched anywhere in this plan |
| Least-privilege OAuth scope, incremental consent, login flow untouched | Tasks 3, 4 |
| No calendar event content persisted beyond the linked event's id/link | Tasks 7, 12, 15 (explicit non-persistence, called out per task) |
| Encrypted token storage, separate key from `demographics` | Tasks 1, 2 |
| Reauth handled explicitly, not a silent failure | Tasks 5, 6, 11 |

**Deferred, deliberately**: client-facing calendar/meeting-link UI (blocked on OQ-7); ongoing sync between a linked event and `meeting_url` after link time (accepted drift, not solved here); Google OAuth app verification / moving off "Testing" publishing status (external, non-code, tracked as a known limitation — see SPEC decision); no row lock/dedup on `_get_valid_access_token`'s refresh path (Task 6 review) — two concurrent requests for the same HC can both trigger a Google token refresh; each caller still gets a valid token, so this is a duplicate network call, not an incorrect result. Documented in a code comment on `_get_valid_access_token` (`backend/src/api/calendar.py`); revisit only if real-world concurrency at this chokepoint becomes a cost/quota concern.

**Placeholder scan**: Tasks 3–4, 6–7, 9–13, 15–16 describe interfaces/behavior precisely but leave literal implementation code to the TDD-following implementer subagent (appropriate for this phase's size and novelty — not a placeholder, a deliberate level of specification, per subagent-driven-development's own model-tier guidance).

**Type consistency check**: `google_calendar_event_id: str | None` (Python) / `string | null` (Zod) — verify consistent across `Session`, `SessionOut`, and the frontend schema at Task 16.
