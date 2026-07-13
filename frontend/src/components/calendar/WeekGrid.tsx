import { addDays, differenceInMinutes, eachDayOfInterval, format, isSameDay, startOfDay } from "date-fns";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/lib/api/calendar";

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const PIXELS_PER_HOUR = 60;
const PIXELS_PER_MINUTE = PIXELS_PER_HOUR / 60;
const GRID_HEIGHT = HOURS.length * PIXELS_PER_HOUR;

function hourLabel(hour: number): string {
  return format(new Date(2000, 0, 1, hour), "h a");
}

type PositionedEvent = {
  event: CalendarEvent;
  top: number;
  height: number;
  left: string;
  width: string;
};

// Groups a day's events into clusters of mutually-overlapping events (by
// time range), then splits each cluster into equal-width side-by-side
// columns. This is a simple equal-width split, not pixel-perfect stacking
// (out of scope per PHASE-01e Task 10's design rationale).
function layoutDayEvents(dayEvents: CalendarEvent[], dayStart: Date): PositionedEvent[] {
  const withMinutes = dayEvents
    .map((event) => ({
      event,
      startMinutes: differenceInMinutes(new Date(event.start), dayStart),
      endMinutes: differenceInMinutes(new Date(event.end), dayStart),
    }))
    .sort((a, b) => a.startMinutes - b.startMinutes);

  const clusters: (typeof withMinutes)[] = [];
  let currentCluster: typeof withMinutes = [];
  let clusterEnd = -Infinity;

  for (const item of withMinutes) {
    if (currentCluster.length === 0 || item.startMinutes < clusterEnd) {
      currentCluster.push(item);
      clusterEnd = Math.max(clusterEnd, item.endMinutes);
    } else {
      clusters.push(currentCluster);
      currentCluster = [item];
      clusterEnd = item.endMinutes;
    }
  }
  if (currentCluster.length > 0) clusters.push(currentCluster);

  const positioned: PositionedEvent[] = [];
  for (const cluster of clusters) {
    const count = cluster.length;
    cluster.forEach((item, index) => {
      positioned.push({
        event: item.event,
        top: item.startMinutes * PIXELS_PER_MINUTE,
        height: Math.max((item.endMinutes - item.startMinutes) * PIXELS_PER_MINUTE, 15),
        left: `${(index / count) * 100}%`,
        width: `${(1 / count) * 100}%`,
      });
    });
  }
  return positioned;
}

export function WeekGrid({
  weekStart,
  events,
  onSelectEvent,
}: {
  weekStart: Date;
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
}) {
  const days = eachDayOfInterval({ start: weekStart, end: addDays(weekStart, 6) });

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="grid grid-cols-[3rem_repeat(7,1fr)] border-b border-border bg-muted/20">
        <div />
        {days.map((day) => (
          <div
            key={day.toISOString()}
            className="px-2 py-2 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
          >
            {format(day, "EEE d")}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-[3rem_repeat(7,1fr)] overflow-y-auto">
        <div className="relative" style={{ height: GRID_HEIGHT }}>
          {HOURS.map((hour) => (
            <div
              key={hour}
              className="absolute inset-x-0 border-b border-border px-1 text-right font-sans text-[10px] text-muted-foreground"
              style={{ top: hour * PIXELS_PER_HOUR, height: PIXELS_PER_HOUR }}
            >
              {hourLabel(hour)}
            </div>
          ))}
        </div>

        {days.map((day) => {
          const dayStart = startOfDay(day);
          const dayEvents = events.filter((event) => isSameDay(new Date(event.start), day));
          const positioned = layoutDayEvents(dayEvents, dayStart);

          return (
            <div
              key={day.toISOString()}
              data-testid="day-column"
              data-date={format(day, "yyyy-MM-dd")}
              className="relative border-r border-border"
              style={{ height: GRID_HEIGHT }}
            >
              {HOURS.map((hour) => (
                <div
                  key={hour}
                  className={cn("absolute inset-x-0 border-b border-border", hour === 0 && "border-t")}
                  style={{ top: hour * PIXELS_PER_HOUR, height: PIXELS_PER_HOUR }}
                />
              ))}
              {positioned.map(({ event, top, height, left, width }) => (
                <button
                  key={event.id}
                  type="button"
                  onClick={() => onSelectEvent(event)}
                  className="absolute overflow-hidden rounded bg-primary/10 px-1.5 py-0.5 text-left font-sans text-xs text-foreground hover:bg-primary/20"
                  style={{ top, height, left, width }}
                  title={event.summary}
                >
                  {event.summary}
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
