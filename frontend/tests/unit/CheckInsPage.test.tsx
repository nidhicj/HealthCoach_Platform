import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CheckInsPage from "@/app/me/checkins/page";
import { listMyCheckIns, submitMyCheckIn } from "@/lib/api/me";
import type { CheckInOut } from "@/lib/api/checkIns";

vi.mock("@/lib/api/me", () => ({
  listMyCheckIns: vi.fn(),
  submitMyCheckIn: vi.fn(),
}));

function makeCheckIn(overrides: Partial<CheckInOut> = {}): CheckInOut {
  return {
    id: "cin-1",
    client_id: "c-1",
    hc_user_id: "hc-1",
    payload: null,
    requested_at: null,
    sentiment_flag: null,
    created_at: "2026-07-30T12:00:00Z",
    ...overrides,
  };
}

async function pickThreeAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Energy levels", exact: true }));
  await user.click(screen.getByRole("button", { name: "Sleep quality", exact: true }));
  await user.click(screen.getByRole("button", { name: "Mood", exact: true }));
  await user.click(screen.getByRole("button", { name: /submit check-in/i }));
}

describe("CheckInsPage", () => {
  beforeEach(() => {
    vi.mocked(listMyCheckIns).mockReset();
    vi.mocked(submitMyCheckIn).mockReset();
  });

  it("shows the metrics form directly when a pending check-in exists", async () => {
    vi.mocked(listMyCheckIns).mockResolvedValue({
      items: [makeCheckIn({ requested_at: "2026-07-25T09:30:00Z", payload: null })],
      next_cursor: null,
    });

    render(<CheckInsPage />);

    expect(await screen.findByText(/your coach asked for a check-in/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /check in now/i })).not.toBeInTheDocument();
  });

  it("with nothing pending, shows the empty state plus a working 'Check in now' affordance", async () => {
    vi.mocked(listMyCheckIns).mockResolvedValue({ items: [], next_cursor: null });
    const user = userEvent.setup();

    render(<CheckInsPage />);

    expect(await screen.findByText(/nothing to answer right now/i)).toBeInTheDocument();
    const checkInNowBtn = screen.getByRole("button", { name: /check in now/i });
    expect(checkInNowBtn).toBeInTheDocument();

    // No metrics form until the button is clicked.
    expect(screen.queryByRole("button", { name: "Energy levels", exact: true })).not.toBeInTheDocument();

    await user.click(checkInNowBtn);

    expect(screen.getByRole("button", { name: "Energy levels", exact: true })).toBeInTheDocument();
  });

  it("submits an ad-hoc check-in from the 'Check in now' flow and collapses the form afterward", async () => {
    vi.mocked(listMyCheckIns).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(submitMyCheckIn).mockResolvedValue(
      makeCheckIn({ payload: { "Energy levels": 5, "Sleep quality": 5, Mood: 5 } }),
    );
    const user = userEvent.setup();

    render(<CheckInsPage />);
    await user.click(await screen.findByRole("button", { name: /check in now/i }));
    await pickThreeAndSubmit(user);

    await waitFor(() => expect(submitMyCheckIn).toHaveBeenCalledTimes(1));
    // Form collapses back to the empty state with the affordance restored.
    expect(await screen.findByText(/nothing to answer right now/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /check in now/i })).toBeInTheDocument();
  });

  it("shows a distinct load-error message when listMyCheckIns fails, and no 'Check in now' button", async () => {
    vi.mocked(listMyCheckIns).mockRejectedValue(new Error("List my check-ins failed: 500"));

    render(<CheckInsPage />);

    expect(await screen.findByText(/couldn.t load your check-ins/i)).toBeInTheDocument();
    expect(screen.queryByText(/nothing to answer right now/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /check in now/i })).not.toBeInTheDocument();
  });

  it("shows a submit-error message and re-enables the button when submitMyCheckIn fails", async () => {
    vi.mocked(listMyCheckIns).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(submitMyCheckIn).mockRejectedValue(new Error("Submit check-in failed: 500"));
    const user = userEvent.setup();

    render(<CheckInsPage />);
    await user.click(await screen.findByRole("button", { name: /check in now/i }));
    await pickThreeAndSubmit(user);

    expect(await screen.findByText(/couldn.t submit your check-in/i)).toBeInTheDocument();
    const submitBtn = screen.getByRole("button", { name: /submit check-in/i });
    expect(submitBtn).toBeEnabled();
  });
});
