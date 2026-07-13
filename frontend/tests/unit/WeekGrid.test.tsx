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

  it("clusters a transitive overlap chain (A-B overlap, B-C overlap, A-C do not) into one 3-way equal-width split", () => {
    // Thursday: A 9:00-9:40, B 9:30-10:10, C 10:00-10:40.
    // A/B overlap 9:30-9:40, B/C overlap 10:00-10:10, A/C do not overlap at all.
    // The clustering algorithm is transitive (merges via shared cluster end),
    // so all three must still land in a single 3-way cluster, not two separate
    // 2-way pairs.
    const chainA = makeEvent({
      id: "e-chain-a",
      summary: "Chain A",
      start: "2026-01-08T09:00:00",
      end: "2026-01-08T09:40:00",
    });
    const chainB = makeEvent({
      id: "e-chain-b",
      summary: "Chain B",
      start: "2026-01-08T09:30:00",
      end: "2026-01-08T10:10:00",
    });
    const chainC = makeEvent({
      id: "e-chain-c",
      summary: "Chain C",
      start: "2026-01-08T10:00:00",
      end: "2026-01-08T10:40:00",
    });

    const onSelectEvent = vi.fn();
    render(
      <WeekGrid
        weekStart={weekStart}
        events={[chainA, chainB, chainC]}
        onSelectEvent={onSelectEvent}
      />,
    );

    const dayColumns = screen.getAllByTestId("day-column");
    const thursdayColumn = dayColumns.find((el) => el.getAttribute("data-date") === "2026-01-08");
    expect(thursdayColumn).toBeTruthy();

    const chainAButton = within(thursdayColumn!).getByRole("button", { name: "Chain A" });
    const chainBButton = within(thursdayColumn!).getByRole("button", { name: "Chain B" });
    const chainCButton = within(thursdayColumn!).getByRole("button", { name: "Chain C" });

    // Equal 3-way width split (1/3 * 100 in floating point), not a 2-way 50%
    // split — proves the cluster merged all three rather than pairing A/B and
    // leaving C alone, or vice versa.
    expect(chainAButton.style.width).toBe("33.33333333333333%");
    expect(chainBButton.style.width).toBe("33.33333333333333%");
    expect(chainCButton.style.width).toBe("33.33333333333333%");

    // Distinct left offsets in start-time order: A, B, C.
    expect(chainAButton.style.left).toBe("0%");
    expect(chainBButton.style.left).toBe("33.33333333333333%");
    expect(chainCButton.style.left).toBe("66.66666666666666%");

    // Vertical position still reflects each event's own start/end time.
    expect(chainAButton.style.top).toBe("540px");
    expect(chainAButton.style.height).toBe("40px");
    expect(chainBButton.style.top).toBe("570px");
    expect(chainBButton.style.height).toBe("40px");
    expect(chainCButton.style.top).toBe("600px");
    expect(chainCButton.style.height).toBe("40px");
  });
});
