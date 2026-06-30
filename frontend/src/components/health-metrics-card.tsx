"use client";

import { useState } from "react";
import { patchClient } from "@/lib/api/clients";
import type { HealthMetric } from "@/lib/api/clients";

interface HealthMetricsCardProps {
  clientId: string;
  metrics: HealthMetric[];
  onSave: (metrics: HealthMetric[]) => void;
}

export function HealthMetricsCard({ clientId, metrics: initialMetrics, onSave }: HealthMetricsCardProps) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [metrics, setMetrics] = useState<HealthMetric[]>(initialMetrics);

  const displayCount = metrics.filter(m => m.display_on_card).length;

  function addMetric() {
    setMetrics(prev => [
      ...prev,
      { id: crypto.randomUUID(), name: "", value: "", unit: "", display_on_card: false },
    ]);
  }

  function removeMetric(id: string) {
    setMetrics(prev => prev.filter(m => m.id !== id));
  }

  function updateMetric(id: string, patch: Partial<HealthMetric>) {
    setMetrics(prev => prev.map(m => m.id === id ? { ...m, ...patch } : m));
  }

  async function handleSave() {
    setSaving(true);
    try {
      await patchClient(clientId, { health_metrics: metrics });
      onSave(metrics);
      setEditing(false);
    } catch (e) {
      console.error("Failed to save health metrics", e);
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
          <div className="flex gap-2">
            <button
              onClick={() => { setMetrics(initialMetrics); setEditing(false); }}
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
        ) : (
          <button
            onClick={() => setEditing(true)}
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
      ) : (
        <div className="space-y-2">
          {metrics.map(m => (
            <div key={m.id} className="flex items-center gap-2">
              {editing ? (
                <>
                  <input
                    placeholder="Name"
                    value={m.name}
                    onChange={e => updateMetric(m.id, { name: e.target.value })}
                    className="flex-1 rounded-md border border-border bg-background px-2 py-1 font-sans text-sm outline-none focus:ring-1 focus:ring-primary"
                  />
                  <input
                    placeholder="Value"
                    value={m.value}
                    onChange={e => updateMetric(m.id, { value: e.target.value })}
                    className="w-20 rounded-md border border-border bg-background px-2 py-1 font-sans text-sm outline-none focus:ring-1 focus:ring-primary"
                  />
                  <input
                    placeholder="Unit"
                    value={m.unit}
                    onChange={e => updateMetric(m.id, { unit: e.target.value })}
                    className="w-16 rounded-md border border-border bg-background px-2 py-1 font-sans text-sm outline-none focus:ring-1 focus:ring-primary"
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
                </>
              ) : (
                <span className="text-sm">
                  <span className="text-muted-foreground">{m.name}:</span>{" "}
                  <span className="font-medium text-foreground">{m.value} {m.unit}</span>
                  {m.display_on_card && (
                    <span className="ml-2 text-xs text-primary">★ card</span>
                  )}
                </span>
              )}
            </div>
          ))}
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
