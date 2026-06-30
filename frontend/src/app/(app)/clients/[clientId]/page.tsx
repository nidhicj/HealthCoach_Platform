"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getClient, patchClient, type ClientDetailOut, type HealthMetric } from "@/lib/api/clients";
import { listSessions, type SessionOut } from "@/lib/api/sessions";
import { listActionItems, patchActionItem, type ActionItemOut } from "@/lib/api/actionItems";
import {
  getClientDietChart,
  generateDietChart,
  listTemplates,
  type DietChartOut,
} from "@/lib/api/dietCharts";
import {
  listSupplements,
  createSupplement,
  patchSupplement,
  deleteSupplement,
  type SupplementOut,
} from "@/lib/api/supplements";
import { Settings } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { HealthMetricsCard } from "@/components/health-metrics-card";

function isOverdue(dateStr: string | null): boolean {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date(new Date().toDateString());
}

const JOURNEY_STAGE_LABEL: Record<string, string> = {
  onboarding: "Onboarding",
  active: "Active",
  plateau: "Plateau",
  off_track: "Off Track",
  completed: "Completed",
};

const SUPPLEMENT_CATALOG = [
  "Vitamin D3", "Vitamin B12", "Vitamin C", "Omega-3 / Fish Oil",
  "Magnesium", "Iron", "Zinc", "Calcium", "Ashwagandha",
  "Curcumin / Turmeric", "Probiotics", "Whey Protein", "Plant Protein",
  "Multivitamin", "Collagen", "Biotin", "CoQ10", "Melatonin",
];

