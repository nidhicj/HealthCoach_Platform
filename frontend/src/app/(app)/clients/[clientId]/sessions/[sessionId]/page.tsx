"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  getSession,
  getBrief,
  getMom,
  draftMom,
  patchMom,
  sendMom,
  endSession,
  patchSession,
  type SessionOut,
  type BriefOut,
  type MomOut,
} from "@/lib/api/sessions";
import {
  listFiles,
  uploadFiles,
  deleteFile,
  type ClientFileOut,
} from "@/lib/api/files";
import { getClient, type ClientDetailOut } from "@/lib/api/clients";
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
}: {
  session: SessionOut;
  brief: BriefOut | null;
  briefLoading: boolean;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  const sessionDate = new Date(session.scheduled_at).toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="font-heading text-2xl font-black text-foreground">
          Pre-session brief — M{String(session.session_number).padStart(3, "0")}, {sessionDate}
        </h2>
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

// ── tab: Notes ────────────────────────────────────────────────────────────────

function NotesTab({
  session,
  files,
  filesLoading,
  onFilesChange,
}: {
  session: SessionOut;
  files: ClientFileOut[];
  filesLoading: boolean;
  onFilesChange: (files: ClientFileOut[]) => void;
}) {
  const [notes, setNotes] = useState(session.session_notes ?? "");
  const [saving, setSaving] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerSave = useCallback(
    (value: string) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(async () => {
        setSaving(true);
        try {
          await patchSession(session.id, { session_notes: value });
        } finally {
          setSaving(false);
        }
      }, 800);
    },
    [session.id],
  );

  function handleNotesChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setNotes(val);
    triggerSave(val);
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
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
            Session notes
          </h2>
          {saving && (
            <span className="font-sans text-xs text-muted-foreground">Saving…</span>
          )}
        </div>
        <Textarea
          value={notes}
          onChange={handleNotesChange}
          placeholder="Paste transcript, write observations, add context…"
          className="min-h-64 font-sans text-sm leading-relaxed resize-y"
        />
      </div>

      <Separator />

      <div className="space-y-4">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Files
        </h2>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 transition-colors duration-150 ${
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

        {/* File list */}
        {filesLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : files.length > 0 ? (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {files.map((file) => (
              <li
                key={file.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div>
                  <p className="font-sans text-sm text-foreground">
                    {file.original_filename}
                    {file.is_zoom_summary && (
                      <Badge variant="secondary" className="ml-2">
                        Zoom summary
                      </Badge>
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
  );
}

// ── tab: MOM ─────────────────────────────────────────────────────────────────

function MomTab({
  session,
  mom,
  onMomChange,
}: {
  session: SessionOut;
  mom: MomOut | null;
  onMomChange: (mom: MomOut) => void;
}) {
  const [drafting, setDrafting] = useState(false);
  const [sending, setSending] = useState(false);
  const [editedText, setEditedText] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [draftVisible, setDraftVisible] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (mom?.final_text != null) {
      setEditedText(mom.final_text);
      setDraftVisible(true);
    } else if (mom?.draft_text) {
      setEditedText(mom.draft_text);
      setDraftVisible(true);
    }
  }, [mom?.id]);

  async function handleDraft() {
    setDrafting(true);
    setDraftVisible(false);
    try {
      const result = await draftMom(session.id, session.session_notes ?? "");
      onMomChange(result);
      setEditedText(result.draft_text);
    } finally {
      setDrafting(false);
      requestAnimationFrame(() => setDraftVisible(true));
    }
  }

  function handleEditChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setEditedText(val);
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      setSaving(true);
      try {
        const updated = await patchMom(session.id, { final_text: val });
        onMomChange(updated);
      } finally {
        setSaving(false);
      }
    }, 800);
  }

  async function handleSend() {
    setSending(true);
    try {
      const result = await sendMom(session.id);
      onMomChange(result);
    } finally {
      setSending(false);
    }
  }

  const isSent = mom?.status === "sent";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Minutes of meeting
        </h2>
        {mom && (
          <Badge variant={isSent ? "secondary" : "outline"}>
            {isSent ? "Sent" : mom.status.replace(/_/g, " ")}
          </Badge>
        )}
      </div>

      {mom === null ? (
        <div className="space-y-4">
          <p className="font-heading text-lg font-black text-muted-foreground">
            No MOM yet. <em>Generate the draft first.</em>
          </p>
          <Button variant="default" onClick={handleDraft} disabled={drafting}>
            {drafting ? "Generating draft…" : "Generate draft"}
          </Button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Two-pane on desktop, stacked on mobile */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Left: AI draft */}
            <div className="space-y-2">
              <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                AI draft
              </p>
              {drafting ? (
                <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-4">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                  <Skeleton className="h-4 w-4/6" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/6" />
                </div>
              ) : (
                <div
                  className={cn(
                    "rounded-lg border border-border bg-muted/40 p-4 transition-opacity duration-200",
                    draftVisible ? "opacity-100" : "opacity-0",
                  )}
                >
                  <p className="font-sans text-sm leading-relaxed text-foreground whitespace-pre-line">
                    {mom.draft_text}
                  </p>
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleDraft}
                disabled={drafting || isSent}
              >
                {drafting ? "Regenerating…" : "Regenerate draft"}
              </Button>
            </div>

            {/* Right: editable final */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                  Your version
                </p>
                {saving && (
                  <span className="font-sans text-xs text-muted-foreground">
                    Saving…
                  </span>
                )}
              </div>
              <Textarea
                value={editedText}
                onChange={handleEditChange}
                disabled={isSent}
                placeholder="Edit the draft here before sending…"
                className="min-h-64 font-sans text-sm leading-relaxed resize-y"
              />
            </div>
          </div>

          {/* Send button — THE single Marigold on this screen */}
          {!isSent ? (
            <Button
              variant="accent"
              onClick={handleSend}
              disabled={sending || !editedText.trim()}
              className="view-transition-name-[mom-send]"
            >
              {sending ? "Sending…" : "Send to client"}
            </Button>
          ) : (
            <p className="font-sans text-sm font-bold text-primary">
              MOM sent to client.{" "}
              {mom.sent_at &&
                new Date(mom.sent_at).toLocaleDateString("en-IN", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
            </p>
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
      const result = await getBrief(sessionId);
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
          <Tabs defaultValue="brief" className="space-y-0">
            {/* overflow-x-auto keeps the tab strip from expanding <html> width at 375px */}
            <div className="overflow-x-auto">
              <TabsList variant="line">
                <TabsTrigger value="brief">Pre-session brief</TabsTrigger>
                <TabsTrigger value="notes">In-session notes</TabsTrigger>
                <TabsTrigger value="mom">MOM editor</TabsTrigger>
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
                />
              </TabsContent>

              <TabsContent value="notes">
                <NotesTab
                  session={session!}
                  files={files}
                  filesLoading={filesLoading}
                  onFilesChange={setFiles}
                />
              </TabsContent>

              <TabsContent value="mom">
                <MomTab
                  session={session!}
                  mom={mom}
                  onMomChange={setMom}
                />
              </TabsContent>
            </div>
          </Tabs>
        </>
      )}
    </div>
  );
}
