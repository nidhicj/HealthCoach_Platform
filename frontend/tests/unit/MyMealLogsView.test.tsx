/**
 * PHASE-03 final review Finding I2.3 — MyMealLogsView (client-side /me/chat page's
 * Logged Meals sub-view). Mirrors TextView.test.tsx's mocking style: mock the API
 * module, render the component directly, assert on rendered output and validation.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MyMealLogsView } from "@/app/me/chat/page";
import { listMyMealLogs, submitMyMealLog, type MealLogOut } from "@/lib/api/mealLogs";

vi.mock("@/lib/api/mealLogs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/mealLogs")>();
  return {
    ...actual,
    listMyMealLogs: vi.fn(),
    submitMyMealLog: vi.fn(),
  };
});

// Sidesteps AuthedImage's real fetchWithAuth/blob/object-URL flow — irrelevant to
// this component's own logic (submit validation, list rendering).
vi.mock("@/components/authed-image", () => ({
  AuthedImage: ({ alt }: { alt: string }) => <img alt={alt} />,
}));

function meal(overrides: Partial<MealLogOut> = {}): MealLogOut {
  return {
    id: "meal-1",
    client_id: "client-1",
    hc_user_id: "hc-1",
    meal_slot: "breakfast",
    description: "Idli and sambar",
    photo_original_filename: "breakfast.jpg",
    photo_mime_type: "image/jpeg",
    captured_at: null,
    logged_at: "2026-07-20T02:00:00Z",
    hc_reaction: null,
    reacted_at: null,
    ...overrides,
  };
}

describe("MyMealLogsView", () => {
  beforeEach(() => {
    vi.mocked(listMyMealLogs).mockReset();
    vi.mocked(submitMyMealLog).mockReset();
    vi.mocked(listMyMealLogs).mockResolvedValue({ items: [], next_cursor: null });
  });

  it("shows an inline error and does not submit when no photo is attached", async () => {
    const user = userEvent.setup();

    render(<MyMealLogsView />);
    await waitFor(() => screen.getByText(/no meals logged yet/i));

    await user.click(screen.getByRole("button", { name: /^log meal$/i }));

    await waitFor(() => screen.getByText(/a photo is required to log a meal/i));
    expect(submitMyMealLog).not.toHaveBeenCalled();
  });

  it("submits with a photo and shows the new entry in the list", async () => {
    vi.mocked(submitMyMealLog).mockResolvedValue(meal());
    const user = userEvent.setup();

    render(<MyMealLogsView />);
    await waitFor(() => screen.getByText(/no meals logged yet/i));

    const file = new File(["fake-image-bytes"], "breakfast.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, file);

    await user.click(screen.getByRole("button", { name: /^log meal$/i }));

    await waitFor(() => expect(submitMyMealLog).toHaveBeenCalledTimes(1));
    await waitFor(() => screen.getByText("Idli and sambar"));
    expect(screen.queryByText(/no meals logged yet/i)).not.toBeInTheDocument();
  });
});
