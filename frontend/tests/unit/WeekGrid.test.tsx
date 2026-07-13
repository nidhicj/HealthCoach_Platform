import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WeekGrid } from "@/components/calendar/WeekGrid";
import type { CalendarEvent } from "@/lib/api/calendar";

function makeEvent(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    id: "id",
    summary: "summary",
    start: "2026-01-05T09:00:00",
    end: "2026-01-05T10:00:00",
    hangout_link: null,
    html_link: "https://calendar.google.com/event?eid=x",
    location: null,
    ...overrides,
  };
}

describe("WeekGrid", () => {
  // Fixed week: Sun Jan 4, 2026 - Sat Jan 10, 2026.
  const weekStart = new Date(2026, 0, 4);

  const mondayEvent = makeEvent({
    id: "e-monday",
    summary: "Morning Sync",
    start: "2026-01-05T09:00:00",
    end: "2026-01-05T10:00:00",
  });
  // Two overlapping events on Wednesday: 10:00-11:00 and 10:30-11:30.
  const overlapOne = makeEvent({
    id: "e-overlap-1",
    summary: "Overlap One",
    start: "2026-01-07T10:00:00",
    end: "2026-01-07T11:00:00",
  });
  const overlapTwo = makeEvent({
    id: "e-overlap-2",
    summary: "Overlap Two",
    start: "2026-01-07T10:30:00",
    end: "2026-01-07T11:30:00",
  });

  const events = [mondayEvent, overlapOne, overlapTwo];

  it("renders 7 day columns, positions events by time-of-day, keeps overlapping events both visible side-by-side, and reports the exact event object on click", async () => {
    const user = userEvent.setup();
    const onSelectEvent = vi.fn();

    render(<WeekGrid weekStart={weekStart} events={events} onSelectEvent={onSelectEvent} />);

    const dayColumns = screen.getAllByTestId("day-column");
    expect(dayColumns).toHaveLength(7);

    // Monday's event renders inside Monday's column specifically.
    const mondayColumn = dayColumns.find((el) => el.getAttribute("data-date") === "2026-01-05");
    expect(mondayColumn).toBeTruthy();
    const mondayButton = within(mondayColumn!).getByRole("button", { name: "Morning Sync" });
    // Anchored from day-start (00:00): 9:00 AM = 540 minutes in.
    expect(mondayButton.style.top).toBe("540px");
    expect(mondayButton.style.height).toBe("60px");

    // It must not leak into another day's column.
    const tuesdayColumn = dayColumns.find((el) => el.getAttribute("data-date") === "2026-01-06");
    expect(within(tuesdayColumn!).queryByText("Morning Sync")).not.toBeInTheDocument();

    // Wednesday: both overlapping events render (neither dropped), positioned
    // side-by-side (narrower than full width, non-overlapping horizontally).
    const wednesdayColumn = dayColumns.find((el) => el.getAttribute("data-date") === "2026-01-07");
    expect(wednesdayColumn).toBeTruthy();
    const overlapOneButton = within(wednesdayColumn!).getByRole("button", { name: "Overlap One" });
    const overlapTwoButton = within(wednesdayColumn!).getByRole("button", { name: "Overlap Two" });
    expect(overlapOneButton).toBeInTheDocument();
    expect(overlapTwoButton).toBeInTheDocument();
    // Equal-width split for a 2-event cluster: 50% each, side-by-side.
    expect(overlapOneButton.style.width).toBe("50%");
    expect(overlapTwoButton.style.width).toBe("50%");
    expect(overlapOneButton.style.left).toBe("0%");
    expect(overlapTwoButton.style.left).toBe("50%");
    // Vertical position still reflects each event's own start time.
    expect(overlapOneButton.style.top).toBe("600px");
    expect(overlapTwoButton.style.top).toBe("630px");

    // Clicking an event calls onSelectEvent with the exact event object.
    await user.click(mondayButton);
    expect(onSelectEvent).toHaveBeenCalledTimes(1);
    expect(onSelectEvent).toHaveBeenCalledWith(mondayEvent);
  });
});
