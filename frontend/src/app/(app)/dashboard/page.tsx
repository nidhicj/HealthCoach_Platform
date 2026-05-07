"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listSessions, type SessionOut } from "@/lib/api/sessions";
import { listClients, type ClientOut } from "@/lib/api/clients";
import { listActionItems, type ActionItemOut } from "@/lib/api/actionItems";

function isToday(iso: string): boolean {
  return new Date(iso).toDateString() === new Date().toDateString();
}

function isOverdue(dateStr: string | null): boolean {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date(new Date().toDateString());
}

export default function DashboardPage() {
  const [todaySessions, setTodaySessions] = useState<SessionOut[] | null>(null);
  const [clients, setClients] = useState<ClientOut[] | null>(null);
  const [actionItems, setActionItems] = useState<ActionItemOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    Promise.all([
      listSessions({ limit: 50 }),
      listClients({ limit: 5 }),
      listActionItems({ status: "open", limit: 20 }),
    ])
      .then(([s, c, a]) => {
        setTodaySessions(s.items.filter((x) => isToday(x.scheduled_at)));
        setClients(c.items);
        const sorted = [...a.items].sort((x, y) => {
          return (isOverdue(x.due_date) ? 0 : 1) - (isOverdue(y.due_date) ? 0 : 1);
        });
        setActionItems(sorted);
      })
      .catch(() => setLoadError(true));
  }, []);

  const loading = !loadError && todaySessions === null;

  const todayEmpty = !loading && !loadError && todaySessions?.length === 0;
  // Only one Marigold per screen — goes to Today empty-state CTA when sessions empty
  const showMarigold = todayEmpty;

  return (
    <div className="space-y-10">
      {/* Page header */}
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          {new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Dashboard
        </h1>
      </div>

      {/* Section 1 — Today */}
      <section className="space-y-4">
        <h2 className="font-heading text-xl font-bold text-foreground">Today</h2>
        <Separator />
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : loadError ? (
          <p className="font-sans text-sm text-destructive">
            Could not load sessions.
          </p>
        ) : todaySessions!.length === 0 ? (
          <div className="flex flex-col items-start gap-5 py-4">
            <p className="font-heading text-2xl font-black text-muted-foreground">
              No sessions today. <em>Quiet morning.</em>
            </p>
            <Link
              href="/clients"
              className={cn(buttonVariants({ variant: showMarigold ? "accent" : "default" }))}
            >
              New session
            </Link>
          </div>
        ) : (
          <ul className="space-y-2">
            {todaySessions!.map((sess) => (
              <li key={sess.id}>
                <Link
                  href={`/clients/${sess.client_id}/sessions/${sess.id}`}
                  className="flex items-center justify-between rounded-lg border border-border px-4 py-3 transition-colors duration-150 hover:bg-muted"
                >
                  <div>
                    <p className="font-heading text-base font-bold text-foreground">
                      Session {sess.session_number}
                    </p>
                    <p className="font-sans text-sm text-muted-foreground">
                      {new Date(sess.scheduled_at).toLocaleTimeString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                  {sess.ended_at ? (
                    <Badge variant="secondary">Ended</Badge>
                  ) : sess.started_at ? (
                    <Badge>In progress</Badge>
                  ) : (
                    <Badge variant="outline">Scheduled</Badge>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Section 2 — Recent clients */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-xl font-bold text-foreground">
            Recent clients
          </h2>
          <Link
            href="/clients"
            className="font-sans text-xs text-primary underline-offset-4 hover:underline"
          >
            All clients →
          </Link>
        </div>
        <Separator />
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : clients?.length === 0 ? (
          <p className="py-2 font-heading text-xl font-black text-muted-foreground">
            No clients yet. <em>Start by adding one.</em>
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {clients?.map((client) => (
              <li key={client.id}>
                <Link
                  href={`/clients/${client.id}`}
                  className="flex items-center justify-between py-3 transition-colors duration-150 hover:text-primary"
                >
                  <p className="font-heading text-base font-bold text-foreground">
                    {client.full_name}
                  </p>
                  <span className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                    {client.journey_stage.replace(/_/g, " ")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Section 3 — Pending action items */}
      <section className="space-y-4">
        <h2 className="font-heading text-xl font-bold text-foreground">
          Pending action items
        </h2>
        <Separator />
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : actionItems?.length === 0 ? (
          <p className="py-2 font-heading text-xl font-black text-muted-foreground">
            All clear. <em>Nothing pending.</em>
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {actionItems?.map((item) => (
              <li key={item.id} className="flex items-start justify-between py-3">
                <div className="space-y-0.5">
                  <p className="font-sans text-sm text-foreground">
                    {item.description}
                  </p>
                  {item.due_date && (
                    <p
                      className={cn(
                        "font-sans text-xs",
                        isOverdue(item.due_date)
                          ? "font-bold text-destructive"
                          : "text-muted-foreground",
                      )}
                    >
                      Due {new Date(item.due_date).toLocaleDateString("en-IN")}
                      {isOverdue(item.due_date) && " · Overdue"}
                    </p>
                  )}
                </div>
                <Link href={`/clients/${item.client_id}`}>
                  <Badge variant="outline" className="shrink-0">
                    View client
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
