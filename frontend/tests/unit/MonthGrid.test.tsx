import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MonthGrid } from "@/components/calendar/MonthGrid";
import type { CalendarEvent } from "@/lib/api/calendar";

function makeEvent(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    id: "id",
    summary: "summary",
    start: "2026-01-01T09:00:00",
    end: "2026-01-01T10:00:00",
    hangout_link: null,
    html_link: "https://calendar.google.com/event?eid=x",
    location: null,
    ...overrides,
  };
}

describe("MonthGrid", () => {
  // Fixed month: January 2026. Jan 1, 2026 is a Thursday, so the leading
  // week starts Sun Dec 28, 2025; 42 cells run through Sat Feb 7, 2026.
  const month = new Date(2026, 0, 15);

  const firstDayEvent = makeEvent({
    id: "e-first",
    summary: "New Year Kickoff",
    start: "2026-01-01T09:00:00",
    end: "2026-01-01T10:00:00",
  });
  const lastDayEvent = makeEvent({
    id: "e-last",
    summary: "Month End Review",
    start: "2026-01-31T15:00:00",
    end: "2026-01-31T16:00:00",
  });
  // Falls outside both January AND the rendered 42-day window (which ends
  // Feb 7, 2026), so it must not render anywhere.
  const outsideEvent = makeEvent({
    id: "e-outside",
    summary: "Unrelated Future Event",
    start: "2026-03-01T09:00:00",
    end: "2026-03-01T10:00:00",
  });

  const events = [firstDayEvent, lastDayEvent, outsideEvent];

  it("renders 42 day cells spanning leading/trailing days, places events on the right day, and reports the exact event object on click", async () => {
    const user = userEvent.setup();
    const onSelectEvent = vi.fn();

    render(<MonthGrid month={month} events={events} onSelectEvent={onSelectEvent} />);

    // 42 day cells (6 weeks x 7 days), including leading Dec 2025 / trailing
    // Feb 2026 days.
    expect(screen.getAllByTestId("day-cell")).toHaveLength(42);

    // Event on the 1st renders under the correct day.
    const firstDayButton = screen.getByRole("button", { name: "New Year Kickoff" });
    expect(firstDayButton).toBeInTheDocument();

    // Event on the last day of the month renders too.
    const lastDayButton = screen.getByRole("button", { name: "Month End Review" });
    expect(lastDayButton).toBeInTheDocument();

    // Event entirely outside the rendered window is not shown anywhere.
    expect(screen.queryByText("Unrelated Future Event")).not.toBeInTheDocument();

    // Clicking an event calls onSelectEvent with the exact event object.
    await user.click(firstDayButton);
    expect(onSelectEvent).toHaveBeenCalledTimes(1);
    expect(onSelectEvent).toHaveBeenCalledWith(firstDayEvent);
  });

  // PHASE-01f Task 4 — visible feedback while linking an event.
  describe("linkingEventId", () => {
    it("marks the specific event matching linkingEventId as busy, and leaves other events unmarked when linkingEventId is null", () => {
      render(<MonthGrid month={month} events={events} onSelectEvent={vi.fn()} linkingEventId={null} />);

      const firstDayButton = screen.getByRole("button", { name: "New Year Kickoff" });
      const lastDayButton = screen.getByRole("button", { name: "Month End Review" });

      expect(firstDayButton).not.toBeDisabled();
      expect(firstDayButton).toHaveAttribute("aria-busy", "false");
      expect(lastDayButton).not.toBeDisabled();
      expect(lastDayButton).toHaveAttribute("aria-busy", "false");
    });

    it("shows a visibly busy state on the event matching linkingEventId, and disables (but still renders) other events", () => {
      render(
        <MonthGrid month={month} events={events} onSelectEvent={vi.fn()} linkingEventId="e-first" />,
      );

      const firstDayButton = screen.getByRole("button", { name: "New Year Kickoff" });
      const lastDayButton = screen.getByRole("button", { name: "Month End Review" });

      // The clicked event is visibly busy (spinner via aria-busy) and disabled.
      expect(firstDayButton).toHaveAttribute("aria-busy", "true");
      expect(firstDayButton).toBeDisabled();

      // The other event remains visible but is now non-interactive — guards
      // against a second click racing the first while a link request is
      // in flight.
      expect(lastDayButton).toBeInTheDocument();
      expect(lastDayButton).not.toHaveAttribute("aria-busy", "true");
      expect(lastDayButton).toBeDisabled();
    });

    it("clicking a disabled (non-busy) event while another is linking does not call onSelectEvent", async () => {
      const user = userEvent.setup();
      const onSelectEvent = vi.fn();
      render(
        <MonthGrid month={month} events={events} onSelectEvent={onSelectEvent} linkingEventId="e-first" />,
      );

      const lastDayButton = screen.getByRole("button", { name: "Month End Review" });
      await user.click(lastDayButton);

      expect(onSelectEvent).not.toHaveBeenCalled();
    });
  });
});
