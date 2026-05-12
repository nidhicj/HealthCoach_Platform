"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  getClientDietChart,
  generateDietChart,
  patchDietChart,
  listTemplates,
  type DietChartOut,
} from "@/lib/api/dietCharts";
import { getClient, type ClientDetailOut } from "@/lib/api/clients";

type GridCell = { food: string; timing: string };
type Grid = Record<string, Record<string, GridCell>>;

const DAYS = [
  "Monday", "Tuesday", "Wednesday", "Thursday",
  "Friday", "Saturday", "Sunday",
];

function getGrid(chart: DietChartOut): Grid {
  return ((chart.parameters as Record<string, unknown>)?.grid as Grid) ?? {};
}

function getMealSlots(chart: DietChartOut): string[] {
  return (
    (chart.parameters as Record<string, unknown>)?.meal_slots as string[]
  ) ?? [];
}

export default function DietChartEditorPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const [client, setClient] = useState<ClientDetailOut | null>(null);
  const [chart, setChart] = useState<DietChartOut | null | undefined>(undefined);
  const [templates, setTemplates] = useState<DietChartOut[]>([]);
  const [editedGrid, setEditedGrid] = useState<Grid>({});
  const [mealSlots, setMealSlots] = useState<string[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [modifications, setModifications] = useState("");
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fallbackWarning, setFallbackWarning] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [newSlotName, setNewSlotName] = useState("");
  const [editingSlot, setEditingSlot] = useState<string | null>(null);
  const [editingSlotValue, setEditingSlotValue] = useState("");

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      getClient(clientId),
      getClientDietChart(clientId),
      listTemplates(),
    ])
      .then(([c, dc, tpls]) => {
        setClient(c);
        setChart(dc);
        setTemplates(tpls);
        if (tpls.length > 0) setSelectedTemplateId(tpls[0].id);
        if (dc) {
          setEditedGrid(getGrid(dc));
          setMealSlots(getMealSlots(dc));
        }
      })
      .catch(() => setLoadError(true));
  }, [clientId]);

  async function handleGenerate() {
    if (!selectedTemplateId) return;
    setGenerating(true);
    setFallbackWarning(false);
    try {
      const { chart: newChart, generation_status } = await generateDietChart(
        clientId,
        { template_id: selectedTemplateId, modifications: modifications || undefined },
      );
      setChart(newChart);
      setEditedGrid(getGrid(newChart));
      setMealSlots(getMealSlots(newChart));
      if (generation_status === "fallback") setFallbackWarning(true);
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    if (!chart) return;
    setSaving(true);
    setSaveError(null);
    try {
      const params = {
        ...(chart.parameters as Record<string, unknown>),
        meal_slots: mealSlots,
        grid: editedGrid,
      };
      const updated = await patchDietChart(clientId, params);
      setChart(updated);
      setEditedGrid(getGrid(updated));
      setMealSlots(getMealSlots(updated));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function updateCell(
    day: string,
    slot: string,
    field: "food" | "timing",
    value: string,
  ) {
    setEditedGrid((prev) => ({
      ...prev,
      [day]: {
        ...(prev[day] ?? {}),
        [slot]: {
          ...(prev[day]?.[slot] ?? { food: "", timing: "" }),
          [field]: value,
        },
      },
    }));
  }

  function renameSlot(oldName: string, newName: string) {
    const trimmed = newName.trim();
    if (!trimmed || trimmed === oldName || mealSlots.includes(trimmed)) {
      setEditingSlot(null);
      return;
    }
    setMealSlots((prev) => prev.map((s) => (s === oldName ? trimmed : s)));
    setEditedGrid((prev) => {
      const next: Grid = {};
      for (const day of DAYS) {
        next[day] = {};
        for (const slot of mealSlots) {
          const key = slot === oldName ? trimmed : slot;
          next[day][key] = prev[day]?.[slot] ?? { food: "", timing: "" };
        }
      }
      return next;
    });
    setEditingSlot(null);
  }

  function moveSlot(index: number, direction: "left" | "right") {
    const swapIdx = direction === "left" ? index - 1 : index + 1;
    if (swapIdx < 0 || swapIdx >= mealSlots.length) return;
    setMealSlots((prev) => {
      const next = [...prev];
      [next[index], next[swapIdx]] = [next[swapIdx], next[index]];
      return next;
    });
  }

  function addMealSlot() {
    const name = newSlotName.trim();
    if (!name || mealSlots.includes(name)) return;
    setMealSlots((prev) => [...prev, name]);
    setEditedGrid((prev) => {
      const next = { ...prev };
      for (const day of DAYS) {
        next[day] = { ...(next[day] ?? {}), [name]: { food: "", timing: "" } };
      }
      return next;
    });
    setNewSlotName("");
  }

  const loading = chart === undefined && !loadError;

  return (
    <div className="space-y-8">
      <Link
        href={`/clients/${clientId}`}
        className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        ← {client?.full_name ?? "Client"}
      </Link>

      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Nutrition
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Diet chart
        </h1>
      </div>

      {loadError && (
        <p className="font-sans text-sm text-destructive">
          Could not load diet chart.
        </p>
      )}

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {!loading && !loadError && (
        <>
          <section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
            <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
              {chart ? "Regenerate chart" : "Generate chart"}
            </h2>
            <Separator />
            {templates.length === 0 ? (
              <p className="font-sans text-sm text-muted-foreground">
                No templates in library.{" "}
                <Link
                  href="/settings/diet-chart-templates"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  Upload one →
                </Link>
              </p>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      Template
                    </label>
                    <select
                      value={selectedTemplateId}
                      onChange={(e) => setSelectedTemplateId(e.target.value)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 font-sans text-sm text-foreground"
                    >
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                      Modifications / additions (optional)
                    </label>
                    <input
                      type="text"
                      value={modifications}
                      onChange={(e) => setModifications(e.target.value)}
                      placeholder="e.g. replace Saturday dinner with paneer, add evening snack Mon–Wed…"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground"
                    />
                  </div>
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={generating || !selectedTemplateId}
                  className="rounded-lg bg-primary px-4 py-2 font-sans text-xs font-bold uppercase tracking-widest text-primary-foreground disabled:opacity-50"
                >
                  {generating ? "Generating…" : chart ? "Regenerate" : "Generate"}
                </button>
              </div>
            )}
          </section>

          {fallbackWarning && (
            <div className="rounded-lg border border-amber-400 bg-amber-50 px-4 py-3">
              <p className="font-sans text-sm text-amber-800">
                AI generation failed — showing the template grid unchanged. Edit cells below and save.
              </p>
            </div>
          )}

          {chart && (
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                  7-day grid
                </h2>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-lg bg-primary px-4 py-2 font-sans text-xs font-bold uppercase tracking-widest text-primary-foreground disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save chart"}
                </button>
              </div>
              {saveError && (
                <p className="font-sans text-xs text-destructive">{saveError}</p>
              )}
              <div className="overflow-x-auto rounded-2xl border border-border">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted">
                      <th className="w-24 p-3 text-left font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                        Day
                      </th>
                      {mealSlots.map((slot, idx) => (
                        <th
                          key={slot}
                          className="min-w-[160px] border-l border-border p-3 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground"
                        >
                          {editingSlot === slot ? (
                            <input
                              autoFocus
                              value={editingSlotValue}
                              onChange={(e) => setEditingSlotValue(e.target.value)}
                              onBlur={() => renameSlot(slot, editingSlotValue)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") renameSlot(slot, editingSlotValue);
                                if (e.key === "Escape") setEditingSlot(null);
                              }}
                              className="w-full rounded border border-primary bg-background px-1 py-0.5 font-sans text-xs font-bold uppercase tracking-widest text-foreground focus:outline-none"
                            />
                          ) : (
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => { setEditingSlot(slot); setEditingSlotValue(slot); }}
                                className="flex-1 text-left hover:text-primary"
                                title="Click to rename"
                              >
                                {slot}
                              </button>
                              <button
                                type="button"
                                onClick={() => moveSlot(idx, "left")}
                                disabled={idx === 0}
                                className="shrink-0 text-muted-foreground hover:text-foreground disabled:opacity-20"
                                title="Move left"
                              >
                                ←
                              </button>
                              <button
                                type="button"
                                onClick={() => moveSlot(idx, "right")}
                                disabled={idx === mealSlots.length - 1}
                                className="shrink-0 text-muted-foreground hover:text-foreground disabled:opacity-20"
                                title="Move right"
                              >
                                →
                              </button>
                            </div>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {DAYS.map((day) => (
                      <tr
                        key={day}
                        className="border-b border-border align-top last:border-0"
                      >
                        <td className="p-3">
                          <span className="font-heading text-sm font-bold text-foreground">
                            {day.slice(0, 3)}
                          </span>
                        </td>
                        {mealSlots.map((slot) => {
                          const cell = editedGrid[day]?.[slot] ?? {
                            food: "",
                            timing: "",
                          };
                          return (
                            <td key={slot} className="border-l border-border p-2">
                              <div className="space-y-1">
                                <input
                                  type="text"
                                  value={cell.food}
                                  onChange={(e) =>
                                    updateCell(day, slot, "food", e.target.value)
                                  }
                                  placeholder="Food"
                                  className="w-full rounded border border-border bg-background px-2 py-1 font-sans text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                                <input
                                  type="text"
                                  value={cell.timing}
                                  onChange={(e) =>
                                    updateCell(day, slot, "timing", e.target.value)
                                  }
                                  placeholder="Timing"
                                  className="w-full rounded border border-border bg-background px-2 py-1 font-sans text-xs text-muted-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={newSlotName}
                  onChange={(e) => setNewSlotName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addMealSlot()}
                  placeholder="New meal slot name…"
                  className="w-56 rounded-lg border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground"
                />
                <button
                  onClick={addMealSlot}
                  disabled={!newSlotName.trim()}
                  className="font-sans text-xs text-primary underline-offset-4 hover:underline disabled:opacity-40"
                >
                  + Add column
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
