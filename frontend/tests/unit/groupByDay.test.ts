import { describe, expect, it } from "vitest";
import { groupMealLogsByDay } from "@/components/meal-logs/groupByDay";
import type { MealLogOut } from "@/lib/api/mealLogs";

function meal(overrides: Partial<MealLogOut>): MealLogOut {
  return {
    id: "1", client_id: "c1", hc_user_id: "hc1",
    meal_slot: "breakfast", description: null,
    photo_original_filename: "x.jpg", photo_mime_type: "image/jpeg",
    captured_at: null, logged_at: "2026-07-20T08:00:00Z",
    hc_reaction: null, reacted_at: null,
    ...overrides,
  };
}

describe("groupMealLogsByDay", () => {
  it("groups by captured_at's date when present", () => {
    // Chosen so captured_at and logged_at fall on different IST calendar days, so the
    // assertion unambiguously proves captured_at takes precedence (rather than the two
    // timestamps coincidentally landing on the same IST day).
    const logs = [meal({ id: "a", captured_at: "2026-07-19T10:00:00Z", logged_at: "2026-07-20T10:00:00Z" })];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].day).toBe("2026-07-19");
  });

  it("falls back to logged_at's date when captured_at is null", () => {
    const logs = [meal({ id: "a", captured_at: null, logged_at: "2026-07-20T06:00:00Z" })];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].day).toBe("2026-07-20");
  });

  it("groups by the IST calendar day, not the UTC one, near the day boundary", () => {
    // 2026-07-19T22:30:00Z is 2026-07-20T04:00:00 IST (UTC+5:30) — should bucket under the
    // *next* UTC day, proving grouping uses Asia/Kolkata rather than raw UTC.
    const logs = [meal({ id: "a", captured_at: "2026-07-19T22:30:00Z", logged_at: "2026-07-19T22:30:00Z" })];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].day).toBe("2026-07-20");
  });

  it("orders entries within a day by fixed meal-slot sequence, not by time", () => {
    // Both timestamps kept before 18:30 UTC so they land on the same IST calendar day
    // (18:30 UTC = 00:00 IST the next day) — isolates the slot-ordering behavior under test
    // from the IST day-boundary logic covered separately above.
    const logs = [
      meal({ id: "dinner", meal_slot: "dinner", logged_at: "2026-07-20T14:00:00Z" }),
      meal({ id: "breakfast", meal_slot: "breakfast", logged_at: "2026-07-20T08:00:00Z" }),
    ];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].entries.map((e) => e.id)).toEqual(["breakfast", "dinner"]);
  });

  it("orders entries sharing the same meal slot by logged_at ascending", () => {
    const logs = [
      meal({ id: "later", meal_slot: "breakfast", logged_at: "2026-07-20T08:30:00Z" }),
      meal({ id: "earlier", meal_slot: "breakfast", logged_at: "2026-07-20T07:00:00Z" }),
    ];
    const groups = groupMealLogsByDay(logs);
    expect(groups[0].entries.map((e) => e.id)).toEqual(["earlier", "later"]);
  });

  it("orders days most-recent-first", () => {
    const logs = [
      meal({ id: "old", logged_at: "2026-07-18T08:00:00Z" }),
      meal({ id: "new", logged_at: "2026-07-20T08:00:00Z" }),
    ];
    const groups = groupMealLogsByDay(logs);
    expect(groups.map((g) => g.day)).toEqual(["2026-07-20", "2026-07-18"]);
  });
});
