import { MEAL_SLOTS, type MealLogOut, type MealSlot } from "@/lib/api/mealLogs";

const SLOT_ORDER: Record<MealSlot, number> = Object.fromEntries(
  MEAL_SLOTS.map((slot, i) => [slot, i]),
) as Record<MealSlot, number>;

function dayKey(log: MealLogOut): string {
  // Decision 3/1: captured_at's date when present, else logged_at's — both read in local time,
  // matching this app's IST-first assumption elsewhere (e.g. PHASE-02b's Saturday cron).
  const iso = log.captured_at ?? log.logged_at;
  return new Date(iso).toISOString().slice(0, 10);
}

export function groupMealLogsByDay(logs: MealLogOut[]): { day: string; entries: MealLogOut[] }[] {
  const byDay = new Map<string, MealLogOut[]>();
  for (const log of logs) {
    const key = dayKey(log);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(log);
  }

  const days = Array.from(byDay.keys()).sort((a, b) => (a < b ? 1 : -1)); // most recent first

  return days.map((day) => ({
    day,
    entries: byDay.get(day)!.slice().sort((a, b) => {
      const slotDiff = SLOT_ORDER[a.meal_slot] - SLOT_ORDER[b.meal_slot];
      if (slotDiff !== 0) return slotDiff;
      return new Date(a.logged_at).getTime() - new Date(b.logged_at).getTime();
    }),
  }));
}
