"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getClient, patchClient, createInvite, type ClientDetailOut, type HealthMetric } from "@/lib/api/clients";
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { listClientCheckIns, requestCheckIn, type CheckInOut } from "@/lib/api/checkIns";
import { listClientMessages, sendClientMessage, messageAttachmentUrl, type MessageOut } from "@/lib/api/messages";
import { AuthedImage } from "@/components/authed-image";
import { listClientMealLogs, reactToMealLog, mealLogPhotoUrl, type MealLogOut } from "@/lib/api/mealLogs";
import { groupMealLogsByDay, formatDayHeading } from "@/components/meal-logs/groupByDay";
import { MealCard } from "@/components/meal-logs/MealCard";

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
  saveError,
}: {
  demographics: Record<string, string>;
  onSave: (data: Record<string, string>) => void;
  saving: boolean;
  saveError?: string | null;
}) {
  const [form, setForm] = useState<Record<string, string>>(demographics);

  const field = (key: string, label: string, type: "text" | "date" | "select" | "textarea" = "text", options?: string[]) => (
    <div key={key} className="space-y-2">
      <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">{label}</label>
      {type === "textarea" ? (
        <textarea
          className="w-full rounded-md border border-border bg-background/80 px-3 py-2 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary resize-none"
          rows={3}
          value={form[key] ?? ""}
          onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
        />
      ) : type === "select" ? (
        <select
          className="w-full rounded-md border border-border bg-background/80 px-3 py-2 font-sans text-sm text-foreground outline-none"
          value={form[key] ?? ""}
          onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
        >
          <option value="">— select —</option>
          {options!.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input
          type={type}
          className="w-full rounded-md border border-border bg-background/80 px-3 py-2 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
          value={form[key] ?? ""}
          onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
        />
      )}
    </div>
  );

  return (
    <div className="space-y-5">
      {field("dob", "Date of birth", "date")}
      {field("gender", "Gender", "select", ["Female", "Male", "Non-binary", "Prefer not to say"])}
      {field("city", "City / location")}
      {field("occupation", "Occupation")}
      {field("medical_conditions", "Medical conditions", "textarea")}
      {field("allergies", "Allergies", "textarea")}
      {field("current_medications", "Current medications", "textarea")}
      {field("emergency_contact", "Emergency contact")}
      {saveError && (
        <p className="text-sm text-error">{saveError}</p>
      )}
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
  const [activeTab, setActiveTab] = useState("summary");
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
  const [demoSaveError, setDemoSaveError] = useState<string | null>(null);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteCopied, setInviteCopied] = useState(false);

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

  async function handleInvite() {
    setInviteLoading(true);
    setInviteError(null);
    setInviteCopied(false);
    try {
      const result = await createInvite(clientId);
      setInviteUrl(result.invite_url);
    } catch {
      setInviteError("Could not create invite link. Please try again.");
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleCopyInvite() {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setInviteCopied(true);
    } catch {
      setInviteError("Could not copy link. Please copy it manually.");
    }
  }

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
    setDemoSaveError(null);
    setDemoSaving(true);
    try {
      const updated = await patchClient(clientId, { demographics: data });
      setClient(prev => prev ? { ...prev, demographics: updated.demographics } : prev);
    } catch (e) {
      console.error("Failed to save demographics", e);
      setDemoSaveError("Failed to save — please try again.");
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
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-8">
            <TabsList variant="line">
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="chat">Chat</TabsTrigger>
            </TabsList>
            <TabsContent value="summary" className="space-y-8">
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
                  <SheetContent side="right" className="w-[420px] overflow-y-auto bg-section-fill-03">
                    <SheetHeader className="px-5 pt-5 pb-4">
                      <SheetTitle className="font-heading text-xl font-bold">Client profile</SheetTitle>
                    </SheetHeader>
                    <div className="px-5 pb-8">
                      <DemographicsForm
                        demographics={client!.demographics ?? {}}
                        onSave={handleDemoSave}
                        saving={demoSaving}
                        saveError={demoSaveError}
                      />
                    </div>
                  </SheetContent>
                </Sheet>
              </div>
            </div>

            {/* ── GOAL + HEALTH METRICS ROW — 30/70 ── */}
            <div className="flex gap-4">
              {/* Goal card — 30% */}
              <section className="w-[40%] shrink-0 rounded-2xl border border-border bg-section-fill-03 p-6">
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

                <div className="space-y-2 border-t border-border pt-4">
                  <button
                    type="button"
                    disabled={inviteLoading}
                    onClick={handleInvite}
                    className={cn(
                      buttonVariants({ variant: "accent", size: "sm" }),
                      "disabled:opacity-50",
                    )}
                  >
                    {inviteLoading ? "Generating…" : "Invite to portal"}
                  </button>
                  {inviteError && (
                    <p className="font-sans text-xs text-destructive">{inviteError}</p>
                  )}
                  {inviteUrl && (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <input
                          readOnly
                          value={inviteUrl}
                          onFocus={(e) => e.currentTarget.select()}
                          className="w-full rounded-md border border-border bg-background/80 px-3 py-1.5 font-sans text-xs text-foreground outline-none"
                        />
                        <button
                          type="button"
                          onClick={handleCopyInvite}
                          className="font-sans text-xs text-primary underline-offset-4 hover:underline whitespace-nowrap"
                        >
                          {inviteCopied ? "Copied!" : "Copy"}
                        </button>
                      </div>
                      <p className="font-sans text-xs text-muted-foreground">
                        Share this link with the client to complete their first sign-in.
                      </p>
                    </div>
                  )}
                </div>
              </section>
            </div>
            </TabsContent>
            <TabsContent value="chat">
              <ChatTab clientId={clientId} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}

function ChatTab({ clientId }: { clientId: string }) {
  const [subTab, setSubTab] = useState("text");
  const [checkIns, setCheckIns] = useState<CheckInOut[] | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    listClientCheckIns(clientId).then((data) => setCheckIns(data.items)).catch(() => setCheckIns([]));
  }, [clientId]);

  const pending = checkIns?.find((c) => c.requested_at && c.payload === null) ?? null;

  async function handleRequest() {
    setRequesting(true);
    setRequestError(null);
    try {
      const created = await requestCheckIn(clientId);
      setCheckIns((prev) => [created, ...(prev ?? [])]);
    } catch {
      setRequestError("A check-in is already pending, or the request failed.");
    } finally {
      setRequesting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Tabs value={subTab} onValueChange={setSubTab}>
        <TabsList variant="line">
          <TabsTrigger value="text">Text</TabsTrigger>
          <TabsTrigger value="checkins">Check-ins</TabsTrigger>
          <TabsTrigger value="meals">Logged Meals</TabsTrigger>
        </TabsList>
        <TabsContent value="text">
          <TextView clientId={clientId} />
        </TabsContent>
        <TabsContent value="meals">
          <LoggedMealsView clientId={clientId} />
        </TabsContent>
        <TabsContent value="checkins">
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="font-heading text-xl font-bold text-foreground">Check-ins</h2>
              <button
                onClick={handleRequest}
                disabled={requesting || pending !== null}
                className="rounded-md border border-border px-3 py-1.5 font-sans text-xs font-bold uppercase tracking-widest text-foreground disabled:opacity-50"
              >
                {pending ? "Awaiting answer" : requesting ? "Requesting…" : "Request check-in"}
              </button>
            </div>

            {requestError && <p className="font-sans text-sm text-destructive">{requestError}</p>}

            {checkIns === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}

            {checkIns !== null && checkIns.filter((c) => c.payload !== null).length === 0 && (
              <p className="font-sans text-sm italic text-muted-foreground">No check-ins yet.</p>
            )}

            {checkIns !== null && (
              <ul className="space-y-3">
                {checkIns
                  .filter((c) => c.payload !== null)
                  .map((c) => (
                    <li key={c.id} className="rounded-md border border-border p-4 font-sans text-sm">
                      <p className="mb-1 text-xs text-muted-foreground">
                        {new Date(c.created_at).toLocaleDateString()}
                      </p>
                      <pre className="whitespace-pre-wrap font-sans text-sm">
                        {JSON.stringify(c.payload, null, 2)}
                      </pre>
                    </li>
                  ))}
              </ul>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export function LoggedMealsView({ clientId }: { clientId: string }) {
  const [mealLogs, setMealLogs] = useState<MealLogOut[] | null>(null);
  const [reacting, setReacting] = useState<string | null>(null); // meal log id currently being reacted to
  const [reactError, setReactError] = useState<string | null>(null);

  useEffect(() => {
    listClientMealLogs(clientId).then((data) => setMealLogs(data.items)).catch(() => setMealLogs([]));
  }, [clientId]);

  async function handleReact(mealLogId: string, reaction: "happy" | "neutral" | "sad") {
    setReacting(mealLogId);
    setReactError(null);
    try {
      const updated = await reactToMealLog(clientId, mealLogId, reaction);
      setMealLogs((prev) => prev?.map((m) => (m.id === mealLogId ? updated : m)) ?? null);
    } catch {
      setReactError("Reaction failed to save. Please try again.");
    } finally {
      setReacting(null);
    }
  }

  if (mealLogs === null) return <p className="font-sans text-sm text-muted-foreground">Loading…</p>;
  if (mealLogs.length === 0) return <p className="font-sans text-sm italic text-muted-foreground">No meals logged yet.</p>;

  const groups = groupMealLogsByDay(mealLogs);

  return (
    <div className="space-y-8">
      {reactError && <p className="font-sans text-sm text-destructive">{reactError}</p>}

      {groups.map(({ day, entries }) => (
        <div key={day} className="space-y-3">
          <h3 className="font-heading text-sm font-bold text-foreground">
            {formatDayHeading(day)}
          </h3>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {entries.map((meal) => (
              <MealCard key={meal.id} meal={meal} photoUrl={mealLogPhotoUrl(clientId, meal.id)} showReaction>
                <div className="flex gap-1">
                  {(["happy", "neutral", "sad"] as const).map((r) => (
                    <button
                      key={r}
                      onClick={() => handleReact(meal.id, r)}
                      disabled={reacting === meal.id}
                      className={`rounded px-1.5 py-0.5 text-sm ${meal.hc_reaction === r ? "bg-primary/20" : ""}`}
                    >
                      {{ happy: "😊", neutral: "😐", sad: "😞" }[r]}
                    </button>
                  ))}
                </div>
              </MealCard>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function TextView({ clientId }: { clientId: string }) {
  const [messages, setMessages] = useState<MessageOut[] | null>(null);
  const [body, setBody] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    listClientMessages(clientId).then((data) => setMessages(data.items.slice().reverse())).catch(() => setMessages([]));
  }, [clientId]);

  async function handleSend() {
    if (!body.trim()) return;
    setSending(true);
    setSendError(null);
    try {
      const sent = await sendClientMessage(clientId, { body, attachment: attachment ?? undefined });
      setMessages((prev) => [...(prev ?? []), sent]);
      setBody("");
      setAttachment(null);
    } catch {
      setSendError("Message failed to send. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="max-h-96 space-y-3 overflow-y-auto">
        {messages === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}
        {messages !== null && messages.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">No messages yet.</p>
        )}
        {messages?.map((m) => (
          <div
            key={m.id}
            className={`max-w-[75%] rounded-md border p-3 font-sans text-sm ${
              m.direction === "coach" ? "ml-auto border-primary/30 bg-primary/5" : "border-border"
            }`}
          >
            <p>{m.body}</p>
            {m.has_attachment && (
              <AuthedImage
                url={messageAttachmentUrl(clientId, m.id)}
                alt={m.attachment_original_filename ?? "attachment"}
                className="mt-2 max-h-48 rounded"
              />
            )}
            <p className="mt-1 text-xs text-muted-foreground">{new Date(m.sent_at).toLocaleString()}</p>
          </div>
        ))}
      </div>

      {sendError && <p className="font-sans text-sm text-destructive">{sendError}</p>}

      <div className="flex gap-2">
        <input
          type="text" value={body} onChange={(e) => setBody(e.target.value)}
          placeholder="Type a message…"
          className="flex-1 rounded-md border border-border px-3 py-2 font-sans text-sm"
        />
        <input
          type="file" accept="image/jpeg,image/png,image/webp,image/heic"
          onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
          className="w-40 font-sans text-xs"
        />
        <Button onClick={handleSend} disabled={sending || !body.trim()}>
          {sending ? "Sending…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
