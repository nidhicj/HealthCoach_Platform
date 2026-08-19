/**
 * PHASE-03 final review Finding I2.2 — LoggedMealsView (Chat tab's HC-side Logged
 * Meals sub-view). Mirrors TextView.test.tsx's mocking style: mock the API module,
 * render the component directly, assert on rendered output and error states.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoggedMealsView } from "@/app/(app)/clients/[clientId]/page";
import { listClientMealLogs, reactToMealLog, type MealLogOut } from "@/lib/api/mealLogs";

vi.mock("@/lib/api/mealLogs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/mealLogs")>();
  return {
    ...actual,
    listClientMealLogs: vi.fn(),
    reactToMealLog: vi.fn(),
  };
});

// Sidesteps AuthedImage's real fetchWithAuth/blob/object-URL flow — irrelevant to
// this component's own logic (day grouping, reaction handling, error surfacing).
vi.mock("@/components/authed-image", () => ({
  AuthedImage: ({ alt }: { alt: string }) => <img alt={alt} />,
}));

function meal(overrides: Partial<MealLogOut> = {}): MealLogOut {
  return {
    id: "meal-1",
    client_id: "client-1",
    hc_user_id: "hc-1",
    meal_slot: "lunch",
    description: "Dal, rice, and sabzi",
    photo_original_filename: "lunch.jpg",
    photo_mime_type: "image/jpeg",
    captured_at: "2026-07-20T07:00:00Z",
    logged_at: "2026-07-20T07:00:00Z",
    hc_reaction: null,
    reacted_at: null,
    ...overrides,
  };
}

describe("LoggedMealsView", () => {
  beforeEach(() => {
    vi.mocked(listClientMealLogs).mockReset();
    vi.mocked(reactToMealLog).mockReset();
  });

  it("renders a day heading and a meal card from the mocked list", async () => {
    vi.mocked(listClientMealLogs).mockResolvedValue({ items: [meal()], next_cursor: null });

    render(<LoggedMealsView clientId="client-1" />);

    await waitFor(() => screen.getByText("Dal, rice, and sabzi"));
    expect(screen.getByRole("heading", { level: 3 })).toBeInTheDocument();
    expect(screen.getByText("Lunch")).toBeInTheDocument();
  });

  it("clicking a reaction emoji calls reactToMealLog and highlights the clicked reaction", async () => {
    vi.mocked(listClientMealLogs).mockResolvedValue({ items: [meal()], next_cursor: null });
    vi.mocked(reactToMealLog).mockResolvedValue(meal({ hc_reaction: "happy", reacted_at: "2026-07-20T08:00:00Z" }));
    const user = userEvent.setup();

    render(<LoggedMealsView clientId="client-1" />);
    await waitFor(() => screen.getByText("Dal, rice, and sabzi"));

    const happyBtn = screen.getByRole("button", { name: "😊" });
    await user.click(happyBtn);

    await waitFor(() => expect(reactToMealLog).toHaveBeenCalledWith("client-1", "meal-1", "happy"));
    await waitFor(() => expect(happyBtn.className).toMatch(/bg-primary\/20/));
  });

  it("shows a visible error message when reacting fails", async () => {
    vi.mocked(listClientMealLogs).mockResolvedValue({ items: [meal()], next_cursor: null });
    vi.mocked(reactToMealLog).mockRejectedValue(new Error("React to meal log failed: 500"));
    const user = userEvent.setup();

    render(<LoggedMealsView clientId="client-1" />);
    await waitFor(() => screen.getByText("Dal, rice, and sabzi"));

    await user.click(screen.getByRole("button", { name: "😐" }));

    await waitFor(() => screen.getByText(/reaction failed to save/i));
  });
});
