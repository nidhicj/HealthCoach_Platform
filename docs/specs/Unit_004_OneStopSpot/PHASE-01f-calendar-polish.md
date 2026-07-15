# PHASE-01f — Calendar Integration Polish (F6 extension, round 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan builds directly on PHASE-01e (Google Calendar integration, shipped and merged into this branch's history) — read `PHASE-01e-calendar-integration.md` if you need that phase's full context, but do not re-implement anything from it.

**Goal:** Fix five real gaps found during SoJo's own manual testing of PHASE-01e against a live Google account (screenshots + screen recordings, 2026-07-13):
1. No visible feedback while linking a calendar event (picker silently closes with zero indication anything happened).
2. `CreateEventForm`'s title field starts blank; it should default to a sensible, still-editable value.
3. The linked event's title isn't shown anywhere durable — "Join call →" gives no indication of *which* meeting you're about to join.
4. The calendar picker's month/week view is locked to "today" — no way to navigate to a different month/week.
5. The meeting-link block's typography is low-contrast/too-small for the secondary actions (Edit link / Choose from Google Calendar).

A sixth reported symptom — "Join call" leads to a Google Meet room that loops between "Getting ready…" and the join lobby without ever entering the call — was diagnosed as **not a code issue**: it reproduces identically when opening the same `meet.google.com` URL directly, bypassing this app entirely, and persists after a 30-minute wait (ruling out Meet-room provisioning lag). It is out of scope for this plan.

