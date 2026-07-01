"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listClients, type ClientOut } from "@/lib/api/clients";
import { listSessions, type SessionOut } from "@/lib/api/sessions";
import { listActionItems, type ActionItemOut } from "@/lib/api/actionItems";
import { ClientCard } from "@/components/client-card";
import {
  buildLastSessionMap,
  buildFlaggedSet,
  findMilestone,
  formatRelativeDate,
} from "@/lib/rosterUtils";

const toIST = (d: Date) =>
  d.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata" });

function isToday(iso: string): boolean {
  return toIST(new Date(iso)) === toIST(new Date());
}

function sessionDayLabel(iso: string): string {
  const sessionDate = toIST(new Date(iso));
  if (sessionDate === toIST(new Date())) return "";
  if (sessionDate === toIST(new Date(Date.now() + 86_400_000))) return "Tomorrow";
  return new Date(iso).toLocaleDateString("en-IN", {
    weekday: "short",
    timeZone: "Asia/Kolkata",
  });
}

export default function DashboardPage() {
  const [clients, setClients] = useState<ClientOut[] | null>(null);
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [missedItems, setMissedItems] = useState<ActionItemOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [pastExpanded, setPastExpanded] = useState(false);

  useEffect(() => {
    Promise.all([
      listClients({ limit: 100 }),
      listSessions({ limit: 100 }),
      listActionItems({ status: "missed", limit: 100 }),
    ])
      .then(([c, s, m]) => {
        setClients(c.items);
        setSessions(s.items);
        setMissedItems(m.items);
      })
      .catch(() => setLoadError(true));
  }, []);

  const loading = !loadError && clients === null;

  const clientMap = new Map((clients ?? []).map((c) => [c.id, c]));
  const lastSessionMap = buildLastSessionMap(sessions ?? []);
  const flaggedSet = buildFlaggedSet(missedItems ?? []);
  const milestone = findMilestone(sessions ?? [], clients ?? []);

  const todaySessions = (sessions ?? []).filter((s) => isToday(s.scheduled_at));
  const upcomingThisWeek = (sessions ?? [])
    .filter((s) => {
      const d = new Date(s.scheduled_at);
      return d > new Date() && d.getTime() - Date.now() <= 7 * 24 * 60 * 60 * 1000;
    })
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime());
  const bannerSessions = todaySessions.length > 0 ? todaySessions : upcomingThisWeek;
  const bannerLabel = todaySessions.length > 0 ? "Today" : "Upcoming";
  const activeClients = (clients ?? []).filter((c) => c.journey_stage !== "completed");
  const pastClients = (clients ?? []).filter((c) => c.journey_stage === "completed");
  const flaggedCount = activeClients.filter((c) => flaggedSet.has(c.id)).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
            Your Practice
          </p>
          <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
            Dashboard
          </h1>
          <p className="mt-1 font-sans text-sm text-muted-foreground">
            Your whole practice, in one place.
          </p>
        </div>
        <Link href="/clients/new" className={cn(buttonVariants({ variant: "accent" }), "shrink-0")}>
          + New client
        </Link>
      </div>

      {/* Sessions banner */}
      <section className="rounded-2xl border border-border bg-muted px-5 py-3">
        {loading ? (
          <Skeleton className="h-5 w-56" />
        ) : bannerSessions.length === 0 ? (
          <p className="font-heading text-base font-black text-muted-foreground">
            No sessions today.{" "}
            <em>Quiet morning.</em>{" "}
            <Link
              href="/action-items"
              className="font-sans text-xs font-normal text-primary underline-offset-4 hover:underline"
            >
              Review follow-ups →
            </Link>
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
              {bannerLabel}
            </span>
            {bannerSessions.map((s) => {
              const dayLabel = sessionDayLabel(s.scheduled_at);
              return (
                <Link
                  key={s.id}
                  href={`/clients/${s.client_id}/sessions/${s.id}`}
                  className="rounded-full border border-border bg-background px-3 py-1 font-sans text-sm text-foreground transition-colors duration-150 hover:border-primary hover:text-primary"
                >
                  {clientMap.get(s.client_id)?.full_name ?? `Session ${s.session_number}`}
                  {dayLabel && ` · ${dayLabel}`}
                  {" · "}
                  {new Date(s.scheduled_at).toLocaleTimeString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZone: "Asia/Kolkata",
                  })}
                </Link>
              );
            })}
          </div>
        )}
      </section>

      {/* Milestone / flag signal */}
      {!loading && (milestone !== null || flaggedCount > 0) && (
        <div
          className={cn(
            "rounded-2xl border px-5 py-4",
            milestone
              ? "border-accent/40 bg-accent/10"
              : "border-warning/40 bg-warning/5",
          )}
        >
          {milestone ? (
            <p className="font-sans text-sm text-foreground">
              🎉{" "}
              <strong className="font-heading">{milestone.clientName}</strong>{" "}
              just completed their{" "}
              <strong>{milestone.sessionNumber}th</strong> session with you.
            </p>
          ) : (
            <p className="font-sans text-sm text-foreground">
              🚩{" "}
              <strong>{flaggedCount}</strong>{" "}
              {flaggedCount === 1 ? "client has" : "clients have"} missed action
              items — worth a check-in before their next session.
            </p>
          )}
        </div>
      )}

      {/* Client grid */}
      <section className="space-y-4">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Your Clients
        </h2>

        {loadError && (
          <p className="font-sans text-sm text-destructive">
            Could not load clients.
          </p>
        )}

        {loading ? (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
        ) : activeClients.length === 0 ? (
          <p className="font-heading text-xl font-black text-muted-foreground py-4">
            No active clients yet. <em>Add your first one.</em>
          </p>
        ) : (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {activeClients.map((client) => (
              <ClientCard
                key={client.id}
                client={client}
                relativeDate={formatRelativeDate(lastSessionMap.get(client.id) ?? null)}
                hasFlags={flaggedSet.has(client.id)}
                metrics={client.health_metrics.filter(m => m.display_on_card).map(({ id, name, value, unit, target }) => ({ id, name, value, unit, target }))}
              />
            ))}
          </div>
        )}

        {/* Past clients collapsible */}
        {!loading && pastClients.length > 0 && (
          <div className="pt-2 border-t border-border">
            <button
              type="button"
              onClick={() => setPastExpanded((v) => !v)}
              className="flex items-center gap-2 py-3 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground transition-colors duration-150 hover:text-foreground"
            >
              Past clients ({pastClients.length})
              <span className="text-xs">{pastExpanded ? "▲" : "▼"}</span>
            </button>
            {pastExpanded && (
              <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 mt-2">
                {pastClients.map((client) => (
                  <ClientCard
                    key={client.id}
                    client={client}
                    relativeDate={formatRelativeDate(lastSessionMap.get(client.id) ?? null)}
                    hasFlags={false}
                    dim
                    metrics={client.health_metrics.filter(m => m.display_on_card).map(({ id, name, value, unit, target }) => ({ id, name, value, unit, target }))}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
