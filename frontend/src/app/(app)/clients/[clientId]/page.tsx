"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getClient, getClientAst, type ClientDetailOut, type AstOut } from "@/lib/api/clients";
import { listSessions, type SessionOut } from "@/lib/api/sessions";
import { listActionItems, patchActionItem, type ActionItemOut } from "@/lib/api/actionItems";

function isOverdue(dateStr: string | null): boolean {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date(new Date().toDateString());
}

const JOURNEY_STAGE_LABEL: Record<string, string> = {
  onboarding: "Onboarding",
  active: "Active",
  plateau: "Plateau",
  off_track: "Off track",
  completed: "Completed",
};

const FLAG_LABEL: Record<string, string> = {
  missed_action_item: "Missed action item",
  no_recent_checkin: "No recent check-in",
  manual_sentiment_flag: "Sentiment flag",
};

export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [client, setClient] = useState<ClientDetailOut | null>(null);
  const [ast, setAst] = useState<AstOut | null>(null);
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());
  const [closedItems, setClosedItems] = useState<ActionItemOut[] | null>(null);
  const [reopenedIds, setReopenedIds] = useState<Set<string>>(new Set());
  const [showClosed, setShowClosed] = useState(false);

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      getClient(clientId),
      getClientAst(clientId),
      listSessions({ client_id: clientId, limit: 20 }),
      listActionItems({ client_id: clientId, status: "completed", limit: 50 }),
    ])
      .then(([c, a, s, closed]) => {
        setClient(c);
        setAst(a);
        setSessions(s.items);
        setClosedItems(closed.items);
      })
      .catch(() => setLoadError(true));
  }, [clientId]);

  async function toggleItem(id: string, markComplete: boolean) {
    if (markComplete) {
      setCompletedIds((prev) => new Set(prev).add(id));
      setReopenedIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
      try {
        await patchActionItem(id, { status: "completed" });
      } catch {
        setCompletedIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
      }
    } else {
      setReopenedIds((prev) => new Set(prev).add(id));
      setCompletedIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
      try {
        await patchActionItem(id, { status: "open" });
      } catch {
        setReopenedIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
      }
    }
  }

  const loading = !loadError && client === null;

  const displayOpen = [
    ...(ast?.open_items ?? []).filter((i) => !completedIds.has(i.id)),
    ...(closedItems ?? []).filter((i) => reopenedIds.has(i.id)),
  ];

  const displayClosed = [
    ...(closedItems ?? []).filter((i) => !reopenedIds.has(i.id)),
    ...(ast?.open_items ?? []).filter((i) => completedIds.has(i.id)),
  ];

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <Link
        href="/clients"
        className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        ← Clients
      </Link>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-5 w-32" />
        </div>
      ) : loadError ? (
        <p className="font-sans text-sm text-destructive">
          Could not load client.
        </p>
      ) : (
        <>
          {/* Client name header */}
          <div className="space-y-2">
            <h1 className="font-heading text-4xl font-black text-foreground">
              {client!.full_name}
            </h1>
            {/* ONE Marigold accent line — brand rule: divider beneath the headline */}
            <div className="h-0.5 w-14 bg-accent" aria-hidden />
            <div className="flex items-center gap-3">
              <Badge variant="secondary">
                {JOURNEY_STAGE_LABEL[client!.journey_stage] ?? client!.journey_stage}
              </Badge>
              {client!.code && (
                <span className="font-sans text-xs text-muted-foreground">
                  {client!.code}
                </span>
              )}
            </div>
          </div>

          {/* Two-column layout */}
          <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
            {/* Left: meta + session history */}
            <div className="space-y-8">
              {/* Client meta */}
              <section className="space-y-3 rounded-2xl border border-border bg-muted p-6">
                <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                  Details
                </h2>
                <Separator />
                <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 font-sans text-sm">
                  {client!.email && (
                    <>
                      <dt className="text-muted-foreground">Email</dt>
                      <dd className="text-foreground">{client!.email}</dd>
                    </>
                  )}
                  {client!.phone && (
                    <>
                      <dt className="text-muted-foreground">Phone</dt>
                      <dd className="text-foreground">{client!.phone}</dd>
                    </>
                  )}
                  {client!.course_goal && (
                    <>
                      <dt className="text-muted-foreground">Goal</dt>
                      <dd className="text-foreground">{client!.course_goal}</dd>
                    </>
                  )}
                </dl>
              </section>

              {/* Open action items */}
              <section className="space-y-4 rounded-2xl border border-border bg-section-fill-02 p-6">
                <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                  Open action items
                </h2>
                <Separator />
                {ast === null ? (
                  <div className="space-y-2">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ) : displayOpen.length === 0 ? (
                  <p className="py-2 font-heading text-lg font-black text-muted-foreground">
                    All clear. <em>Nothing pending.</em>
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {displayOpen.map((item) => (
                      <li key={item.id} className="flex items-start gap-3 py-3">
                        <input
                          type="checkbox"
                          checked={false}
                          onChange={() => toggleItem(item.id, true)}
                          className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                        />
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
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* Closed action items (collapsible) */}
              <section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
                <button
                  type="button"
                  onClick={() => setShowClosed((v) => !v)}
                  className="flex w-full items-center justify-between"
                >
                  <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                    Closed action items
                    {displayClosed.length > 0 && (
                      <span className="ml-2 font-normal normal-case tracking-normal text-muted-foreground">
                        ({displayClosed.length})
                      </span>
                    )}
                  </h2>
                  <span className="font-sans text-xs text-muted-foreground">
                    {showClosed ? "▲" : "▼"}
                  </span>
                </button>
                {showClosed && (
                  <>
                    <Separator />
                    {closedItems === null ? (
                      <div className="space-y-2">
                        <Skeleton className="h-10 w-full" />
                      </div>
                    ) : displayClosed.length === 0 ? (
                      <p className="py-2 font-sans text-sm italic text-muted-foreground">
                        No completed items yet.
                      </p>
                    ) : (
                      <ul className="divide-y divide-border">
                        {displayClosed.map((item) => (
                          <li key={item.id} className="flex items-start gap-3 py-3 opacity-60">
                            <input
                              type="checkbox"
                              checked={true}
                              onChange={() => toggleItem(item.id, false)}
                              className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                            />
                            <div className="space-y-0.5">
                              <p className="font-sans text-sm text-foreground line-through">
                                {item.description}
                              </p>
                              {item.due_date && (
                                <p className="font-sans text-xs text-muted-foreground">
                                  Due {new Date(item.due_date).toLocaleDateString("en-IN")}
                                </p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </section>

              {/* Session history */}
              <section className="space-y-4 rounded-2xl border border-border bg-section-fill-02 p-6">
                <div className="flex items-center justify-between">
                  <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                    Sessions
                  </h2>
                  <Link
                    href={`/clients/${clientId}/sessions/new`}
                    className={cn(buttonVariants({ variant: "default", size: "sm" }))}
                  >
                    New session
                  </Link>
                </div>
                <Separator />
                {sessions === null ? (
                  <div className="space-y-2">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                ) : sessions.length === 0 ? (
                  <p className="font-heading text-lg font-black text-muted-foreground py-2">
                    No sessions yet. <em>Start one.</em>
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {sessions.map((sess) => (
                      <li key={sess.id}>
                        <Link
                          href={`/clients/${clientId}/sessions/${sess.id}`}
                          className="flex items-center justify-between py-3 transition-colors duration-150 hover:text-primary"
                        >
                          <div>
                            <span className="font-heading text-base font-bold text-foreground">
                              Session {sess.session_number}
                            </span>
                            <span className="ml-3 font-sans text-sm text-muted-foreground">
                              {new Date(sess.scheduled_at).toLocaleDateString("en-IN", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })}
                            </span>
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
            </div>

            {/* Right: AST card */}
            <aside className="space-y-4">
              <Card className="bg-muted">
                <CardHeader>
                  <CardTitle className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                    Client status
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-5">
                  {ast === null ? (
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-4 w-3/4" />
                    </div>
                  ) : (
                    <>
                      {/* Triage flags */}
                      {ast.triage_flags.length > 0 && (
                        <div className="space-y-2">
                          <p className="font-sans text-xs font-bold uppercase tracking-widest text-destructive">
                            Flags
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {ast.triage_flags.map((flag) => (
                              <Badge key={flag} variant="destructive">
                                {FLAG_LABEL[flag] ?? flag}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Status summary */}
                      <div className="space-y-1.5">
                        <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                          Recent check-ins
                        </p>
                        <p className="font-sans text-sm text-foreground whitespace-pre-line">
                          {ast.status_summary}
                        </p>
                      </div>

                      {/* Open action items count */}
                      <div className="space-y-1.5">
                        <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                          Open items
                        </p>
                        <p className="font-heading text-2xl font-black text-foreground">
                          {ast.open_items.length}
                        </p>
                      </div>

                      {/* Missed action items count */}
                      {ast.missed_items.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                            Missed
                          </p>
                          <p className="font-heading text-2xl font-black text-destructive">
                            {ast.missed_items.length}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
