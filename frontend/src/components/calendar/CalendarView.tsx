"use client";

import { useEffect, useState } from "react";
import { addDays, endOfDay, startOfDay, startOfMonth, startOfWeek } from "date-fns";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getCalendarStatus,
  getCalendarConnectUrl,
  listCalendarEvents,
  type CalendarStatus,
  type CalendarEvent,
} from "@/lib/api/calendar";
import { MonthGrid } from "@/components/calendar/MonthGrid";
import { WeekGrid } from "@/components/calendar/WeekGrid";
import { CreateEventForm } from "@/components/calendar/CreateEventForm";

// 6 weeks x 7 days — mirrors MonthGrid's own fixed-height grid, so the events
// we fetch cover exactly the leading/trailing days it actually renders.
const MONTH_GRID_CELLS = 42;

type ViewMode = "month" | "week";

function visibleRange(viewMode: ViewMode, anchor: Date): { start: Date; end: Date } {
  if (viewMode === "week") {
    const start = startOfWeek(anchor);
    return { start, end: addDays(start, 6) };
  }
  const start = startOfWeek(startOfMonth(anchor));
  return { start, end: addDays(start, MONTH_GRID_CELLS - 1) };
}

// ── connect / reconnect prompt (shared by the not-connected and needs_reauth states) ──

function ConnectPrompt({
  message,
  buttonLabel,
  onConnect,
  connecting,
  connectError,
}: {
  message: string | null;
  buttonLabel: string;
  onConnect: () => void;
  connecting: boolean;
  connectError: string | null;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-border p-6 text-center">
      {message && <p className="font-sans text-sm text-muted-foreground">{message}</p>}
      <Button onClick={onConnect} disabled={connecting}>
        {connecting ? "Redirecting…" : buttonLabel}
      </Button>
      {connectError && <p className="font-sans text-xs text-destructive">{connectError}</p>}
    </div>
  );
}

export function CalendarView({ onSelectEvent }: { onSelectEvent: (event: CalendarEvent) => void }) {
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [statusError, setStatusError] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [anchor] = useState(() => new Date());
  const [events, setEvents] = useState<CalendarEvent[] | null>(null);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCalendarStatus()
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch(() => {
        if (!cancelled) setStatusError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!status || !status.connected || status.needs_reauth) return;
    let cancelled = false;
    setEventsLoading(true);
    setEventsError(null);
    const { start, end } = visibleRange(viewMode, anchor);
    listCalendarEvents(startOfDay(start).toISOString(), endOfDay(end).toISOString())
      .then((evts) => {
        if (!cancelled) setEvents(evts);
      })
      .catch(() => {
        if (!cancelled) setEventsError("Could not load calendar events. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setEventsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [status, viewMode, anchor]);

  async function handleConnect() {
    setConnecting(true);
    setConnectError(null);
    try {
      const url = await getCalendarConnectUrl();
      window.location.href = url;
    } catch (err) {
      setConnectError(err instanceof Error ? err.message : "Could not start Google Calendar connection.");
    } finally {
      setConnecting(false);
    }
  }

  if (statusError) {
    return (
      <p className="font-sans text-sm text-destructive">
        Could not load Google Calendar status. Please try again.
      </p>
    );
  }

  if (status === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!status.connected) {
    return (
      <ConnectPrompt
        message="Connect your Google Calendar to see and schedule sessions here."
        buttonLabel="Connect Google Calendar"
        onConnect={handleConnect}
        connecting={connecting}
        connectError={connectError}
      />
    );
  }

  if (status.needs_reauth) {
    return (
      <ConnectPrompt
        message="Your Google Calendar connection needs to be renewed."
        buttonLabel="Reconnect Google Calendar"
        onConnect={handleConnect}
        connecting={connecting}
        connectError={connectError}
      />
    );
  }

  // connected && !needs_reauth
  if (events === null && eventsLoading && !eventsError) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const weekStart = startOfWeek(anchor);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as ViewMode)}>
          <TabsList variant="line">
            <TabsTrigger value="month">Month</TabsTrigger>
            <TabsTrigger value="week">Week</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button size="sm" onClick={() => setShowCreateForm(true)}>
          + Create event
        </Button>
      </div>

      {showCreateForm && (
        <div className="rounded-lg border border-dashed border-border p-4">
          <CreateEventForm
            onCreated={(event) => {
              setShowCreateForm(false);
              onSelectEvent(event);
            }}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      )}

      {eventsError ? (
        <p className="font-sans text-sm text-destructive">{eventsError}</p>
      ) : eventsLoading || events === null ? (
        <Skeleton className="h-64 w-full" />
      ) : viewMode === "month" ? (
        <MonthGrid month={anchor} events={events} onSelectEvent={onSelectEvent} />
      ) : (
        <WeekGrid weekStart={weekStart} events={events} onSelectEvent={onSelectEvent} />
      )}
    </div>
  );
}
