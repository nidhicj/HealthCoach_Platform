/**
 * PHASE-01e Task 16 — separate from NotesTab.test.tsx, which mocks
 * CalendarView entirely to isolate the linking wiring. This file renders the
 * REAL CalendarView inside the picker (only its own API module is mocked,
 * same as tests/unit/CalendarView.test.tsx), to verify the not-connected path
 * end-to-end: opening "Choose from Google Calendar →" on a session with no
 * Google Calendar connection shows the real "Connect Google Calendar" CTA.
 *
 * This substitutes, at the automated/UI-state level, for Task 16's manual
 * checklist item 1 (see PHASE-01e Task 16 report) — it does not require a
 * live Google account, unlike checklist items 2-4, 6, 8.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotesTab } from "@/app/(app)/clients/[clientId]/sessions/[sessionId]/page";
import { linkCalendarEvent, patchSession } from "@/lib/api/sessions";
import type { SessionOut } from "@/lib/api/sessions";
import { getCalendarStatus, getCalendarConnectUrl, listCalendarEvents } from "@/lib/api/calendar";

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
    notes_internal: null,
    session_notes: null,
    created_at: "2026-07-01T00:00:00Z",
    ...overrides,
  };
}

describe("NotesTab — Google Calendar picker, real CalendarView, not-connected path", () => {
  beforeEach(() => {
    vi.mocked(linkCalendarEvent).mockReset();
    vi.mocked(patchSession).mockReset();
    vi.mocked(getCalendarStatus).mockReset();
    vi.mocked(getCalendarConnectUrl).mockReset();
    vi.mocked(listCalendarEvents).mockReset();
  });

  it("shows the real 'Connect Google Calendar' CTA when opening the picker with no calendar connection", async () => {
    const user = userEvent.setup();
    vi.mocked(getCalendarStatus).mockResolvedValue({
      connected: false,
      google_account_email: null,
      connected_at: null,
      needs_reauth: false,
    });

    render(
      <NotesTab
        session={makeSession()}
        files={[]}
        filesLoading={false}
        onFilesChange={vi.fn()}
        onSessionChange={vi.fn()}
        onNext={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Choose from Google Calendar →" }));

    expect(
      await screen.findByRole("button", { name: "Connect Google Calendar" }),
    ).toBeInTheDocument();
    expect(listCalendarEvents).not.toHaveBeenCalled();
  });
});
