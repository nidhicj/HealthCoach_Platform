import { MEAL_SLOTS, type MealLogOut, type MealSlot } from "@/lib/api/mealLogs";

const SLOT_ORDER: Record<MealSlot, number> = Object.fromEntries(
  MEAL_SLOTS.map((slot, i) => [slot, i]),
) as Record<MealSlot, number>;

const IST_DATE_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function dayKey(log: MealLogOut): string {
  // Decision 3/1: captured_at's date when present, else logged_at's — both computed in
  // Asia/Kolkata (IST, UTC+5:30) explicitly, not the browser's ambient local timezone and not
  // UTC, matching this app's IST-first assumption elsewhere (e.g. PHASE-02b's Saturday cron).
  // en-CA formats as YYYY-MM-DD, which sorts correctly as a plain string.
  const iso = log.captured_at ?? log.logged_at;
  return IST_DATE_FORMATTER.format(new Date(iso));
}

// PHASE-03 final review Finding I3: day headings and meal times must be formatted
// explicitly in Asia/Kolkata, matching the grouping logic above — otherwise the
// heading/time shown depends on the viewer's browser timezone (e.g. new
// Date("2026-07-20").toLocaleDateString() parses "YYYY-MM-DD" as UTC midnight,
// then formats in the browser's ambient local zone, which can land on the wrong
// day name for a browser west of UTC).

export function formatDayHeading(day: string): string {
  // day is "YYYY-MM-DD" already computed in IST by dayKey above — parse as a
  // UTC instant at that calendar date, then render with an explicit
  // Asia/Kolkata timeZone so the displayed weekday/date never shifts with the
  // viewer's local timezone.
  const [year, month, date] = day.split("-").map(Number);
  const d = new Date(Date.UTC(year, month - 1, date));
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Kolkata",
    weekday: "long",
    month: "short",
    day: "numeric",
  }).format(d);
}

export function formatMealTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
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
