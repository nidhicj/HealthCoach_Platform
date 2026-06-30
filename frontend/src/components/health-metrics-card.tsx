"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { patchClient } from "@/lib/api/clients";
import type { HealthMetric } from "@/lib/api/clients";

interface HealthMetricsCardProps {
  clientId: string;
  metrics: HealthMetric[];
  onSave: (metrics: HealthMetric[]) => void;
}

const VISIBLE_COUNT = 3;

function OverflowPanel({ metrics, onClose }: { metrics: HealthMetric[]; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function handleScroll() { onClose(); }
    function handleKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    document.addEventListener("mousedown", handle);
    document.addEventListener("scroll", handleScroll, true);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handle);
      document.removeEventListener("scroll", handleScroll, true);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute left-0 right-0 top-full z-50 mt-1 rounded-xl border border-border bg-section-fill-01 p-4 shadow-lg"
    >
      <div className="grid grid-cols-3 gap-2 mb-2">
        <span className="font-sans text-[10px] uppercase tracking-wider text-muted-foreground">Metric</span>
        <span className="font-sans text-[10px] uppercase tracking-wider text-muted-foreground">Current</span>
        <span className="font-sans text-[10px] uppercase tracking-wider text-muted-foreground">Target</span>
      </div>
      <div className="space-y-1.5">
        {metrics.map(m => (
          <div key={m.id} className="grid grid-cols-3 gap-2">
            <span className="font-sans text-sm text-foreground truncate">{m.name}</span>
            <span className="font-sans text-sm font-medium text-foreground">{m.value} {m.unit}</span>
            <span className="font-sans text-sm text-muted-foreground">
              {m.target ? `${m.target} ${m.unit}` : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function HealthMetricsCard({ clientId, metrics: initialMetrics, onSave }: HealthMetricsCardProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<HealthMetric[]>(initialMetrics);
  const [showAll, setShowAll] = useState(false);
  const closePanel = useCallback(() => setShowAll(false), []);

  const displayCount = metrics.filter(m => m.display_on_card).length;

  function addMetric() {
    setMetrics(prev => [
      ...prev,
      { id: crypto.randomUUID(), name: "", value: "", unit: "", target: "", display_on_card: false },
    ]);
  }

  function removeMetric(id: string) {
    setMetrics(prev => prev.filter(m => m.id !== id));
  }

  function updateMetric(id: string, patch: Partial<HealthMetric>) {
    setMetrics(prev => prev.map(m => m.id === id ? { ...m, ...patch } : m));
  }

  async function handleSave() {
    setSaveError(null);
    setSaving(true);
    try {
      await patchClient(clientId, { health_metrics: metrics });
      onSave(metrics);
      setEditing(false);
    } catch (e) {
      console.error("Failed to save health metrics", e);
      setSaveError("Failed to save — please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Health Metrics
        </h2>
        {editing ? (
          <div className="flex flex-col gap-1">
            {saveError && (
              <p className="text-sm text-error mt-2">{saveError}</p>
            )}
            <div className="flex gap-2">
              <button
                onClick={() => { setMetrics(initialMetrics); setEditing(false); setSaveError(null); }}
                className="rounded-md border border-border px-3 py-1 font-sans text-xs text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                disabled={saving}
                onClick={handleSave}
                className="rounded-md bg-primary px-3 py-1 font-sans text-xs font-bold text-primary-foreground disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => { setShowAll(false); setEditing(true); }}
            className="rounded-md border border-border px-3 py-1 font-sans text-xs text-muted-foreground hover:text-foreground"
          >
            Edit
          </button>
        )}
      </div>

      {metrics.length === 0 && !editing ? (
        <p className="font-heading italic text-muted-foreground text-sm">
          No metrics yet. Click Edit to add.
        </p>
      ) : editing ? (
        <div className="space-y-2">
          {metrics.map(m => (
            <div key={m.id} className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-1.5 items-center">
              <input
                placeholder="Name"
                value={m.name}
                onChange={e => updateMetric(m.id, { name: e.target.value })}
                className="rounded-md border border-border bg-background px-2 py-1 font-sans text-sm outline-none focus:ring-1 focus:ring-primary"
              />
              <input
                placeholder="Current"
                value={m.value}
                onChange={e => updateMetric(m.id, { value: e.target.value })}
                className="w-[72px] rounded-md border border-border bg-background px-2 py-1 font-sans text-sm outline-none focus:ring-1 focus:ring-primary"
              />
              <input
                placeholder="Target"
                value={m.target ?? ""}
                onChange={e => updateMetric(m.id, { target: e.target.value })}
                className="w-[72px] rounded-md border border-border bg-background px-2 py-1 font-sans text-sm outline-none focus:ring-1 focus:ring-primary"
              />
              <input
                placeholder="Unit"
                value={m.unit}
                onChange={e => updateMetric(m.id, { unit: e.target.value })}
                className="w-14 rounded-md border border-border bg-background px-2 py-1 font-sans text-sm outline-none focus:ring-1 focus:ring-primary"
              />
              <label className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
                <input
                  type="checkbox"
                  checked={m.display_on_card}
                  disabled={!m.display_on_card && displayCount >= 3}
                  onChange={e => updateMetric(m.id, { display_on_card: e.target.checked })}
                />
                Card
              </label>
              <button
                onClick={() => removeMetric(m.id)}
                className="text-muted-foreground hover:text-destructive text-sm"
                aria-label="Remove metric"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="relative">
          {/* Column headers */}
          <div className="grid grid-cols-3 gap-2 mb-1">
            <span className="font-sans text-[10px] uppercase tracking-wider text-muted-foreground">Metric</span>
            <span className="font-sans text-[10px] uppercase tracking-wider text-muted-foreground">Current</span>
            <span className="font-sans text-[10px] uppercase tracking-wider text-muted-foreground">Target</span>
          </div>
          {/* Metric rows — show only first VISIBLE_COUNT */}
          <div className="space-y-1.5">
            {metrics.slice(0, VISIBLE_COUNT).map(m => (
              <div key={m.id} className="grid grid-cols-3 gap-2">
                <span className="font-sans text-sm text-foreground truncate">{m.name}</span>
                <span className="font-sans text-sm font-medium text-foreground">{m.value} {m.unit}</span>
                <span className="font-sans text-sm text-muted-foreground">
                  {m.target ? `${m.target} ${m.unit}` : "—"}
                </span>
              </div>
            ))}
          </div>
          {/* +N more button */}
          {metrics.length > VISIBLE_COUNT && (
            <button
              onClick={() => setShowAll(v => !v)}
              className="mt-2 font-sans text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              {showAll ? "▲ Show less" : `▼ Show all ${metrics.length}`}
            </button>
          )}
          {/* Overflow popover */}
          {showAll && (
            <OverflowPanel metrics={metrics} onClose={closePanel} />
          )}
        </div>
      )}

      {editing && (
        <button
          onClick={addMetric}
          className="mt-3 flex items-center gap-1 font-sans text-xs text-muted-foreground hover:text-foreground"
        >
          + Add metric
        </button>
      )}
    </div>
  );
}
