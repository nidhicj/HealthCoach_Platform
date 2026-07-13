/**
 * PHASE-01f Task 4 — visible feedback while linking a calendar event.
 *
 * Separate from NotesTab.test.tsx (which mocks CalendarView entirely) and
 * mirrors NotesTab.calendarConnect.test.tsx's convention of rendering the
 * REAL CalendarView (only its own API module mocked), because the bug this
 * covers only manifests through the real grid: clicking an event showed no
 * visible state at all while the link request was in flight, and nothing
 * guarded against clicking a second event before the first resolved.
 */
import { useState } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotesTab } from "@/app/(app)/clients/[clientId]/sessions/[sessionId]/page";
import { linkCalendarEvent, patchSession } from "@/lib/api/sessions";
import type { SessionOut } from "@/lib/api/sessions";
import { getCalendarStatus, getCalendarConnectUrl, listCalendarEvents } from "@/lib/api/calendar";
import type { CalendarEvent, CalendarStatus } from "@/lib/api/calendar";

vi.mock("@/lib/api/sessions", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/sessions")>();
  return {
    ...actual,
    patchSession: vi.fn(),
    linkCalendarEvent: vi.fn(),
  };
});

vi.mock("@/lib/api/files", () => ({
  uploadFiles: vi.fn(),
  deleteFile: vi.fn(),
}));

vi.mock("@/lib/api/calendar", () => ({
  getCalendarStatus: vi.fn(),
  getCalendarConnectUrl: vi.fn(),
  listCalendarEvents: vi.fn(),
}));

function makeSession(overrides: Partial<SessionOut> = {}): SessionOut {
  return {
    id: "sess-1",
    hc_user_id: "hc-1",
    client_id: "cli-1",
    session_number: 1,
    scheduled_at: "2026-07-14T09:00:00+05:30",
    started_at: null,
    ended_at: null,
    zoom_meeting_id: null,
    meeting_url: null,
    google_calendar_event_id: null,
    google_calendar_event_title: null,
    notes_internal: null,
    session_notes: null,
    created_at: "2026-07-01T00:00:00Z",
    ...overrides,
  };
}

function makeStatus(overrides: Partial<CalendarStatus> = {}): CalendarStatus {
  return {
    connected: true,
    google_account_email: "coach@example.com",
    connected_at: "2026-07-01T00:00:00Z",
    needs_reauth: false,
    ...overrides,
  };
}

function todayAt(hour: number): string {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

function makeEvent(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    id: "id",
    summary: "summary",
    start: todayAt(9),
    end: todayAt(10),
    hangout_link: null,
    html_link: "https://calendar.google.com/event?eid=x",
    location: null,
    ...overrides,
  };
}

// A promise we can resolve/reject on our own schedule, to observe the
// in-flight UI state before settling the request.
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

// Mirrors SessionPage's real ownership of `session` state: NotesTab is a
// controlled component that only re-renders with a linked event's fields
// (e.g. for the "Unlink" button to appear) once its `session` prop actually
// changes. A bare `vi.fn()` for onSessionChange — fine for tests that only
// assert it was *called* — can never produce that re-render, so tests that
// need to observe the post-link UI use this small stateful harness instead,
// matching how the real parent (SessionPage) behaves.
function Harness() {
  const [session, setSession] = useState(makeSession());
  return (
    <NotesTab
      session={session}
      files={[]}
      filesLoading={false}
      onFilesChange={vi.fn()}
      onSessionChange={setSession}
      onNext={vi.fn()}
    />
  );
}

