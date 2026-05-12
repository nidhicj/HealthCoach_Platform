"use client";

import { useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  listTemplates,
  uploadTemplate,
  deleteTemplate,
  type DietChartOut,
} from "@/lib/api/dietCharts";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function TemplateGrid({ template }: { template: DietChartOut }) {
  const params = template.parameters as Record<string, unknown>;
  const slots = (params?.meal_slots ?? []) as string[];
  const grid = (params?.grid ?? {}) as Record<
    string,
    Record<string, { food: string; timing: string }>
  >;

  if (slots.length === 0) return null;

  return (
    <div className="overflow-x-auto pt-3">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-border">
            <th className="py-1.5 pr-3 text-left font-sans font-bold text-muted-foreground">
              Day
            </th>
            {slots.map((s) => (
              <th
                key={s}
                className="border-l border-border px-3 py-1.5 text-left font-sans font-bold text-muted-foreground"
              >
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DAYS.map((day) => (
            <tr key={day} className="border-b border-border last:border-0">
              <td className="py-2 pr-3 font-heading font-bold text-foreground">
                {day.slice(0, 3)}
              </td>
              {slots.map((s) => {
                const cell = grid[day]?.[s];
                return (
                  <td key={s} className="border-l border-border px-3 py-2 font-sans text-foreground">
                    <span>{cell?.food ?? "—"}</span>
                    {cell?.timing && (
                      <span className="ml-1.5 text-muted-foreground">{cell.timing}</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DietChartTemplatesPage() {
  const [templates, setTemplates] = useState<DietChartOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setLoadError(true));
  }, []);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const created = await uploadTemplate(file);
      setTemplates((prev) => (prev ? [...prev, created] : [created]));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteTemplate(id);
      setTemplates((prev) => (prev ? prev.filter((t) => t.id !== id) : prev));
      if (expandedId === id) setExpandedId(null);
    } catch {
      // leave list as-is
    }
  }

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Diet Charts
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Templates
        </h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          Upload CSV templates. Each template is a 7-day grid the AI uses as a starting point when generating a client chart.
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-foreground">
          Upload a template
        </h2>
        <Separator />
        <p className="font-sans text-xs text-muted-foreground">
          CSV format: header row <code className="font-mono">Day,Breakfast,Lunch,…</code>, rows 2–8 are Monday–Sunday, cells are{" "}
          <code className="font-mono">food · timing</code>.
        </p>
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            disabled={uploading}
            className="font-sans text-sm text-foreground file:mr-3 file:cursor-pointer file:rounded file:border-0 file:bg-primary file:px-3 file:py-1.5 file:font-sans file:text-xs file:font-bold file:uppercase file:tracking-widest file:text-primary-foreground disabled:opacity-50"
          />
          {uploading && (
            <span className="font-sans text-xs text-muted-foreground">Uploading…</span>
          )}
        </div>
        {uploadError && (
          <p className="font-sans text-xs text-destructive">{uploadError}</p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-foreground">
          Library
        </h2>
        <Separator />
        {loadError ? (
          <p className="font-sans text-sm text-destructive">Could not load templates.</p>
        ) : templates === null ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : templates.length === 0 ? (
          <p className="py-2 font-heading text-xl font-black text-muted-foreground">
            No templates yet. <em>Upload one above.</em>
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-2xl border border-border">
            {templates.map((t) => {
              const isOpen = expandedId === t.id;
              const slots = (
                (t.parameters as Record<string, unknown>)?.meal_slots as string[]
              ) ?? [];
              return (
                <li key={t.id} className="px-5 py-4">
                  {/* Header row */}
                  <div className="flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => setExpandedId(isOpen ? null : t.id)}
                      className="flex min-w-0 flex-1 items-start gap-3 text-left"
                    >
                      <span
                        className="mt-0.5 shrink-0 font-sans text-xs text-muted-foreground"
                        aria-hidden
                      >
                        {isOpen ? "▲" : "▼"}
                      </span>
                      <div className="min-w-0">
                        <p className="font-heading text-base font-bold text-foreground">
                          {t.name}
                        </p>
                        {slots.length > 0 && (
                          <p className="font-sans text-xs text-muted-foreground">
                            {slots.join(" · ")}
                          </p>
                        )}
                      </div>
                    </button>
                    <button
                      onClick={() => handleDelete(t.id)}
                      className="ml-4 shrink-0 font-sans text-xs text-destructive underline-offset-4 hover:underline"
                    >
                      Remove
                    </button>
                  </div>

                  {/* Expanded grid */}
                  {isOpen && <TemplateGrid template={t} />}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
