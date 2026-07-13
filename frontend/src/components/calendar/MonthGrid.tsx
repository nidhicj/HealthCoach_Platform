import { addDays, eachDayOfInterval, format, isSameDay, isSameMonth, startOfMonth, startOfWeek } from "date-fns";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/lib/api/calendar";

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const GRID_CELL_COUNT = 42; // 6 weeks x 7 days, always a fixed-height grid.

export function MonthGrid({
  month,
  events,
  onSelectEvent,
  linkingEventId = null,
}: {
  month: Date; // any date within the month to display
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
  // Id of the event currently being linked (PHASE-01f Task 4), or null when
  // no link request is in flight. The matching event shows a visible busy
  // state; while any link request is in flight, all events are disabled to
  // guard against a second click racing the first.
  linkingEventId?: string | null;
}) {
  const gridStart = startOfWeek(startOfMonth(month));
  const days = eachDayOfInterval({ start: gridStart, end: addDays(gridStart, GRID_CELL_COUNT - 1) });

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="grid grid-cols-7 border-b border-border bg-muted/20">
        {WEEKDAY_LABELS.map((label) => (
          <div
            key={label}
            className="px-2 py-2 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
          >
            {label}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7">
        {days.map((day) => {
          const inMonth = isSameMonth(day, month);
          const dayEvents = events.filter((event) => isSameDay(new Date(event.start), day));

          return (
            <div
              key={day.toISOString()}
              data-testid="day-cell"
              className={cn(
                "min-h-24 space-y-1 border-b border-r border-border p-2",
                !inMonth && "bg-muted/20",
              )}
            >
              <p
                className={cn(
                  "font-sans text-xs font-bold",
                  inMonth ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {format(day, "d")}
              </p>
              {dayEvents.map((event) => {
                const isLinking = linkingEventId === event.id;
                const linkingInFlight = linkingEventId !== null;
                return (
                  <button
                    key={event.id}
                    type="button"
                    onClick={() => onSelectEvent(event)}
                    disabled={linkingInFlight}
                    aria-busy={isLinking}
                    className={cn(
                      "block w-full truncate rounded bg-primary/10 px-1.5 py-0.5 text-left font-sans text-xs text-foreground hover:bg-primary/20",
                      linkingInFlight && "opacity-60",
                    )}
                    title={event.summary}
                  >
                    {event.summary}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
