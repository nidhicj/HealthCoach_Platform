import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CreateEventForm } from "@/components/calendar/CreateEventForm";
import type { CalendarEvent } from "@/lib/api/calendar";
import { createCalendarEvent } from "@/lib/api/calendar";

vi.mock("@/lib/api/calendar", () => ({
  createCalendarEvent: vi.fn(),
}));

function makeEvent(overrides: Partial<CalendarEvent> = {}): CalendarEvent {
  return {
    id: "evt-1",
    summary: "Client check-in",
    start: "2026-07-15T09:00:00.000Z",
    end: "2026-07-15T09:30:00.000Z",
    hangout_link: "https://meet.google.com/abc-defg-hij",
    html_link: "https://calendar.google.com/event?eid=x",
    location: null,
    ...overrides,
  };
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/title/i), "Client check-in");
  fireEvent.change(screen.getByLabelText(/start/i), { target: { value: "2026-07-15T09:00" } });
  fireEvent.change(screen.getByLabelText(/end/i), { target: { value: "2026-07-15T09:30" } });
  await user.click(screen.getByRole("button", { name: /create event/i }));
}

describe("CreateEventForm", () => {
  beforeEach(() => {
    vi.mocked(createCalendarEvent).mockReset();
  });

  it("defaults the Add Google Meet checkbox to checked", () => {
    render(<CreateEventForm onCreated={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("checkbox", { name: /add google meet/i })).toBeChecked();
  });

  it("submits the form with the exact expected payload and calls onCreated with the returned event", async () => {
    const user = userEvent.setup();
    const event = makeEvent();
    vi.mocked(createCalendarEvent).mockResolvedValue(event);
    const onCreated = vi.fn();

    render(<CreateEventForm onCreated={onCreated} onCancel={vi.fn()} />);
    await fillAndSubmit(user);

    expect(createCalendarEvent).toHaveBeenCalledTimes(1);
    expect(createCalendarEvent).toHaveBeenCalledWith({
      summary: "Client check-in",
      start: new Date("2026-07-15T09:00").toISOString(),
      end: new Date("2026-07-15T09:30").toISOString(),
      add_meet: true,
    });

    expect(onCreated).toHaveBeenCalledTimes(1);
    expect(onCreated).toHaveBeenCalledWith(event);
  });

  it("respects an unchecked Add Google Meet checkbox in the payload", async () => {
    const user = userEvent.setup();
    vi.mocked(createCalendarEvent).mockResolvedValue(makeEvent());

    render(<CreateEventForm onCreated={vi.fn()} onCancel={vi.fn()} />);
    await user.click(screen.getByRole("checkbox", { name: /add google meet/i }));
    await fillAndSubmit(user);

    expect(createCalendarEvent).toHaveBeenCalledWith(
      expect.objectContaining({ add_meet: false }),
    );
  });

  it("shows an inline error and does NOT call onCreated when the API call fails", async () => {
    const user = userEvent.setup();
    vi.mocked(createCalendarEvent).mockRejectedValue(new Error("Create calendar event failed: 500"));
    const onCreated = vi.fn();

    render(<CreateEventForm onCreated={onCreated} onCancel={vi.fn()} />);
    await fillAndSubmit(user);

    expect(await screen.findByText("Create calendar event failed: 500")).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("falls back to a generic inline error when a non-Error rejection is thrown", async () => {
    const user = userEvent.setup();
    vi.mocked(createCalendarEvent).mockRejectedValue("network down");
    const onCreated = vi.fn();

    render(<CreateEventForm onCreated={onCreated} onCancel={vi.fn()} />);
    await fillAndSubmit(user);

    expect(await screen.findByText(/could not create event/i)).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("calls onCancel when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<CreateEventForm onCreated={vi.fn()} onCancel={onCancel} />);

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(createCalendarEvent).not.toHaveBeenCalled();
  });

  it("shows a validation error and does NOT call createCalendarEvent when end time equals start time", async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();

    render(<CreateEventForm onCreated={onCreated} onCancel={vi.fn()} />);
    await user.type(screen.getByLabelText(/title/i), "Client check-in");
    fireEvent.change(screen.getByLabelText(/start/i), { target: { value: "2026-07-15T09:00" } });
    fireEvent.change(screen.getByLabelText(/end/i), { target: { value: "2026-07-15T09:00" } });
    await user.click(screen.getByRole("button", { name: /create event/i }));

    expect(await screen.findByText("End time must be after start time.")).toBeInTheDocument();
    expect(createCalendarEvent).not.toHaveBeenCalled();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("shows a validation error and does NOT call createCalendarEvent when end time is before start time", async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();

    render(<CreateEventForm onCreated={onCreated} onCancel={vi.fn()} />);
    await user.type(screen.getByLabelText(/title/i), "Client check-in");
    fireEvent.change(screen.getByLabelText(/start/i), { target: { value: "2026-07-15T10:00" } });
    fireEvent.change(screen.getByLabelText(/end/i), { target: { value: "2026-07-15T09:00" } });
    await user.click(screen.getByRole("button", { name: /create event/i }));

    expect(await screen.findByText("End time must be after start time.")).toBeInTheDocument();
    expect(createCalendarEvent).not.toHaveBeenCalled();
    expect(onCreated).not.toHaveBeenCalled();
  });

  // PHASE-01f Task 5 — pre-filled title.
  describe("defaultTitle", () => {
    it("pre-fills the title input with defaultTitle on mount", () => {
      render(<CreateEventForm onCreated={vi.fn()} onCancel={vi.fn()} defaultTitle="Session-3 with Asha" />);

      expect(screen.getByLabelText(/title/i)).toHaveValue("Session-3 with Asha");
    });

    it("leaves the title blank when defaultTitle is not provided", () => {
      render(<CreateEventForm onCreated={vi.fn()} onCancel={vi.fn()} />);

      expect(screen.getByLabelText(/title/i)).toHaveValue("");
    });

    it("remains editable and submits the edited value instead of the default", async () => {
      const user = userEvent.setup();
      vi.mocked(createCalendarEvent).mockResolvedValue(makeEvent());

      render(<CreateEventForm onCreated={vi.fn()} onCancel={vi.fn()} defaultTitle="Session-3 with Asha" />);

      const titleInput = screen.getByLabelText(/title/i);
      await user.clear(titleInput);
      await user.type(titleInput, "Rescheduled sync");
      fireEvent.change(screen.getByLabelText(/start/i), { target: { value: "2026-07-15T09:00" } });
      fireEvent.change(screen.getByLabelText(/end/i), { target: { value: "2026-07-15T09:30" } });
      await user.click(screen.getByRole("button", { name: /create event/i }));

      expect(createCalendarEvent).toHaveBeenCalledWith(
        expect.objectContaining({ summary: "Rescheduled sync" }),
      );
    });
  });
});
