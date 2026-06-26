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
import { getClientDietChart, type DietChartOut } from "@/lib/api/dietCharts";
import {
  listSupplements,
  createSupplement,
  patchSupplement,
  deleteSupplement,
  type SupplementOut,
} from "@/lib/api/supplements";

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

const SUPPLEMENT_CATALOG = [
  "Vitamin D3", "Vitamin B12", "Vitamin C", "Omega-3 / Fish Oil",
  "Magnesium", "Iron", "Zinc", "Calcium", "Ashwagandha",
  "Curcumin / Turmeric", "Probiotics", "Whey Protein", "Plant Protein",
  "Multivitamin", "Collagen", "Biotin", "CoQ10", "Melatonin",
];

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
  const [dietChart, setDietChart] = useState<DietChartOut | null | undefined>(undefined);
  const [supplements, setSupplements] = useState<SupplementOut[] | null>(null);
  const [suppLoadError, setSuppLoadError] = useState(false);
  const [showSuppForm, setShowSuppForm] = useState(false);
  const [editingSuppId, setEditingSuppId] = useState<string | null>(null);
  const [suppForm, setSuppForm] = useState({
    name: "",
    dosage: "",
    duration_days: "",
    recommended_at: new Date().toISOString().slice(0, 10),
    notes: "",
  });
  const [suppSaving, setSuppSaving] = useState(false);
  const [suppFormError, setSuppFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      getClient(clientId),
      getClientAst(clientId),
      listSessions({ client_id: clientId, limit: 20 }),
      listActionItems({ client_id: clientId, status: "completed", limit: 50 }),
      getClientDietChart(clientId),
      listSupplements(clientId),
    ])
      .then(([c, a, s, closed, dc, supps]) => {
        setClient(c);
        setAst(a);
        setSessions(s.items);
        setClosedItems(closed.items);
        setDietChart(dc);
        setSupplements(supps);
      })
      .catch(() => {
        setLoadError(true);
        setSuppLoadError(true);
      });
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

  function openAddForm() {
    setEditingSuppId(null);
    setSuppForm({
      name: "",
      dosage: "",
      duration_days: "",
      recommended_at: new Date().toISOString().slice(0, 10),
      notes: "",
    });
    setSuppFormError(null);
    setShowSuppForm(true);
  }

  function openEditForm(s: SupplementOut) {
    setEditingSuppId(s.id);
    setSuppForm({
      name: s.name,
      dosage: s.dosage ?? "",
      duration_days: s.duration_days?.toString() ?? "",
      recommended_at: s.recommended_at.slice(0, 10),
      notes: s.notes ?? "",
    });
    setSuppFormError(null);
    setShowSuppForm(true);
  }

  function closeSuppForm() {
    setShowSuppForm(false);
    setEditingSuppId(null);
    setSuppFormError(null);
  }

  async function handleSuppSave() {
    if (!suppForm.name.trim()) {
      setSuppFormError("Supplement name is required.");
      return;
    }
    setSuppSaving(true);
    setSuppFormError(null);
    const payload = {
      name: suppForm.name.trim(),
      dosage: suppForm.dosage.trim() || null,
      duration_days: suppForm.duration_days ? parseInt(suppForm.duration_days, 10) : null,
      recommended_at: suppForm.recommended_at
        ? new Date(suppForm.recommended_at).toISOString()
        : undefined,
      notes: suppForm.notes.trim() || null,
    };
    try {
      if (editingSuppId) {
        const updated = await patchSupplement(clientId, editingSuppId, payload);
        setSupplements((prev) =>
          prev ? prev.map((s) => (s.id === editingSuppId ? updated : s)) : prev
        );
      } else {
        const created = await createSupplement(clientId, payload);
        setSupplements((prev) => (prev ? [created, ...prev] : [created]));
      }
      closeSuppForm();
    } catch {
      setSuppFormError("Could not save. Please try again.");
    } finally {
      setSuppSaving(false);
    }
  }

  async function handleSuppDelete(id: string) {
    if (!confirm("Remove this supplement entry?")) return;
    try {
      await deleteSupplement(clientId, id);
      setSupplements((prev) => (prev ? prev.filter((s) => s.id !== id) : prev));
      closeSuppForm();
    } catch {
      setSuppFormError("Could not remove. Please try again.");
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

              {/* Supplement recommendations */}
              <section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
                <div className="flex items-center justify-between">
                  <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                    Supplement recommendations
                  </h2>
                  {!showSuppForm && (
                    <button
                      type="button"
                      onClick={openAddForm}
                      className="font-sans text-xs text-primary underline-offset-4 hover:underline"
                    >
                      + Add
                    </button>
                  )}
                </div>
                <Separator />

                {/* Inline form */}
                {showSuppForm && (
                  <div className="space-y-3 rounded-xl border border-border bg-background p-4">
                    <div className="space-y-1">
                      <label className="font-sans text-xs text-muted-foreground">
                        Name <span className="text-destructive">*</span>
                      </label>
                      <input
                        list="supplement-catalog"
                        value={suppForm.name}
                        onChange={(e) => setSuppForm((f) => ({ ...f, name: e.target.value }))}
                        placeholder="Type or select a supplement"
                        className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                      />
                      <datalist id="supplement-catalog">
                        {SUPPLEMENT_CATALOG.map((s) => (
                          <option key={s} value={s} />
                        ))}
                      </datalist>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className="font-sans text-xs text-muted-foreground">Dosage</label>
                        <input
                          value={suppForm.dosage}
                          onChange={(e) => setSuppForm((f) => ({ ...f, dosage: e.target.value }))}
                          placeholder="e.g. 2000 IU daily"
                          className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="font-sans text-xs text-muted-foreground">Duration (days)</label>
                        <input
                          type="number"
                          min={1}
                          value={suppForm.duration_days}
                          onChange={(e) => setSuppForm((f) => ({ ...f, duration_days: e.target.value }))}
                          placeholder="e.g. 30"
                          className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="font-sans text-xs text-muted-foreground">Date recommended</label>
                      <input
                        type="date"
                        value={suppForm.recommended_at}
                        onChange={(e) => setSuppForm((f) => ({ ...f, recommended_at: e.target.value }))}
                        className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="font-sans text-xs text-muted-foreground">Notes (optional)</label>
                      <textarea
                        value={suppForm.notes}
                        onChange={(e) => setSuppForm((f) => ({ ...f, notes: e.target.value }))}
                        placeholder="Reason or context"
                        rows={2}
                        className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                      />
                    </div>

                    {suppFormError && (
                      <p className="font-sans text-xs text-destructive">{suppFormError}</p>
                    )}

                    <div className="flex items-center justify-between gap-2">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={handleSuppSave}
                          disabled={suppSaving}
                          className="rounded-md bg-primary px-3 py-1.5 font-sans text-xs font-bold text-primary-foreground disabled:opacity-50"
                        >
                          {suppSaving ? "Saving…" : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={closeSuppForm}
                          className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
                        >
                          Cancel
                        </button>
                      </div>
                      {editingSuppId && (
                        <button
                          type="button"
                          onClick={() => handleSuppDelete(editingSuppId)}
                          className="font-sans text-xs text-destructive underline-offset-4 hover:underline"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* List */}
                {suppLoadError ? (
                  <p className="font-sans text-sm text-destructive">Could not load supplements.</p>
                ) : supplements === null ? (
                  <div className="space-y-2">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ) : supplements.length === 0 && !showSuppForm ? (
                  <p className="font-sans text-sm italic text-muted-foreground">
                    No supplements logged yet.
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {supplements.map((s) => (
                      <li key={s.id} className="py-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-0.5">
                            <p className="font-sans text-sm text-foreground">{s.name}</p>
                            <p className="font-sans text-xs text-muted-foreground">
                              {[
                                s.dosage,
                                s.duration_days ? `${s.duration_days} days` : null,
                                new Date(s.recommended_at).toLocaleDateString("en-IN", {
                                  day: "numeric",
                                  month: "short",
                                  year: "numeric",
                                }),
                              ]
                                .filter(Boolean)
                                .join(" · ")}
                            </p>
                            {s.notes && (
                              <p className="font-sans text-xs italic text-muted-foreground">{s.notes}</p>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => openEditForm(s)}
                            className="shrink-0 font-sans text-xs text-primary underline-offset-4 hover:underline"
                          >
                            Edit
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
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

            {/* Right: AST card + diet chart */}
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

              {/* Diet chart preview */}
              <Card className="bg-muted">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                      Diet chart
                    </CardTitle>
                    <Link
                      href={`/clients/${clientId}/diet-chart`}
                      className="font-sans text-xs text-primary underline-offset-4 hover:underline"
                    >
                      {dietChart ? "Edit →" : "Generate →"}
                    </Link>
                  </div>
                </CardHeader>
                <CardContent>
                  {dietChart === undefined ? (
                    <Skeleton className="h-20 w-full" />
                  ) : dietChart === null ? (
                    <p className="font-sans text-sm italic text-muted-foreground">
                      No diet chart yet.
                    </p>
                  ) : (
                    (() => {
                      const params = dietChart.parameters as Record<string, unknown>;
                      const grid = (params?.grid ?? {}) as Record<
                        string,
                        Record<string, { food: string; timing: string }>
                      >;
                      const slots = (params?.meal_slots ?? []) as string[];
                      return (
                        <div className="overflow-x-auto">
                          <table className="w-full border-collapse text-xs">
                            <thead>
                              <tr className="border-b border-border">
                                <th className="py-1.5 pr-2 text-left font-sans font-bold text-muted-foreground">
                                  Day
                                </th>
                                {slots.slice(0, 2).map((s) => (
                                  <th
                                    key={s}
                                    className="border-l border-border px-2 py-1.5 text-left font-sans font-bold text-muted-foreground"
                                  >
                                    {s}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {["Monday", "Tuesday"].map((day) => (
                                <tr key={day} className="border-b border-border last:border-0">
                                  <td className="py-1.5 pr-2 font-heading font-bold text-foreground">
                                    {day.slice(0, 3)}
                                  </td>
                                  {slots.slice(0, 2).map((s) => (
                                    <td
                                      key={s}
                                      className="border-l border-border px-2 py-1.5 font-sans text-foreground"
                                    >
                                      {grid[day]?.[s]?.food ?? "—"}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      );
                    })()
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
