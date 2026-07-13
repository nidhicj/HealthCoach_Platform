import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { addDays, addMonths, endOfDay, format, startOfDay, startOfMonth, startOfWeek, subMonths } from "date-fns";
import { CalendarView } from "@/components/calendar/CalendarView";
import type { CalendarEvent, CalendarStatus } from "@/lib/api/calendar";
import { getCalendarStatus, getCalendarConnectUrl, listCalendarEvents } from "@/lib/api/calendar";

// Mirrors CalendarView's internal visibleRange() for month view, so tests can
// assert exact listCalendarEvents call args without hardcoding dates.
function expectedMonthRange(anchor: Date): [string, string] {
  const start = startOfWeek(startOfMonth(anchor));
  const end = addDays(start, 41);
  return [startOfDay(start).toISOString(), endOfDay(end).toISOString()];
}

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

  it("navigation: clicking next in month view advances the anchor by one month", async () => {
    const user = userEvent.setup();
    vi.mocked(getCalendarStatus).mockResolvedValue(makeStatus({ connected: true, needs_reauth: false }));
    vi.mocked(listCalendarEvents).mockResolvedValue([]);

    render(<CalendarView onSelectEvent={vi.fn()} />);

    const today = new Date();
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(today, "MMMM yyyy"));
    expect(listCalendarEvents).toHaveBeenCalledTimes(1);
    const [initialMin, initialMax] = expectedMonthRange(today);
    expect(listCalendarEvents).toHaveBeenNthCalledWith(1, initialMin, initialMax);

    await user.click(screen.getByRole("button", { name: "Next" }));

    const nextMonth = addMonths(today, 1);
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(nextMonth, "MMMM yyyy"));
    const [nextMin, nextMax] = expectedMonthRange(nextMonth);
    expect(listCalendarEvents).toHaveBeenCalledTimes(2);
    expect(listCalendarEvents).toHaveBeenNthCalledWith(2, nextMin, nextMax);
  });

  it("navigation: clicking previous in month view goes back one month", async () => {
    const user = userEvent.setup();
    vi.mocked(getCalendarStatus).mockResolvedValue(makeStatus({ connected: true, needs_reauth: false }));
    vi.mocked(listCalendarEvents).mockResolvedValue([]);

    render(<CalendarView onSelectEvent={vi.fn()} />);

    const today = new Date();
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(today, "MMMM yyyy"));

    await user.click(screen.getByRole("button", { name: "Previous" }));

    const prevMonth = subMonths(today, 1);
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(prevMonth, "MMMM yyyy"));
    const [prevMin, prevMax] = expectedMonthRange(prevMonth);
    expect(listCalendarEvents).toHaveBeenCalledTimes(2);
    expect(listCalendarEvents).toHaveBeenNthCalledWith(2, prevMin, prevMax);
  });

  it("navigation: switching view mode after navigating away from today preserves the anchor", async () => {
    const user = userEvent.setup();
    vi.mocked(getCalendarStatus).mockResolvedValue(makeStatus({ connected: true, needs_reauth: false }));
    vi.mocked(listCalendarEvents).mockResolvedValue([]);

    render(<CalendarView onSelectEvent={vi.fn()} />);

    const today = new Date();
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(today, "MMMM yyyy"));

    await user.click(screen.getByRole("button", { name: "Next" }));
    const nextMonth = addMonths(today, 1);
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(nextMonth, "MMMM yyyy"));

    // Switch to week view — must show the navigated-to month's week, not today's.
    await user.click(screen.getByRole("tab", { name: "Week" }));
    const expectedWeekStart = startOfWeek(nextMonth);
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(expectedWeekStart, "MMM d"));
    expect(screen.getByTestId("calendar-range-label")).not.toHaveTextContent(format(today, "MMM d"));

    // Switch back to month view — should still show the navigated month, not reset to today.
    await user.click(screen.getByRole("tab", { name: "Month" }));
    expect(await screen.findByTestId("calendar-range-label")).toHaveTextContent(format(nextMonth, "MMMM yyyy"));
  });
});
