"use client";

import { useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  listTemplates,
  uploadTemplate,
  pasteTemplate,
  deleteTemplate,
  type DietChartOut,
} from "@/lib/api/dietCharts";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function TemplateGrid({ template }: { template: DietChartOut }) {
  const params = template.parameters as Record<string, unknown>;

  if (params?.template_type === "raw_table") {
    const rows = (params?.rows ?? []) as string[][];
    if (rows.length === 0) return null;
    return (
      <div className="overflow-x-auto pt-3">
        <table className="border-collapse text-xs">
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} className="border-b border-border last:border-0">
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className={[
                      "px-3 py-2 font-sans align-top",
                      ci === 0
                        ? "font-bold text-foreground"
                        : "text-muted-foreground",
                      ci > 0 ? "border-l border-border" : "",
                    ].join(" ")}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

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

function templateSubtitle(t: DietChartOut): string {
  const params = t.parameters as Record<string, unknown>;
  if (params?.template_type === "raw_table") {
    const rows = (params?.rows ?? []) as string[][];
    return `${rows.length} rows`;
  }
  const slots = (params?.meal_slots as string[]) ?? [];
  return slots.join(" · ");
}

export default function DietChartTemplatesPage() {
  const [templates, setTemplates] = useState<DietChartOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [pasteName, setPasteName] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [pasting, setPasting] = useState(false);
  const [pasteError, setPasteError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);

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

  async function handlePaste() {
    const name = pasteName.trim();
    if (!name || !pasteText.trim()) return;
    setPasting(true);
    setPasteError(null);
    try {
      const created = await pasteTemplate(name, pasteText);
      setTemplates((prev) => (prev ? [...prev, created] : [created]));
      setPasteName("");
      setPasteText("");
    } catch (err) {
      setPasteError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setPasting(false);
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
          Upload CSV templates or paste directly from Google Sheets. Each template is the starting point the AI uses when generating a client chart.
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
          Paste from Google Sheets
        </h2>
        <Separator />
        <p className="font-sans text-xs text-muted-foreground">
          Select your diet chart range in Google Sheets, copy{" "}
          <code className="font-mono">Ctrl+C</code> / <code className="font-mono">Cmd+C</code>,
          then paste below. The full table is preserved as-is.
        </p>
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Template name
            </label>
            <input
              type="text"
              value={pasteName}
              onChange={(e) => setPasteName(e.target.value)}
              placeholder="e.g. Her Diet Chart Jan"
              className="w-full max-w-sm rounded-lg border border-border bg-background px-3 py-2 font-sans text-sm text-foreground placeholder:text-muted-foreground"
            />
          </div>
          <div className="space-y-1">
            <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Paste here
            </label>
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="Paste your copied cells here…"
              rows={6}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 font-sans text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <button
            onClick={handlePaste}
            disabled={pasting || !pasteName.trim() || !pasteText.trim()}
            className="rounded-lg bg-primary px-4 py-2 font-sans text-xs font-bold uppercase tracking-widest text-primary-foreground disabled:opacity-50"
          >
            {pasting ? "Saving…" : "Save template"}
          </button>
          {pasteError && (
            <p className="font-sans text-xs text-destructive">{pasteError}</p>
          )}
        </div>
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
            No templates yet. <em>Upload or paste one above.</em>
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-2xl border border-border">
            {templates.map((t) => {
              const isOpen = expandedId === t.id;
              const subtitle = templateSubtitle(t);
              return (
                <li key={t.id} className="px-5 py-4">
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
                        {subtitle && (
                          <p className="font-sans text-xs text-muted-foreground">
                            {subtitle}
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
