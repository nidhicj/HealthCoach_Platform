/**
 * PHASE-01e Task 16 — wiring CalendarView into NotesTab's meeting-link block.
 * CalendarView itself is mocked (its own behavior is covered by
 * tests/unit/CalendarView.test.tsx); these tests only assert the wiring:
 * opening the picker, linking on selection, and the linked-state badge/Unlink.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotesTab } from "@/app/(app)/clients/[clientId]/sessions/[sessionId]/page";
import { linkCalendarEvent, patchSession } from "@/lib/api/sessions";
import type { SessionOut } from "@/lib/api/sessions";

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

// Mock CalendarView entirely — a fake picker exposing a single "Mock select
// event" button that invokes the onSelectEvent prop with a fixed fixture.
// This isolates the wiring test from CalendarView's own internals/fetches.
vi.mock("@/components/calendar/CalendarView", () => ({
  CalendarView: ({ onSelectEvent }: { onSelectEvent: (event: { id: string; summary: string; start: string; end: string; hangout_link: string | null; html_link: string; location: string | null }) => void }) => (
    <button
      onClick={() =>
        onSelectEvent({
          id: "evt-1",
          summary: "Coaching session",
          start: "2026-07-14T09:00:00+05:30",
          end: "2026-07-14T09:45:00+05:30",
          hangout_link: "https://meet.google.com/abc-defg-hij",
          html_link: "https://calendar.google.com/event?eid=x",
          location: null,
        })
      }
    >
      Mock select event
    </button>
  ),
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
    notes_internal: null,
    session_notes: null,
    created_at: "2026-07-01T00:00:00Z",
    ...overrides,
  };
}

function renderNotesTab(session: SessionOut, onSessionChange = vi.fn()) {
  return render(
    <NotesTab
      session={session}
      files={[]}
      filesLoading={false}
      onFilesChange={vi.fn()}
      onSessionChange={onSessionChange}
      onNext={vi.fn()}
    />,
  );
}

describe("NotesTab — Google Calendar linking (PHASE-01e Task 16)", () => {
  beforeEach(() => {
    vi.mocked(linkCalendarEvent).mockReset();
    vi.mocked(patchSession).mockReset();
  });

  it("shows a 'Choose from Google Calendar' option when there is no meeting link, and opens the picker", async () => {
    const user = userEvent.setup();
    renderNotesTab(makeSession());

    const openButton = screen.getByRole("button", { name: "Choose from Google Calendar →" });
    await user.click(openButton);

    expect(screen.getByRole("button", { name: "Mock select event" })).toBeInTheDocument();
  });

  it("shows a 'Choose from Google Calendar' option next to Edit link when a manual link already exists", () => {
    renderNotesTab(makeSession({ meeting_url: "https://zoom.us/j/123" }));

    expect(screen.getByRole("button", { name: "Choose from Google Calendar →" })).toBeInTheDocument();
    expect(screen.getByText("Edit link")).toBeInTheDocument();
  });

  it("selecting an event in the picker calls linkCalendarEvent(session.id, event.id), then onSessionChange, and closes the picker", async () => {
    const user = userEvent.setup();
    const updated = makeSession({
      google_calendar_event_id: "evt-1",
      meeting_url: "https://meet.google.com/abc-defg-hij",
    });
    vi.mocked(linkCalendarEvent).mockResolvedValue(updated);
    const onSessionChange = vi.fn();

    renderNotesTab(makeSession(), onSessionChange);

    await user.click(screen.getByRole("button", { name: "Choose from Google Calendar →" }));
    await user.click(screen.getByRole("button", { name: "Mock select event" }));

    expect(linkCalendarEvent).toHaveBeenCalledTimes(1);
    expect(linkCalendarEvent).toHaveBeenCalledWith("sess-1", "evt-1");
    expect(onSessionChange).toHaveBeenCalledWith(updated);

    // Picker closes on success.
    expect(screen.queryByRole("button", { name: "Mock select event" })).not.toBeInTheDocument();
  });

  it("shows an inline error and keeps the picker open when linking fails (e.g. 422 — no Meet link)", async () => {
    const user = userEvent.setup();
    vi.mocked(linkCalendarEvent).mockRejectedValue(new Error("Link calendar event failed: 422"));
    const onSessionChange = vi.fn();

    renderNotesTab(makeSession(), onSessionChange);

    await user.click(screen.getByRole("button", { name: "Choose from Google Calendar →" }));
    await user.click(screen.getByRole("button", { name: "Mock select event" }));

    expect(await screen.findByText("Link calendar event failed: 422")).toBeInTheDocument();
    expect(onSessionChange).not.toHaveBeenCalled();
    // Picker remains open — nothing changed.
    expect(screen.getByRole("button", { name: "Mock select event" })).toBeInTheDocument();
  });

  it("shows a 'via Google Calendar' badge and Unlink action next to Join call when linked", () => {
    renderNotesTab(
      makeSession({
        google_calendar_event_id: "evt-1",
        meeting_url: "https://meet.google.com/abc-defg-hij",
      }),
    );

    expect(screen.getByRole("link", { name: "Join call →" })).toBeInTheDocument();
    expect(screen.getByText("via Google Calendar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unlink" })).toBeInTheDocument();
  });

  it("does NOT show the badge/Unlink when meeting_url is set but not calendar-linked", () => {
    renderNotesTab(makeSession({ meeting_url: "https://zoom.us/j/123", google_calendar_event_id: null }));

    expect(screen.getByRole("link", { name: "Join call →" })).toBeInTheDocument();
    expect(screen.queryByText("via Google Calendar")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unlink" })).not.toBeInTheDocument();
  });

  it("Unlink calls linkCalendarEvent(session.id, null), then onSessionChange", async () => {
    const user = userEvent.setup();
    const unlinked = makeSession({
      meeting_url: "https://meet.google.com/abc-defg-hij",
      google_calendar_event_id: null,
    });
    vi.mocked(linkCalendarEvent).mockResolvedValue(unlinked);
    const onSessionChange = vi.fn();

    renderNotesTab(
      makeSession({
        google_calendar_event_id: "evt-1",
        meeting_url: "https://meet.google.com/abc-defg-hij",
      }),
      onSessionChange,
    );

    await user.click(screen.getByRole("button", { name: "Unlink" }));

    expect(linkCalendarEvent).toHaveBeenCalledTimes(1);
    expect(linkCalendarEvent).toHaveBeenCalledWith("sess-1", null);
    expect(onSessionChange).toHaveBeenCalledWith(unlinked);
  });

  it("shows an inline error and does not call onSessionChange when Unlink fails", async () => {
    const user = userEvent.setup();
    vi.mocked(linkCalendarEvent).mockRejectedValue(new Error("Link calendar event failed: 500"));
    const onSessionChange = vi.fn();

    renderNotesTab(
      makeSession({
        google_calendar_event_id: "evt-1",
        meeting_url: "https://meet.google.com/abc-defg-hij",
      }),
      onSessionChange,
    );

    await user.click(screen.getByRole("button", { name: "Unlink" }));

    expect(await screen.findByText("Link calendar event failed: 500")).toBeInTheDocument();
    expect(onSessionChange).not.toHaveBeenCalled();
  });
});