**Architecture:** Mostly additive. One new persisted field (the linked event's title, alongside the existing `id`/`hangoutLink` — SoJo explicitly approved this as a small, deliberate relaxation of PHASE-01e's "id + hangoutLink only" DPDP-minimization rule, since a meeting title isn't sensitive data). Everything else is UI-only: threading two already-available values (session number, client first name) one level deeper, adding visible loading/selected state to existing components, and adding prev/next navigation to `CalendarView`'s existing `anchor` state (which already exists but currently has no setter exposed).

**Tech stack:** Same as PHASE-01e — FastAPI/SQLAlchemy backend, Next.js/TypeScript frontend, Alembic migrations. No new dependencies.

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Tests hit a real PostgreSQL DB (`tapas_test`) — no mocking the DB. Mock Google's HTTP responses only.
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before running backend commands.
- The new persisted title field follows the exact same migration/model/schema conventions as `google_calendar_event_id` (PHASE-01e Task 14) — plain `sa.Text()`, no dialect import needed.
- No other calendar event content (attendees, description, location) gets persisted — this plan adds exactly one new field (title), nothing more.
- Match this app's existing design system (Tailwind + custom tokens) — no new UI library, no invented styling patterns. Reuse `MonthGrid.tsx`'s/`WeekGrid.tsx`'s/`CalendarPickerDialog`'s established conventions.
- Frontend: `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` is the same file PHASE-01d and PHASE-01e Task 16 already modified — read the current `NotesTab`/`CalendarPickerDialog` code first (don't assume PHASE-01e's shape from memory; verify against the live file).

---

## Task 1: Persist the linked event's title

**Files:**
- Modify: `backend/src/db/models/sessions.py` (`Session` class)
- Modify: `backend/src/api/sessions.py` (`SessionOut`, `link_calendar_event`)
- Create: an Alembic migration
- Test: `backend/tests/integration/test_calendar_link.py` (existing file from PHASE-01e Task 15)

**Interfaces:**
- Produces: `Session.google_calendar_event_title: Mapped[str | None] = mapped_column(Text)` — add right after `google_calendar_event_id`.
- Produces: `SessionOut.google_calendar_event_title: str | None` — read-only, same pattern as `google_calendar_event_id`.

---

- [ ] **Step 1.1: Write the failing tests**

Add to `backend/tests/integration/test_calendar_link.py`:
- Linking a mocked event with `summary="Weekly check-in"` and a `hangout_link` sets `google_calendar_event_title == "Weekly check-in"` on the returned `SessionOut`, alongside the existing `google_calendar_event_id`/`meeting_url` assertions.
- `{"google_event_id": null}` (unlink) clears `google_calendar_event_title` to `None`, same as it already clears `google_calendar_event_id`.

Read the existing tests in this file first (`test_link_calendar_event_with_meet_link_sets_session_fields`, `test_unlink_calendar_event_clears_event_id_leaves_meeting_url`) and extend them in place rather than duplicating — add the new field's assertion alongside the existing ones in the same test bodies where it's natural, and update the unlink test's name/assertions to also cover the title.

- [ ] **Step 1.2: Confirm failure**

- [ ] **Step 1.3: Add the column to the model**

```python
    google_calendar_event_title: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 1.4: Update `SessionOut` and `link_calendar_event`**

`SessionOut` gains `google_calendar_event_title: str | None`, placed right after `google_calendar_event_id`.

In `link_calendar_event` (`backend/src/api/sessions.py`), find where `sess.google_calendar_event_id = event.id` and `sess.meeting_url = event.hangout_link` are set on the link path — add `sess.google_calendar_event_title = event.summary` alongside them. Find where the unlink path (`body.google_event_id is None`) clears `sess.google_calendar_event_id = None` — add `sess.google_calendar_event_title = None` alongside it.

- [ ] **Step 1.5: Generate + fill in the migration** (mirror PHASE-01e Task 14's `google_calendar_event_id` migration exactly — plain `sa.Text()`, `down_revision` set to whatever `alembic heads` currently reports)

```python
def upgrade() -> None:
    op.add_column("sessions", sa.Column("google_calendar_event_title", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("sessions", "google_calendar_event_title")
```

- [ ] **Step 1.6: Apply migration, run tests, confirm pass, run full backend suite for regressions, commit.**

---

## Task 2: Display "Join the call — `<title>`"

**Files:**
- Modify: `frontend/src/lib/api/sessions.ts` (`SessionOutSchema`)
- Modify: `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` (`NotesTab`)

**Interfaces:**
- Consumes: Task 1's `SessionOut.google_calendar_event_title`.

---

- [ ] **Step 2.1: Add `google_calendar_event_title: z.string().nullable()` to `SessionOutSchema`.**

- [ ] **Step 2.2: Update the "Join call" button text.**

Currently (verify exact current line against the live file — do not assume line numbers from this plan):
```tsx
<a href={session.meeting_url} target="_blank" rel="noopener noreferrer" className="...">
  Join call →
</a>
```

Change the button text to `Join the call — {session.google_calendar_event_title}` when that field is set, falling back to the current plain `Join call →` when it's null (manually-entered links, or links from before this field existed, have no title). Keep the same styling/classes — this is a text-content change only, not a redesign of this element (redesign is Task 6's job).

- [ ] **Step 2.3: `npx tsc --noEmit` clean, run the affected RTL tests (or add one if this component/behavior doesn't have coverage yet — check `NotesTab.test.tsx` from PHASE-01e Task 16 for the existing convention), commit.**

---

## Task 3: Month/week navigation in the calendar picker

**Files:**
- Modify: `frontend/src/components/calendar/CalendarView.tsx`
- Test: `frontend/tests/unit/CalendarView.test.tsx` (existing file from PHASE-01e Task 11)

**Interfaces:**
- No external prop-interface change — `CalendarView`'s own `{ onSelectEvent }` signature is unchanged. This is entirely internal state/UI.

---

- [ ] **Step 3.1: Add navigation state and controls.**

`CalendarView.tsx` currently has `const [anchor] = useState(() => new Date());` — no setter. Change to `const [anchor, setAnchor] = useState(() => new Date());`.

Add `addMonths`, `subMonths`, `addWeeks`, `subWeeks` to the existing `date-fns` import.

Add prev/next handlers:
```typescript
function goToPrevious() {
  setAnchor((a) => (viewMode === "month" ? subMonths(a, 1) : subWeeks(a, 1)));
}
function goToNext() {
  setAnchor((a) => (viewMode === "month" ? addMonths(a, 1) : addWeeks(a, 1)));
}
```

Add prev/next buttons and a label (e.g. `format(anchor, "MMMM yyyy")` for month view, an appropriate week-range label for week view — use `date-fns`'s `format`) in the header row, next to the existing Month/Week `Tabs`. Match the existing header row's layout (`flex items-center justify-between`) — this row already holds the view-mode tabs and the "+ Create event" button; fit the navigation controls in without breaking that layout on smaller viewports if this app has any responsive breakpoints already in use elsewhere in this file (check before assuming none are needed).

The existing `useEffect` that fetches events already depends on `[status, viewMode, anchor]` — no changes needed there, it will naturally refetch when `anchor` changes via navigation.

- [ ] **Step 3.2: Write/extend RTL tests** covering: clicking "next" in month view advances `anchor` by one month (assert the visible label changes, and that `listCalendarEvents` gets called with a new date range — mock and assert call args); clicking "previous" goes back; switching between month/week view while navigated away from the current month keeps you on the same `anchor` (doesn't reset to today).

- [ ] **Step 3.3: `npx tsc --noEmit` clean, run tests, commit.**

---

## Task 4: Visible feedback while linking an event

**Files:**
- Modify: `frontend/src/components/calendar/MonthGrid.tsx`, `WeekGrid.tsx` (accept a "which event is currently linking" indicator)
- Modify: `frontend/src/components/calendar/CalendarView.tsx` (thread the linking state through)
- Modify: `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` (`CalendarPickerDialog` already receives `linking: boolean` from `NotesTab` — currently only disables the Close button; extend its use)

**Interfaces:**
- `MonthGrid`/`WeekGrid` gain an optional prop, e.g. `linkingEventId: string | null`, to visually distinguish the specific event currently being linked (not just a generic global-loading state) — read both files' current prop interfaces first and add this consistently to both, matching their existing conventions (both already take `events`/`onSelectEvent`).

---

- [ ] **Step 4.1: Design and write the failing tests first**, covering: clicking an event sets that specific event into a visibly "linking" state (spinner, dimmed, disabled — pick one, consistent with this app's existing loading-state conventions elsewhere, e.g. `Skeleton` usage or button `disabled`+text-swap patterns already in this codebase); other events in the grid are not affected/disabled while one is linking (per the brief's earlier review: currently ALL grid interaction stays live during a link request — that's the gap being fixed here, not just adding a global overlay).

- [ ] **Step 4.2: Implement.**

`CalendarView` needs to track *which* event was clicked (not just a boolean) so it can pass that specific event's id down to `MonthGrid`/`WeekGrid` as `linkingEventId`. `CalendarView` currently calls `onSelectEvent(event)` directly and has no local "linking" state of its own — the actual `linkingCalendarEvent` boolean lives up in `NotesTab`, one level above `CalendarPickerDialog`. Decide the cleanest way to get the clicked event's id down to the grids: either (a) `CalendarView` wraps `onSelectEvent` locally to track the clicked event's id in its own state before calling the parent's `onSelectEvent`, clearing it in a `finally` once the parent's promise-based flow completes — but `CalendarView`'s `onSelectEvent` prop is currently `(event: CalendarEvent) => void`, not async/awaitable, so this needs either changing that prop's signature to return a Promise the caller can await, or (b) have `NotesTab`/`CalendarPickerDialog` pass the currently-linking event's id down as a new prop through `CalendarPickerDialog` → `CalendarView` → `MonthGrid`/`WeekGrid`, alongside the existing `linking: boolean`. Prefer whichever requires touching fewer existing signatures — read all four files' current prop shapes before deciding, and if genuinely ambiguous, ask rather than guess (this is exactly the kind of judgment call that's cheap to get a second opinion on before writing code across four files).

Once the clicked event is visually identifiable, ensure other (non-clicked) events remain clickable-looking but functionally should probably also be disabled while a link request is in flight (clicking a second event before the first one resolves is a real race — decide and implement a reasonable guard, e.g. ignore clicks on any event while `linking` is true).

- [ ] **Step 4.3: `npx tsc --noEmit` clean, run tests, commit.**

---

## Task 5: Pre-fill `CreateEventForm`'s title

**Files:**
- Modify: `frontend/src/components/calendar/CreateEventForm.tsx`
- Modify: `frontend/src/components/calendar/CalendarView.tsx` (thread a new prop through to `CreateEventForm`)
- Modify: `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` (`NotesTab` needs `session.session_number` — already has it via its existing `session` prop — and the client's first name, which it currently does NOT receive; `SessionPage`'s parent scope already has `client.full_name` loaded, per `client?.full_name` used elsewhere in this same file)

**Interfaces:**
- `NotesTab` gains a new required prop, e.g. `clientFirstName: string` (derive from `client.full_name.split(" ")[0]` at the call site in `SessionPage`, matching the exact pattern this file already uses elsewhere for `SendDialog`'s `clientName.split(" ")[0]` greeting — verify and reuse, don't reinvent).
- `CalendarPickerDialog` gains the same, passed through to `CalendarView`.
- `CalendarView` gains the same, passed through to `CreateEventForm`.
- `CreateEventForm`'s `title` state initializes to `` `Session-${sessionNumber} with ${clientFirstName}` `` instead of `""`, via a new prop (e.g. `defaultTitle: string`, computed by the caller, OR pass `sessionNumber`/`clientFirstName` separately and compute inside — pick whichever keeps `CreateEventForm` simpler; it currently has no knowledge of sessions/clients at all, so introducing the narrowest new prop that doesn't otherwise couple it to session/client concepts is preferable). The field remains a normal editable text input — this is only about its *initial* value.

---

- [ ] **Step 5.1: Write the failing test first** — `CreateEventForm` rendered with the new default-title prop shows that value pre-filled in the title input on mount, and it remains editable (typing over it works, and the edited value — not the default — is what gets submitted).

- [ ] **Step 5.2: Implement the prop-threading** through all four files listed above. Verify each file's *current* prop interface directly before editing (don't assume the shapes described in PHASE-01e's plan are still exactly accurate — that plan predates today's fixes to some of these same files within this same PHASE-01f).

- [ ] **Step 5.3: `npx tsc --noEmit` clean, run tests, commit.**

---

## Task 6: Meeting-link block visual polish

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` (`NotesTab`'s meeting-link block — the `session.meeting_url ? (...) : (...)` JSX)

**Interfaces:** none — styling only, no behavior change.

---

This task is a design/judgment call, not a mechanical spec — implement it, then flag it explicitly for SoJo's visual review (screenshot or live check) rather than treating "done" as self-evident, since "more user-friendly" and "text too small" are subjective calls this plan can't fully specify in advance.

- [ ] **Step 6.1: Increase the size/weight of the "Edit link" / "Choose from Google Calendar →" row** — currently `font-sans text-xs text-muted-foreground` (12px). Bump to at least `text-sm` (14px) and consider whether `text-muted-foreground` (a deliberately de-emphasized color, appropriate for genuinely secondary actions) is still right here or whether these two actions deserve more visual weight given how central "linking a calendar event" now is to this feature — your call, but be able to explain the reasoning in the self-review.

- [ ] **Step 6.2: Address the general "not user-friendly" feedback** on the block as a whole — look at spacing, button hierarchy (is "Join call"/"Join the call — `<title>`" visually the clear primary action against the secondary Edit/Choose/Unlink actions?), and whether the "via Google Calendar" badge + Unlink placement reads clearly. Do not do a full redesign — this is a polish pass on an already-shipped, already-functional block, not a rebuild.

- [ ] **Step 6.3: `npx tsc --noEmit` clean (styling-only change, should be a no-op here, but verify), commit.** No new automated test is expected for pure visual polish — note in the self-review that this task's verification is visual/manual, not test-covered, and say so plainly rather than inventing a test that doesn't actually verify anything meaningful (e.g. a snapshot test of Tailwind class names would be exactly this kind of hollow coverage — don't write one).

---

## Self-review

**Spec coverage check** (against SoJo's 2026-07-13 feedback):

| Requirement | Covered by |
|---|---|
| Visible feedback while linking | Task 4 |
| Pre-filled, editable Create Event title | Task 5 |
| Durable "Join the call — `<title>`" display | Tasks 1, 2 |
| Month/week navigation in the picker | Task 3 |
| Meeting-link block readability | Task 6 |
| "Join call" Meet-loop diagnosis | Diagnosed as environment/Google-side, not a code fix — explicitly out of scope, see Goal section |

**Deferred, deliberately**: none new — this phase closes out everything raised in the 2026-07-13 feedback except the Meet-loop item, which has no code-side fix available given the evidence gathered.

**Placeholder scan**: Task 4 intentionally leaves one design decision open (how exactly `CalendarView` learns which specific event is linking) rather than prescribing untested code across four files — flagged explicitly as a judgment call for the implementer, not a placeholder.

**Type consistency check**: `google_calendar_event_title: str | None` (Python) / `string | null` (Zod) — verify consistent across `Session`, `SessionOut`, and the frontend schema by the end of Task 2.