async function openPickerWithTwoEvents() {
  const user = userEvent.setup();
  vi.mocked(getCalendarStatus).mockResolvedValue(makeStatus());
  const targetEvent = makeEvent({ id: "e-target", summary: "Client check-in" });
  const otherEvent = makeEvent({ id: "e-other", summary: "1:1 sync", start: todayAt(11), end: todayAt(12) });
  vi.mocked(listCalendarEvents).mockResolvedValue([targetEvent, otherEvent]);

  render(<Harness />);

  await user.click(screen.getByRole("button", { name: "Choose from Google Calendar →" }));
  const targetButton = await screen.findByRole("button", { name: "Client check-in" });
  const otherButton = await screen.findByRole("button", { name: "1:1 sync" });

  return { user, targetButton, otherButton, targetEvent, otherEvent };
}

describe("NotesTab — visible feedback while linking a calendar event (PHASE-01f Task 4)", () => {
  beforeEach(() => {
    vi.mocked(linkCalendarEvent).mockReset();
    vi.mocked(patchSession).mockReset();
    vi.mocked(getCalendarStatus).mockReset();
    vi.mocked(getCalendarConnectUrl).mockReset();
    vi.mocked(listCalendarEvents).mockReset();
  });

  it("shows a visibly busy state on the clicked event, disables other events, and disables Close while the request is in flight", async () => {
    const { promise, resolve } = deferred<SessionOut>();
    vi.mocked(linkCalendarEvent).mockReturnValue(promise);
    const { user, targetButton, otherButton } = await openPickerWithTwoEvents();

    await user.click(targetButton);

    // The clicked event is visibly busy; the other event is disabled but
    // still visible (not hidden), guarding against a second click racing
    // the first in-flight request.
    expect(targetButton).toHaveAttribute("aria-busy", "true");
    expect(targetButton).toBeDisabled();
    expect(otherButton).toBeInTheDocument();
    expect(otherButton).not.toHaveAttribute("aria-busy", "true");
    expect(otherButton).toBeDisabled();
    expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();

    // Settle the in-flight request so no state update leaks past the test.
    resolve(makeSession({ google_calendar_event_id: "e-target" }));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Client check-in" })).not.toBeInTheDocument(),
    );
  });

  it("a second click on another event while the first is in flight does not trigger a second link request", async () => {
    const { promise } = deferred<SessionOut>();
    vi.mocked(linkCalendarEvent).mockReturnValue(promise);
    const { user, targetButton, otherButton } = await openPickerWithTwoEvents();

    await user.click(targetButton);
    expect(linkCalendarEvent).toHaveBeenCalledTimes(1);

    // otherButton is disabled while targetButton's request is in flight —
    // clicking it must not fire a second linkCalendarEvent call.
    await user.click(otherButton);
    expect(linkCalendarEvent).toHaveBeenCalledTimes(1);
    expect(linkCalendarEvent).toHaveBeenCalledWith("sess-1", "e-target");
  });

  it("clears the busy state and re-enables events once the request resolves successfully (picker closes)", async () => {
    const updated = makeSession({ google_calendar_event_id: "e-target", meeting_url: "https://meet.google.com/x" });
    vi.mocked(linkCalendarEvent).mockResolvedValue(updated);
    const { user, targetButton } = await openPickerWithTwoEvents();

    await user.click(targetButton);
    await screen.findByRole("button", { name: "Unlink" }); // linked-state UI confirms flow completed

    // Picker (and its events) are gone entirely on success.
    expect(screen.queryByRole("button", { name: "Client check-in" })).not.toBeInTheDocument();
  });

  it("clears the busy state and re-enables events once the request fails, so the coach can retry", async () => {
    vi.mocked(linkCalendarEvent).mockRejectedValue(new Error("Link calendar event failed: 422"));
    const { user, targetButton, otherButton } = await openPickerWithTwoEvents();

    await user.click(targetButton);

    expect(await screen.findByText("Link calendar event failed: 422")).toBeInTheDocument();

    // Busy/disabled state clears on failure too — both events are
    // interactive again so the coach can retry.
    expect(targetButton).not.toHaveAttribute("aria-busy", "true");
    expect(targetButton).not.toBeDisabled();
    expect(otherButton).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Close" })).not.toBeDisabled();
  });
});
