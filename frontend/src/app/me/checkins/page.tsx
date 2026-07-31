"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { listMyCheckIns, submitMyCheckIn } from "@/lib/api/me";
import type { CheckInOut } from "@/lib/api/checkIns";

const METRICS = [
  "Energy levels", "Sleep quality", "Diet adherence", "Stress levels", "Hydration",
  "Physical activity", "Mood", "Digestion", "Motivation", "Weight trend",
] as const;

export default function CheckInsPage() {
  const [checkIns, setCheckIns] = useState<CheckInOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    listMyCheckIns()
      .then((data) => setCheckIns(data.items))
      .catch(() => setLoadError(true));
  }, []);

  const pending = checkIns?.find((c) => c.requested_at && c.payload === null) ?? null;

  function toggleMetric(metric: string) {
    setSelected((prev) => {
      if (prev.includes(metric)) return prev.filter((m) => m !== metric);
      if (prev.length >= 3) return prev;
      return [...prev, metric];
    });
  }

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const metrics = Object.fromEntries(selected.map((m) => [m, ratings[m] ?? 5]));
      const updated = await submitMyCheckIn({ metrics, note: note || undefined });
      setCheckIns((prev) => [updated, ...(prev ?? []).filter((c) => c.id !== updated.id)]);
      setSelected([]);
      setRatings({});
      setNote("");
      setShowForm(false);
    } catch {
      setSubmitError("Couldn't submit your check-in — please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const answeredCheckIns = (checkIns ?? []).filter((c) => c.payload !== null);

  return (
    <div className="space-y-8">
      <h1 className="font-heading text-3xl font-black text-foreground">Check-ins</h1>

      {(pending || showForm) && (
        <div className="space-y-4 rounded-md border p-4">
          <p className="font-sans text-sm text-foreground">
            {pending
              ? "Your coach asked for a check-in. Pick 3 things to rate:"
              : "Pick 3 things to rate:"}
          </p>
          <div className="flex flex-wrap gap-2">
            {METRICS.map((m) => (
              <button
                key={m}
                onClick={() => toggleMetric(m)}
                className={`rounded-full border px-3 py-1 font-sans text-xs ${
                  selected.includes(m) ? "border-primary bg-primary text-primary-foreground" : "border-border text-foreground"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          {selected.map((m) => (
            <div key={m} className="flex items-center gap-3">
              <span className="w-40 font-sans text-sm">{m}</span>
              <input
                type="range" min={1} max={10}
                value={ratings[m] ?? 5}
                onChange={(e) => setRatings((prev) => ({ ...prev, [m]: Number(e.target.value) }))}
              />
              <span className="font-sans text-sm">{ratings[m] ?? 5}/10</span>
            </div>
          ))}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Anything else? (optional)"
            className="w-full rounded-md border border-border p-2 font-sans text-sm"
          />
          <div className="flex items-center gap-3">
            <Button onClick={handleSubmit} disabled={selected.length !== 3 || submitting}>
              {submitting ? "Submitting…" : "Submit check-in"}
            </Button>
            {submitError && (
              <p className="font-sans text-sm text-destructive">{submitError}</p>
            )}
          </div>
        </div>
      )}

      {!pending && !showForm && checkIns !== null && (
        <div className="space-y-3">
          <p className="font-sans text-sm text-muted-foreground">
            Nothing to answer right now.
          </p>
          <Button variant="outline" onClick={() => setShowForm(true)}>
            Check in now
          </Button>
        </div>
      )}

      {loadError && (
        <p className="font-sans text-sm text-destructive">
          Couldn&apos;t load your check-ins — try refreshing.
        </p>
      )}

      <div className="space-y-3">
        <h2 className="font-heading text-lg font-bold text-foreground">Past check-ins</h2>
        {answeredCheckIns.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">None yet.</p>
        )}
        {answeredCheckIns.map((c) => (
          <div key={c.id} className="rounded-md border border-border p-4 font-sans text-sm">
            <p className="mb-1 text-xs text-muted-foreground">{new Date(c.created_at).toLocaleDateString()}</p>
            <pre className="whitespace-pre-wrap">{JSON.stringify(c.payload, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
