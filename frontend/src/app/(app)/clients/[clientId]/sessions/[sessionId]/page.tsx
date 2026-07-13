"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  getSession,
  getBrief,
  generateBrief,
  getMom,
  draftMom,
  patchMom,
  freezeMom,
  sendMom,
  endSession,
  patchSession,
  linkCalendarEvent,
  type SessionOut,
  type BriefOut,
  type MomOut,
  type ActionItemDraft,
} from "@/lib/api/sessions";
import {
  listFiles,
  uploadFiles,
  deleteFile,
  type ClientFileOut,
} from "@/lib/api/files";
import { getClient, type ClientDetailOut } from "@/lib/api/clients";
import { CalendarView } from "@/components/calendar/CalendarView";
import type { CalendarEvent } from "@/lib/api/calendar";
import { cn } from "@/lib/utils";

// ── helpers ──────────────────────────────────────────────────────────────────

const ALLOWED_MIME = new Set([
  "text/plain",
  "text/markdown",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);
const MAX_SIZE_BYTES = 25 * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── tab: Brief ────────────────────────────────────────────────────────────────

function BriefTab({
  session,
  brief,
  briefLoading,
  onRegenerate,
  regenerating,
  onNext,
}: {
  session: SessionOut;
  brief: BriefOut | null;
  briefLoading: boolean;
  onRegenerate: () => void;
  regenerating: boolean;
  onNext: () => void;
}) {
  const sessionDate = new Date(session.scheduled_at).toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-heading text-2xl font-black text-foreground">
            Pre-session brief — M{String(session.session_number).padStart(3, "0")}, {sessionDate}
          </h2>
          <button
            onClick={onNext}
            className="shrink-0 rounded-md px-3 py-1.5 font-sans text-xs font-bold text-foreground"
            style={{ backgroundColor: "var(--color-marigold)" }}
          >
            Next →
          </button>
        </div>
        <div className="h-0.5 w-10 bg-primary" aria-hidden />
      </div>

      {briefLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-4/5" />
          <Skeleton className="h-5 w-3/5" />
        </div>
      ) : brief === null ? (
        <div className="space-y-4">
          <p className="font-heading text-lg font-black text-muted-foreground">
            No brief yet. <em>Generate one before the session.</em>
          </p>
          <Button variant="default" onClick={onRegenerate} disabled={regenerating}>
            {regenerating ? "Generating…" : "Generate brief"}
          </Button>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="rounded-lg border border-border bg-muted/40 p-5">
            <p className="font-sans text-sm leading-relaxed text-foreground whitespace-pre-line">
              {brief.brief_text}
            </p>
          </div>

          {brief.triage_flags && brief.triage_flags.length > 0 && (
            <div className="space-y-2">
              <p className="font-sans text-xs font-bold uppercase tracking-widest text-destructive">
                Triage flags
              </p>
              <div className="flex flex-wrap gap-1.5">
                {brief.triage_flags.map((flag) => (
                  <Badge key={flag} variant="destructive">
                    {flag.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <Button variant="outline" size="sm" onClick={onRegenerate} disabled={regenerating}>
            {regenerating ? "Regenerating…" : "Regenerate"}
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Google Calendar event picker (PHASE-01e Task 16) ────────────────────────
//
// Reuses this file's existing modal-overlay convention (see SendDialog below):
// a fixed, centered `bg-black/40` backdrop with a bordered panel — rather than
// introducing the separate (and, elsewhere in this app, dev-only) shadcn/base-ui
// Dialog primitive.

function CalendarPickerDialog({
  onClose,
  onSelectEvent,
  linking,
  error,
}: {
  onClose: () => void;
  onSelectEvent: (event: CalendarEvent) => void;
  linking: boolean;
  error: string | null;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[85vh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-xl border border-border bg-background p-6">
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-xl font-black text-foreground">
            Choose from Google Calendar
          </h3>
          <Button variant="outline" size="sm" onClick={onClose} disabled={linking}>
            Close
          </Button>
        </div>

        {error && <p className="font-sans text-sm text-destructive">{error}</p>}

        <CalendarView onSelectEvent={onSelectEvent} />
      </div>
    </div>
  );
}

// ── tab: Session ──────────────────────────────────────────────────────────────

export function NotesTab({
  session,
  files,
  filesLoading,
  onFilesChange,
  onSessionChange,
  onNext,
}: {
  session: SessionOut;
  files: ClientFileOut[];
  filesLoading: boolean;
  onFilesChange: (files: ClientFileOut[]) => void;
  onSessionChange: (session: SessionOut) => void;
  onNext: () => void;
}) {
  const [notes, setNotes] = useState(session.notes_internal ?? "");
  const [notesFrozen, setNotesFrozen] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [editingLink, setEditingLink] = useState(false);
  const [linkDraft, setLinkDraft] = useState("");
  const [savingLink, setSavingLink] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [showCalendarPicker, setShowCalendarPicker] = useState(false);
  const [linkingCalendarEvent, setLinkingCalendarEvent] = useState(false);
  const [calendarLinkError, setCalendarLinkError] = useState<string | null>(null);
  const [unlinking, setUnlinking] = useState(false);

  async function handleNotesSave() {
    setNotesSaving(true);
    try {
      await patchSession(session.id, { notes_internal: notes });
      setNotesFrozen(true);
    } catch (err) {
      console.error(err);
    } finally {
      setNotesSaving(false);
    }
  }

  async function handleSaveLink() {
    setSavingLink(true);
    setLinkError(null);
    try {
      const updated = await patchSession(session.id, { meeting_url: linkDraft.trim() });
      onSessionChange(updated);
      setEditingLink(false);
    } catch (err) {
      setLinkError(err instanceof Error ? err.message : "Failed to save link.");
    } finally {
      setSavingLink(false);
    }
  }

  async function handleSelectCalendarEvent(event: CalendarEvent) {
    setLinkingCalendarEvent(true);
    setCalendarLinkError(null);
    try {
      const updated = await linkCalendarEvent(session.id, event.id);
      onSessionChange(updated);
      setShowCalendarPicker(false);
    } catch (err) {
      setCalendarLinkError(err instanceof Error ? err.message : "Failed to link calendar event.");
    } finally {
      setLinkingCalendarEvent(false);
    }
  }

  async function handleUnlinkCalendarEvent() {
    setUnlinking(true);
    setCalendarLinkError(null);
    try {
      const updated = await linkCalendarEvent(session.id, null);
      onSessionChange(updated);
    } catch (err) {
      setCalendarLinkError(err instanceof Error ? err.message : "Failed to unlink calendar event.");
    } finally {
      setUnlinking(false);
    }
  }

  async function handleFiles(incoming: FileList | null) {
    if (!incoming || incoming.length === 0) return;
    setUploadError(null);
    const valid: File[] = [];
    for (const f of Array.from(incoming)) {
      if (!ALLOWED_MIME.has(f.type)) {
        setUploadError(`${f.name}: unsupported file type. Use .txt, .md, .pdf, or .docx.`);
        return;
      }
      if (f.size > MAX_SIZE_BYTES) {
        setUploadError(`${f.name}: exceeds 25 MB limit.`);
        return;
      }
      valid.push(f);
    }
    setUploading(true);
    try {
      const uploaded = await uploadFiles(session.id, valid);
      onFilesChange([...files, ...uploaded]);
    } catch {
      setUploadError("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(fileId: string) {
    setDeletingId(fileId);
    try {
      await deleteFile(session.id, fileId);
      onFilesChange(files.filter((f) => f.id !== fileId));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-4">
      {/* Tab header */}
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-2xl font-black text-foreground">
          Session
        </h2>
        <button
          onClick={onNext}
          className="rounded-md px-3 py-1.5 font-sans text-xs font-bold text-foreground"
          style={{ backgroundColor: "var(--color-marigold)" }}
        >
          Next →
        </button>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">

        {/* Left: Meet placeholder */}
        <div className="flex min-h-[420px] flex-col items-center justify-center gap-4 rounded-xl border border-border bg-muted/20 p-10 text-center">
          {editingLink ? (
            <div className="w-full max-w-sm space-y-3">
              <Input
                type="url"
                value={linkDraft}
                onChange={(e) => setLinkDraft(e.target.value)}
                placeholder="https://meet.google.com/…"
                autoFocus
              />
              <div className="flex items-center justify-center gap-2">
                <Button size="sm" onClick={handleSaveLink} disabled={savingLink}>
                  {savingLink ? "Saving…" : "Save"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditingLink(false)} disabled={savingLink}>
                  Cancel
                </Button>
              </div>
              {linkError && <p className="font-sans text-xs text-destructive">{linkError}</p>}
            </div>
          ) : session.meeting_url ? (
            <>
              <p className="font-heading text-3xl font-black text-muted-foreground">
                Meeting link
              </p>
              <a
                href={session.meeting_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 rounded-full bg-primary px-4 py-1.5 font-sans text-xs font-bold text-primary-foreground"
              >
                Join call →
              </a>
              {session.google_calendar_event_id && (
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">via Google Calendar</Badge>
                  <button
                    onClick={handleUnlinkCalendarEvent}
                    disabled={unlinking}
                    className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline disabled:opacity-50"
                  >
                    {unlinking ? "Unlinking…" : "Unlink"}
                  </button>
                </div>
              )}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => { setLinkDraft(session.meeting_url ?? ""); setEditingLink(true); }}
                  className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
                >
                  Edit link
                </button>
                <button
                  onClick={() => { setCalendarLinkError(null); setShowCalendarPicker(true); }}
                  className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
                >
                  Choose from Google Calendar →
                </button>
              </div>
              {calendarLinkError && !showCalendarPicker && (
                <p className="font-sans text-xs text-destructive">{calendarLinkError}</p>
              )}
            </>
          ) : (
            <>
              <p className="font-heading text-3xl font-black text-muted-foreground">
                No meeting link yet
              </p>
              <button
                onClick={() => { setLinkDraft(""); setEditingLink(true); }}
                className="mt-1 rounded-full border border-border bg-background px-4 py-1.5 font-sans text-xs text-foreground hover:border-primary"
              >
                + Add meeting link
              </button>
              <button
                onClick={() => { setCalendarLinkError(null); setShowCalendarPicker(true); }}
                className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
              >
                Choose from Google Calendar →
              </button>
              {calendarLinkError && !showCalendarPicker && (
                <p className="font-sans text-xs text-destructive">{calendarLinkError}</p>
              )}
            </>
          )}
        </div>

        {/* Right: Notes + Files */}
        <div className="space-y-5">

          {/* Session notes */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                Session notes
              </h3>
              {notesFrozen ? (
                <Button variant="outline" size="sm" onClick={() => setNotesFrozen(false)}>
                  Edit
                </Button>
              ) : notesSaving ? (
                <span className="font-sans text-xs text-muted-foreground">Saving…</span>
              ) : (
                <Button variant="secondary" size="sm" onClick={handleNotesSave}>
                  Save
                </Button>
              )}
            </div>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              readOnly={notesFrozen}
              placeholder="Paste transcript, write observations, add context…"
              className={cn(
                "min-h-40 font-sans text-sm leading-relaxed resize-y",
                notesFrozen && "opacity-70 bg-muted/50",
              )}
            />
          </div>

          <Separator />

          {/* Files */}
          <div className="space-y-3">
            <h3 className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Files
            </h3>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                handleFiles(e.dataTransfer.files);
              }}
              onClick={() => fileInputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 transition-colors duration-150 ${
                dragOver ? "border-primary bg-muted" : "border-border hover:border-primary/50"
              }`}
            >
              <p className="font-sans text-sm text-muted-foreground">
                {uploading ? "Uploading…" : "Drop files here, or click to browse"}
              </p>
              <p className="font-sans text-xs text-muted-foreground">
                .txt · .md · .pdf · .docx · max 25 MB
              </p>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".txt,.md,.pdf,.docx"
                className="hidden"
                onChange={(e) => handleFiles(e.target.files)}
              />
            </div>
            {uploadError && (
              <p className="font-sans text-sm text-destructive">{uploadError}</p>
            )}
            {filesLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : files.length > 0 ? (
              <ul className="divide-y divide-border rounded-lg border border-border">
                {files.map((file) => (
                  <li key={file.id} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <p className="font-sans text-sm text-foreground">
                        {file.original_filename}
                        {file.is_zoom_summary && (
                          <Badge variant="secondary" className="ml-2">Zoom summary</Badge>
                        )}
                      </p>
                      <p className="font-sans text-xs text-muted-foreground">
                        {formatBytes(file.size_bytes)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(file.id)}
                      disabled={deletingId === file.id}
                      className="text-destructive hover:text-destructive"
                    >
                      {deletingId === file.id ? "Removing…" : "Remove"}
                    </Button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      </div>

      {showCalendarPicker && (
        <CalendarPickerDialog
          onClose={() => setShowCalendarPicker(false)}
          onSelectEvent={handleSelectCalendarEvent}
          linking={linkingCalendarEvent}
          error={calendarLinkError}
        />
      )}
    </div>
  );
}

// ── tab: Session Review ───────────────────────────────────────────────────────

function SendDialog({
  mom,
  clientName,
  coachName,
  onSent,
  onClose,
}: {
  mom: MomOut;
  clientName: string;
  coachName: string;
  onSent: (mom: MomOut) => void;
  onClose: () => void;
}) {
  const [message, setMessage] = useState(
    `Hi ${clientName.split(" ")[0]}, here's what we're focusing on this week. Keep it up! — ${coachName}`,
  );
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    setSending(true);
    setError(null);
    try {
      const updated = await sendMom(mom.session_id, message);
      onSent(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg space-y-4 rounded-xl border border-border bg-background p-6">
        <h3 className="font-heading text-xl font-black text-foreground">Send to client</h3>

        <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-4">
          <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Action items (read-only)
          </p>
          <ul className="space-y-1 font-sans text-sm">
            {(mom.action_items_draft ?? []).map((item, i) => (
              <li key={i}>
                {item.description}
                {item.due_date && <span className="text-muted-foreground"> (due {item.due_date})</span>}
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-1">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="min-h-32 font-sans text-sm"
          />
          <p className="font-sans text-xs text-muted-foreground">
            This message isn&apos;t tracked as an action item.
          </p>
        </div>

        {error && <p className="font-sans text-sm text-destructive">{error}</p>}

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={sending}>
            Cancel
          </Button>
          <Button variant="default" size="sm" onClick={handleSend} disabled={sending}>
            {sending ? "Sending…" : "Send"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function MomTab({
  session,
  mom,
  onMomChange,
  onSaved,
}: {
  session: SessionOut;
  mom: MomOut | null;
  onMomChange: (mom: MomOut) => void;
  onSaved: (mom: MomOut) => void;
}) {
  const [drafting, setDrafting] = useState(false);
  const [sessionReviewText, setSessionReviewText] = useState<string>("");
  const [actionItems, setActionItems] = useState<ActionItemDraft[]>([]);
  const [sessionReviewFrozen, setSessionReviewFrozen] = useState(false);
  const [draftVisible, setDraftVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (mom?.final_text != null) {
      setSessionReviewText(mom.final_text);
      setDraftVisible(true);
    } else if (mom?.draft_text) {
      setSessionReviewText(mom.draft_text);
      setDraftVisible(true);
    }
    setActionItems(mom?.action_items_draft ?? []);
    setSessionReviewFrozen(mom?.status !== "draft" && mom !== null);
  }, [mom?.id, mom?.status]);

  async function handleDraft() {
    setDrafting(true);
    setDraftVisible(false);
    try {
      const result = await draftMom(session.id, session.notes_internal ?? "");
      onMomChange(result);
      setSessionReviewText(result.draft_text);
      setActionItems(result.action_items_draft ?? []);
      setSessionReviewFrozen(false);
    } finally {
      setDrafting(false);
      requestAnimationFrame(() => setDraftVisible(true));
    }
  }

  async function handleSave() {
    const confirmed = window.confirm(
      "Once saved, this locks the review and creates your client's action items — you won't be able to edit it after. Continue?",
    );
    if (!confirmed) return;

    setSaving(true);
    setSaveError(null);
    try {
      await patchMom(session.id, {
        final_text: sessionReviewText,
        action_items_draft: actionItems,
      });
      const frozen = await freezeMom(session.id);
      onMomChange(frozen);
      setSessionReviewFrozen(true);
      onSaved(frozen);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save. Check the action items for anything unusual and try again.");
    } finally {
      setSaving(false);
    }
  }

  function updateActionItem(index: number, description: string) {
    setActionItems((prev) => prev.map((item, i) => (i === index ? { ...item, description } : item)));
  }

  function removeActionItem(index: number) {
    setActionItems((prev) => prev.filter((_, i) => i !== index));
  }

  function addActionItem() {
    setActionItems((prev) => [...prev, { description: "", due_date: null }]);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-2xl font-black text-foreground">
          Session review
        </h2>
      </div>

      {mom === null ? (
        <div className="space-y-4">
          <p className="font-heading text-lg font-black text-muted-foreground">
            No session review yet. <em>Generate the draft first.</em>
          </p>
          <Button variant="default" onClick={handleDraft} disabled={drafting}>
            {drafting ? "Generating draft…" : "Generate draft"}
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {drafting ? (
            <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-4">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-4/6" />
            </div>
          ) : (
            <Textarea
              value={sessionReviewText}
              onChange={(e) => setSessionReviewText(e.target.value)}
              readOnly={sessionReviewFrozen}
              placeholder="Edit the session review here…"
              className={cn(
                "min-h-64 font-sans text-sm leading-relaxed resize-y transition-opacity duration-200",
                draftVisible ? (sessionReviewFrozen ? "opacity-70" : "opacity-100") : "opacity-0",
                sessionReviewFrozen && "bg-muted/50",
              )}
            />
          )}

          {!sessionReviewFrozen && !drafting && (
            <div className="space-y-2 rounded-lg border border-border p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                  Action items
                </h3>
                <p className="font-sans text-xs text-muted-foreground">
                  Anything listed here will be tracked and shown to your client.
                </p>
              </div>
              {actionItems.map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    value={item.description}
                    onChange={(e) => updateActionItem(i, e.target.value)}
                    className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 font-sans text-sm"
                    placeholder="Action item description"
                  />
                  <button
                    onClick={() => removeActionItem(i)}
                    className="font-sans text-xs text-muted-foreground hover:text-destructive"
                  >
                    Remove
                  </button>
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={addActionItem}>
                + Add action item
              </Button>
            </div>
          )}

          {!sessionReviewFrozen && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleDraft} disabled={drafting}>
                  {drafting ? "Regenerating…" : "Regenerate draft"}
                </Button>
                <Button variant="default" size="sm" onClick={handleSave} disabled={saving || drafting || !sessionReviewText.trim()}>
                  {saving ? "Saving…" : "Save"}
                </Button>
              </div>
              {saveError && (
                <p className="font-sans text-sm text-destructive">{saveError}</p>
              )}
            </div>
          )}

          {sessionReviewFrozen && mom.status === "reviewed" && (
            <div className="space-y-2">
              <Button variant="default" size="sm" onClick={() => onSaved(mom)}>
                Send to client
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function SessionPage() {
  const { clientId, sessionId } = useParams<{
    clientId: string;
    sessionId: string;
  }>();

  const [session, setSession] = useState<SessionOut | null>(null);
  const [client, setClient] = useState<ClientDetailOut | null>(null);
  const [brief, setBrief] = useState<BriefOut | null>(null);
  const [briefLoading, setBriefLoading] = useState(true);
  const [mom, setMom] = useState<MomOut | null>(null);
  const [files, setFiles] = useState<ClientFileOut[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [ending, setEnding] = useState(false);
  const [activeTab, setActiveTab] = useState("brief");
  const [sendDialogMom, setSendDialogMom] = useState<MomOut | null>(null);

  useEffect(() => {
    if (!clientId || !sessionId) return;
    Promise.all([
      getSession(sessionId),
      getClient(clientId),
    ])
      .then(([s, c]) => {
        setSession(s);
        setClient(c);
        // Load brief, MOM, files in parallel (all optional — 404 = not yet generated)
        return Promise.allSettled([
          getBrief(sessionId),
          getMom(sessionId),
          listFiles(sessionId),
        ]);
      })
      .then(([briefResult, momResult, filesResult]) => {
        if (briefResult.status === "fulfilled") setBrief(briefResult.value);
        if (momResult.status === "fulfilled") setMom(momResult.value);
        if (filesResult.status === "fulfilled") setFiles(filesResult.value);
        setBriefLoading(false);
        setFilesLoading(false);
      })
      .catch(() => {
        setLoadError(true);
        setBriefLoading(false);
        setFilesLoading(false);
      });
  }, [clientId, sessionId]);

  async function handleRegenerate() {
    if (!sessionId) return;
    setRegenerating(true);
    try {
      const result = brief === null
        ? await getBrief(sessionId)      // first generation: GET (creates if missing)
        : await generateBrief(sessionId); // re-generation: POST (deletes + recreates)
      setBrief(result);
    } finally {
      setRegenerating(false);
    }
  }

  async function handleEndSession() {
    if (!sessionId) return;
    setEnding(true);
    try {
      const updated = await endSession(sessionId);
      setSession(updated);
    } finally {
      setEnding(false);
    }
  }

  const loading = !loadError && session === null;

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <Link
        href={`/clients/${clientId}`}
        className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        ← {client?.full_name ?? "Client"}
      </Link>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-5 w-32" />
        </div>
      ) : loadError ? (
        <p className="font-sans text-sm text-destructive">
          Could not load session.
        </p>
      ) : (
        <>
          {/* Session header */}
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <h1 className="font-heading text-4xl font-black text-foreground">
                Session {session!.session_number}
              </h1>
              <div className="flex items-center gap-3">
                <span className="font-sans text-sm text-muted-foreground">
                  {new Date(session!.scheduled_at).toLocaleDateString("en-IN", {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  })}
                </span>
                {session!.ended_at ? (
                  <Badge variant="secondary">Ended</Badge>
                ) : session!.started_at ? (
                  <Badge>In progress</Badge>
                ) : (
                  <Badge variant="outline">Scheduled</Badge>
                )}
              </div>
            </div>

            {!session!.ended_at && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleEndSession}
                disabled={ending}
              >
                {ending ? "Ending…" : "End session"}
              </Button>
            )}
          </div>

          <Separator />

          {/* Three-tab layout */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-0">
            {/* overflow-x-auto keeps the tab strip from expanding <html> width at 375px */}
            <div className="overflow-x-auto">
              <TabsList variant="line">
                <TabsTrigger value="brief">Pre-session brief</TabsTrigger>
                <TabsTrigger value="notes">Session</TabsTrigger>
                <TabsTrigger value="mom">Session Review</TabsTrigger>
              </TabsList>
            </div>

            <div className="mt-6">
              <TabsContent value="brief">
                <BriefTab
                  session={session!}
                  brief={brief}
                  briefLoading={briefLoading}
                  onRegenerate={handleRegenerate}
                  regenerating={regenerating}
                  onNext={() => setActiveTab("notes")}
                />
              </TabsContent>

              <TabsContent value="notes">
                <NotesTab
                  session={session!}
                  files={files}
                  filesLoading={filesLoading}
                  onFilesChange={setFiles}
                  onSessionChange={setSession}
                  onNext={() => setActiveTab("mom")}
                />
              </TabsContent>

              <TabsContent value="mom">
                <MomTab
                  session={session!}
                  mom={mom}
                  onMomChange={setMom}
                  onSaved={(savedMom) => setSendDialogMom(savedMom)}
                />
              </TabsContent>
            </div>
          </Tabs>

          {sendDialogMom && client && (
            <SendDialog
              mom={sendDialogMom}
              clientName={client.full_name}
              coachName="Your coach"
              onSent={(updated) => {
                setMom(updated);
                setSendDialogMom(null);
              }}
              onClose={() => setSendDialogMom(null)}
            />
          )}
        </>
      )}
    </div>
  );
}
