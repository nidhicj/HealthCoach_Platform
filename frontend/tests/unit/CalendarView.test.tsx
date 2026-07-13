import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CalendarView } from "@/components/calendar/CalendarView";
import type { CalendarEvent, CalendarStatus } from "@/lib/api/calendar";
import { getCalendarStatus, getCalendarConnectUrl, listCalendarEvents } from "@/lib/api/calendar";

vi.mock("@/lib/api/calendar", () => ({
  getCalendarStatus: vi.fn(),
  getCalendarConnectUrl: vi.fn(),
  listCalendarEvents: vi.fn(),
}));

function makeStatus(overrides: Partial<CalendarStatus>): CalendarStatus {
  return {
    connected: false,
    google_account_email: null,
    connected_at: null,
    needs_reauth: false,
    ...overrides,
  };
}

// CalendarView anchors its visible range on the real system clock ("today"),
// so fixture events must fall on today's date (not a hardcoded past/future
// date) to land inside the rendered 42-day month grid / 7-day week grid.
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

describe("CalendarView", () => {
  beforeEach(() => {
    vi.mocked(getCalendarStatus).mockReset();
    vi.mocked(getCalendarConnectUrl).mockReset();
    vi.mocked(listCalendarEvents).mockReset();
    Object.defineProperty(window, "location", {
      writable: true,
      value: { href: "" },
    });
  });

  it("not-connected: shows a Connect CTA and redirects to the connect URL on click", async () => {
    const user = userEvent.setup();
    vi.mocked(getCalendarStatus).mockResolvedValue(makeStatus({ connected: false }));
    vi.mocked(getCalendarConnectUrl).mockResolvedValue("https://accounts.google.com/o/oauth2/auth?mock=1");

    render(<CalendarView onSelectEvent={vi.fn()} />);

    const connectButton = await screen.findByRole("button", { name: "Connect Google Calendar" });
    await user.click(connectButton);

    expect(getCalendarConnectUrl).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe("https://accounts.google.com/o/oauth2/auth?mock=1");
    expect(listCalendarEvents).not.toHaveBeenCalled();
  });

  it("needs_reauth: shows a Reconnect CTA with an explanatory line and redirects on click", async () => {
    const user = userEvent.setup();
    vi.mocked(getCalendarStatus).mockResolvedValue(
      makeStatus({ connected: true, needs_reauth: true, google_account_email: "coach@example.com" }),
    );
    vi.mocked(getCalendarConnectUrl).mockResolvedValue("https://accounts.google.com/o/oauth2/auth?mock=2");

    render(<CalendarView onSelectEvent={vi.fn()} />);

    expect(
      await screen.findByText(/Google Calendar connection needs to be renewed/i),
    ).toBeInTheDocument();

    const reconnectButton = screen.getByRole("button", { name: "Reconnect Google Calendar" });
    await user.click(reconnectButton);

    expect(getCalendarConnectUrl).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe("https://accounts.google.com/o/oauth2/auth?mock=2");
  });

  it("connected: fetches events for the visible range and renders them in MonthGrid", async () => {
    vi.mocked(getCalendarStatus).mockResolvedValue(
      makeStatus({ connected: true, needs_reauth: false, google_account_email: "coach@example.com" }),
    );
    const event = makeEvent({ id: "e-1", summary: "Client check-in" });
    vi.mocked(listCalendarEvents).mockResolvedValue([event]);

    render(<CalendarView onSelectEvent={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "Client check-in" })).toBeInTheDocument();
    expect(screen.getAllByTestId("day-cell")).toHaveLength(42);

    // Called once with a chronologically-ordered ISO range.
    expect(listCalendarEvents).toHaveBeenCalledTimes(1);
    const [timeMin, timeMax] = vi.mocked(listCalendarEvents).mock.calls[0];
    expect(new Date(timeMin).getTime()).toBeLessThan(new Date(timeMax).getTime());

    // Month/week toggle and create-event button are present.
    expect(screen.getByRole("tab", { name: "Month" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Week" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Create event" })).toBeInTheDocument();
  });

  it("connected: clicking an event calls onSelectEvent with the exact event object", async () => {
    const user = userEvent.setup();
    vi.mocked(getCalendarStatus).mockResolvedValue(makeStatus({ connected: true, needs_reauth: false }));
    const event = makeEvent({ id: "e-2", summary: "1:1 session" });
    vi.mocked(listCalendarEvents).mockResolvedValue([event]);
    const onSelectEvent = vi.fn();

    render(<CalendarView onSelectEvent={onSelectEvent} />);

    const eventButton = await screen.findByRole("button", { name: "1:1 session" });
    await user.click(eventButton);

    expect(onSelectEvent).toHaveBeenCalledTimes(1);
    expect(onSelectEvent).toHaveBeenCalledWith(event);
  });

  it("error: shows an inline error message (not a crash) when the events fetch fails", async () => {
    vi.mocked(getCalendarStatus).mockResolvedValue(makeStatus({ connected: true, needs_reauth: false }));
    vi.mocked(listCalendarEvents).mockRejectedValue(new Error("List calendar events failed: 409"));

    render(<CalendarView onSelectEvent={vi.fn()} />);

    expect(await screen.findByText(/could not load calendar events/i)).toBeInTheDocument();
    expect(screen.queryByTestId("day-cell")).not.toBeInTheDocument();
  });
});