function DemographicsForm({
  demographics,
  onSave,
  saving,
}: {
  demographics: Record<string, string>;
  onSave: (data: Record<string, string>) => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<Record<string, string>>(demographics);

  const field = (key: string, label: string, type: "text" | "date" | "select" | "textarea" = "text", options?: string[]) => (
    <div key={key} className="space-y-1">
      <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">{label}</label>
      {type === "textarea" ? (
        <textarea
          className="w-full rounded-md border border-border bg-muted px-3 py-2 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary resize-none"
          rows={3}
          value={form[key] ?? ""}
          onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
        />
      ) : type === "select" ? (
        <select
          className="w-full rounded-md border border-border bg-muted px-3 py-2 font-sans text-sm text-foreground outline-none"
          value={form[key] ?? ""}
          onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
        >
          <option value="">— select —</option>
          {options!.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input
          type={type}
          className="w-full rounded-md border border-border bg-muted px-3 py-2 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
          value={form[key] ?? ""}
          onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
        />
      )}
    </div>
  );

  return (
    <div className="mt-6 space-y-4">
      {field("dob", "Date of birth", "date")}
      {field("gender", "Gender", "select", ["Female", "Male", "Non-binary", "Prefer not to say"])}
      {field("city", "City / location")}
      {field("occupation", "Occupation")}
      {field("medical_conditions", "Medical conditions", "textarea")}
      {field("allergies", "Allergies", "textarea")}
      {field("current_medications", "Current medications", "textarea")}
      {field("emergency_contact", "Emergency contact")}
      <button
        disabled={saving}
        onClick={() => onSave(form)}
        className="mt-2 w-full rounded-md bg-primary px-4 py-2 font-sans text-sm font-bold text-primary-foreground disabled:opacity-60"
      >
        {saving ? "Saving…" : "Save profile"}
      </button>
    </div>
  );
}

export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [client, setClient] = useState<ClientDetailOut | null>(null);
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());
  const [closedItems, setClosedItems] = useState<ActionItemOut[] | null>(null);
  const [openItems, setOpenItems] = useState<ActionItemOut[] | null>(null);
  const [reopenedIds, setReopenedIds] = useState<Set<string>>(new Set());
  const [dietChart, setDietChart] = useState<DietChartOut | null | undefined>(undefined);
  const [supplements, setSupplements] = useState<SupplementOut[] | null>(null);
  const [openItemsError, setOpenItemsError] = useState(false);
  const [pastSessionsOpen, setPastSessionsOpen] = useState(false);
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
  const [stageSaving, setStageSaving] = useState(false);
  const [suppSaving, setSuppSaving] = useState(false);
  const [suppFormError, setSuppFormError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<DietChartOut[] | null>(null);
  const [showGenerate, setShowGenerate] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [demoSaving, setDemoSaving] = useState(false);

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      getClient(clientId),
      listSessions({ client_id: clientId, limit: 20 }),
      listActionItems({ client_id: clientId, status: "completed", limit: 50 }),
      getClientDietChart(clientId),
    ])
      .then(([c, s, closed, dc]) => {
        setClient(c);
        setSessions(s.items);
        setClosedItems(closed.items);
        setDietChart(dc);
      })
      .catch(() => setLoadError(true));

    listActionItems({ client_id: clientId, status: "open", limit: 50 })
      .then((r) => setOpenItems(r.items))
      .catch(() => setOpenItemsError(true));

    listSupplements(clientId)
      .then(setSupplements)
      .catch(() => setSuppLoadError(true));

    listTemplates()
      .then(setTemplates)
      .catch(() => {}); // non-fatal — generate button just stays disabled
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

  async function handleDemoSave(data: Record<string, string>) {
    setDemoSaving(true);
    try {
      const updated = await patchClient(clientId, { demographics: data });
      setClient(prev => prev ? { ...prev, demographics: updated.demographics } : prev);
    } catch (e) {
      console.error("Failed to save demographics", e);
    } finally {
      setDemoSaving(false);
    }
  }

  const loading = !loadError && client === null;

  const displayOpen = [
    ...(openItems ?? []).filter((i) => !completedIds.has(i.id)),
    ...(closedItems ?? []).filter((i) => reopenedIds.has(i.id)),
  ];

  const displayClosed = [
    ...(closedItems ?? []).filter((i) => !reopenedIds.has(i.id)),
    ...(openItems ?? []).filter((i) => completedIds.has(i.id)),
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
        <p className="font-sans text-sm text-destructive">Could not load client.</p>
      ) : (
        <>
          {/* Client header */}
          <div className="space-y-2">
            <h1 className="font-heading text-4xl font-black text-foreground">
              {client!.full_name}
            </h1>
            <div className="h-0.5 w-14 bg-accent" aria-hidden />
            <div className="flex items-center gap-3">
              <select
                value={client!.journey_stage}
                disabled={stageSaving}
                onChange={async (e) => {
                  const newStage = e.target.value;
                  const prevStage = client!.journey_stage;
                  setClient((prev) => prev ? { ...prev, journey_stage: newStage } : prev);
                  setStageSaving(true);
                  try {
                    const updated = await patchClient(clientId, { journey_stage: newStage });
                    setClient((prev) => prev ? { ...prev, journey_stage: updated.journey_stage } : prev);
                  } catch (err) {
                    console.error(err);
                    setClient((prev) => prev ? { ...prev, journey_stage: prevStage } : prev);
                  } finally {
                    setStageSaving(false);
                  }
                }}
                className="rounded-full border border-border bg-muted px-3 py-1 font-sans text-sm font-medium cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
              >
                {Object.entries(JOURNEY_STAGE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              {stageSaving && (
                <span className="font-sans text-xs text-muted-foreground">Saving…</span>
              )}
              {client!.code && (
                <span className="font-sans text-xs text-muted-foreground">{client!.code}</span>
              )}
              <Sheet>
                <SheetTrigger
                  className="ml-auto rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="Edit client profile"
                >
                  <Settings size={18} />
                </SheetTrigger>
                <SheetContent side="right" className="w-[420px] overflow-y-auto">
                  <SheetHeader>
                    <SheetTitle className="font-heading text-lg">Client profile</SheetTitle>
                  </SheetHeader>
                  <DemographicsForm
                    demographics={client!.demographics ?? {}}
                    onSave={handleDemoSave}
                    saving={demoSaving}
                  />
                </SheetContent>
              </Sheet>
            </div>
          </div>

          {/* ── GOAL + HEALTH METRICS ROW — 30/70 ── */}
          <div className="flex gap-4">
            {/* Goal card — 30% */}
            <section className="w-[30%] shrink-0 rounded-2xl border border-border bg-section-fill-03 p-6">
              <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary mb-3">
                Goal
              </h2>
              <Separator />
              <p className="mt-3 font-heading text-lg font-bold text-foreground">
                {client!.course_goal ?? (
                  <span className="font-sans text-sm font-normal italic text-muted-foreground">
                    Add a goal for this client
                  </span>
                )}
              </p>
            </section>

            {/* Health Metrics card — 70% */}
            <section className="flex-1 rounded-2xl border border-border bg-section-fill-01 p-6">
              <HealthMetricsCard
                clientId={clientId}
                metrics={client!.health_metrics ?? []}
                onSave={(metrics) => setClient(prev => prev ? { ...prev, health_metrics: metrics } : prev)}
              />
            </section>
          </div>

          {/* ── SESSIONS (60%) + SUPPLEMENTS (40%) — bg-B / bg-C ── */}
          <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
            {/* Sessions — bg-B */}
            <section className="space-y-4 rounded-2xl border border-border bg-section-fill-01 p-6">
              <div className="flex items-center justify-between">
                <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                  Sessions
                </h2>
                <Link
                  href={`/clients/${clientId}/sessions/new`}
                  className={cn(buttonVariants({ variant: "accent", size: "sm" }))}
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
                <>
                  <ul className="divide-y divide-border">
                    {sessions.slice(0, 5).map((sess) => (
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
                  {sessions.length > 5 && (
                    <div className="pt-2">
                      <button
                        onClick={() => setPastSessionsOpen((prev) => !prev)}
                        className="flex w-full items-center justify-between text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <span>Past sessions</span>
                        <span>{pastSessionsOpen ? "▲" : "▼"}</span>
                      </button>
                      {pastSessionsOpen && (
                        <ul className="mt-3 divide-y divide-border">
                          {sessions.slice(5).map((sess) => (
                            <li key={sess.id}>
                              <Link
                                href={`/clients/${clientId}/sessions/${sess.id}`}
                                className="flex items-center justify-between py-3 opacity-70 transition-colors duration-150 hover:text-primary hover:opacity-100"
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
                                ) : (
                                  <Badge variant="outline">Scheduled</Badge>
                                )}
                              </Link>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </>
              )}
            </section>

            {/* Supplement Recommendations — bg-C */}
            <section className="space-y-4 rounded-2xl border border-border bg-section-fill-02 p-6">
              <div className="flex items-center justify-between">
                <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                  Supplement Recommendations
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

              {/* Supplement inline form */}
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
                      {SUPPLEMENT_CATALOG.map((s) => <option key={s} value={s} />)}
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

              {/* Supplement list */}
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
                                day: "numeric", month: "short", year: "numeric",
                              }),
                            ].filter(Boolean).join(" · ")}
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
          </div>

          {/* ── DIET CHART — bg-A full width ── */}
          <section className="space-y-4 rounded-2xl border border-border bg-section-fill-03 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-heading text-2xl font-bold text-foreground">Diet chart</h2>
              {!showGenerate && (
                <div className="flex items-center gap-3">
                  {dietChart && (
                    <Link
                      href={`/clients/${clientId}/diet-chart`}
                      className="font-sans text-xs text-primary underline-offset-4 hover:underline"
                    >
                      Edit →
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => { setShowGenerate(true); setGenerateError(null); }}
                    className={cn(
                      buttonVariants({ variant: "accent", size: "sm" }),
                    )}
                  >
                    {dietChart ? "Regenerate" : "Generate chart"}
                  </button>
                </div>
              )}
              {showGenerate && (
                <button
                  type="button"
                  onClick={() => setShowGenerate(false)}
                  className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
                >
                  Cancel
                </button>
              )}
            </div>
            <Separator />
            {showGenerate && (
              <div className="space-y-3 rounded-xl border border-border bg-background p-4">
                <div className="space-y-1">
                  <label className="font-sans text-xs text-muted-foreground">
                    Base this chart on a template
                  </label>
                  <select
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="">Select a template…</option>
                    {(templates ?? []).map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
                {generateError && (
                  <p className="font-sans text-xs text-destructive">{generateError}</p>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={!selectedTemplateId || generating}
                    onClick={async () => {
                      if (!selectedTemplateId) return;
                      setGenerating(true);
                      setGenerateError(null);
                      try {
                        const result = await generateDietChart(clientId, { template_id: selectedTemplateId });
                        setDietChart(result.chart);
                        setShowGenerate(false);
                      } catch {
                        setGenerateError("Generation failed. Please try again.");
                      } finally {
                        setGenerating(false);
                      }
                    }}
                    className={cn(
                      buttonVariants({ variant: "accent", size: "sm" }),
                      "disabled:opacity-50",
                    )}
                  >
                    {generating ? "Generating…" : "Generate →"}
                  </button>
                </div>
                {generating && (
                  <div className="space-y-2 pt-2">
                    <Skeleton className="h-6 w-full" />
                    <Skeleton className="h-6 w-full" />
                    <Skeleton className="h-6 w-5/6" />
                    <Skeleton className="h-6 w-full" />
                  </div>
                )}
              </div>
            )}
            {dietChart === undefined ? (
              <Skeleton className="h-40 w-full" />
            ) : dietChart === null ? (
              <p className="font-sans text-sm italic text-muted-foreground">
                No diet chart yet.
              </p>
            ) : null}
            {!generating && dietChart !== null && dietChart !== undefined && (
              <div className="animate-in fade-in duration-200">
                {(() => {
                  const params = dietChart.parameters as Record<string, unknown>;
                  const grid = (params?.grid ?? {}) as Record<
                    string,
                    Record<string, { food: string; timing: string }>
                  >;
                  const slots = (params?.meal_slots ?? []) as string[];
                  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
                  return (
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="py-2 pr-3 text-left font-sans font-bold text-muted-foreground">
                              Day
                            </th>
                            {slots.map((s) => (
                              <th
                                key={s}
                                className="border-l border-border px-3 py-2 text-left font-sans font-bold text-muted-foreground"
                              >
                                {s}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {days.map((day) => (
                            <tr key={day} className="border-b border-border last:border-0">
                              <td className="py-2 pr-3 font-heading font-bold text-foreground">
                                {day.slice(0, 3)}
                              </td>
                              {slots.map((s) => (
                                <td
                                  key={s}
                                  className="border-l border-border px-3 py-2 font-sans text-foreground"
                                >
                                  <div>{grid[day]?.[s]?.food ?? "—"}</div>
                                  {grid[day]?.[s]?.timing && (
                                    <div className="text-muted-foreground">{grid[day][s].timing}</div>
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                })()}
              </div>
            )}
          </section>

          {/* ── OPEN ACTION ITEMS (50%) + DETAILS (50%) — bg-B / bg-C ── */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Open action items — bg-B */}
            <section className="space-y-4 rounded-2xl border border-border bg-section-fill-01 p-6">
              <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                Open action items
              </h2>
              <Separator />
              {openItemsError ? (
                <p className="text-sm text-destructive">Could not load action items.</p>
              ) : openItems === null ? (
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
                        <p className="font-sans text-sm text-foreground">{item.description}</p>
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

              {/* Closed items collapsible — retained */}
              {displayClosed.length > 0 && (
                <details className="pt-2 border-t border-border">
                  <summary className="cursor-pointer py-2 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground list-none hover:text-foreground transition-colors duration-150">
                    Closed ({displayClosed.length}) ▼
                  </summary>
                  <ul className="mt-2 divide-y divide-border">
                    {displayClosed.map((item) => (
                      <li key={item.id} className="flex items-start gap-3 py-3 opacity-60">
                        <input
                          type="checkbox"
                          checked={true}
                          onChange={() => toggleItem(item.id, false)}
                          className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                        />
                        <p className="font-sans text-sm text-foreground line-through">
                          {item.description}
                        </p>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </section>

            {/* Client details — bg-C */}
            <section className="space-y-4 rounded-2xl border border-border bg-section-fill-02 p-6">
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
                <dt className="text-muted-foreground">Stage</dt>
                <dd className="text-foreground">
                  {JOURNEY_STAGE_LABEL[client!.journey_stage] ?? client!.journey_stage}
                </dd>
                {client!.course_start_date && (
                  <>
                    <dt className="text-muted-foreground">Since</dt>
                    <dd className="text-foreground">
                      {new Date(client!.course_start_date).toLocaleDateString("en-IN", {
                        day: "numeric", month: "short", year: "numeric",
                      })}
                    </dd>
                  </>
                )}
              </dl>
              {client!.demographics?.dob && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Date of birth</span>
                  <span className="font-medium">{client!.demographics.dob}</span>
                </div>
              )}
              {client!.demographics?.gender && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Gender</span>
                  <span className="font-medium">{client!.demographics.gender}</span>
                </div>
              )}
              {client!.demographics?.city && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">City</span>
                  <span className="font-medium">{client!.demographics.city}</span>
                </div>
              )}
              {client!.demographics?.occupation && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Occupation</span>
                  <span className="font-medium">{client!.demographics.occupation}</span>
                </div>
              )}
              {client!.demographics?.medical_conditions && (
                <div className="flex flex-col gap-1 text-sm">
                  <span className="text-muted-foreground">Medical conditions</span>
                  <span className="font-medium">{client!.demographics.medical_conditions}</span>
                </div>
              )}
              {client!.demographics?.allergies && (
                <div className="flex flex-col gap-1 text-sm">
                  <span className="text-muted-foreground">Allergies</span>
                  <span className="font-medium">{client!.demographics.allergies}</span>
                </div>
              )}
              {client!.demographics?.current_medications && (
                <div className="flex flex-col gap-1 text-sm">
                  <span className="text-muted-foreground">Medications</span>
                  <span className="font-medium">{client!.demographics.current_medications}</span>
                </div>
              )}
              {client!.demographics?.emergency_contact && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Emergency contact</span>
                  <span className="font-medium">{client!.demographics.emergency_contact}</span>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
