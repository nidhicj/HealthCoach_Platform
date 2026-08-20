"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import {
  getUploadTokenState,
  uploadLeadFiles,
  UploadRateLimitError,
  UploadRetryableError,
  UploadValidationError,
} from "@/lib/api/upload";

// Client-side pre-validation mirrors the backend's actual caps (see
// `backend/src/api/upload.py`'s `_MAX_FILES` / `_MAX_FILE_SIZE_BYTES` /
// `_MAX_TOTAL_SIZE_BYTES`). This is a UX nicety only, NOT the security
// boundary — the backend re-validates every cap and does real magic-byte
// MIME sniffing server-side regardless of what's selected here.
const MAX_FILES = 5;
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_SIZE_BYTES = 30 * 1024 * 1024;
const ACCEPTED_MIME_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const FILE_INPUT_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Plain-language fallback copy for the three non-valid token states. The
 * backend always sends a `message` in practice (see
 * `backend/src/api/upload.py`), but `UploadTokenState.message` is nullable
 * in the schema, so this keeps rendering defensive rather than showing a
 * blank page.
 */
const DEFAULT_STATE_MESSAGE: Record<"not_found" | "expired" | "used", string> = {
  not_found:
    "This upload link doesn't seem to be valid. Please check the link or contact your health coach.",
  expired: "This upload link has expired. Please contact your health coach for a new link.",
  used: "This upload link has already been used. If you need to upload additional reports, please contact your health coach.",
};

const STATE_HEADING: Record<"not_found" | "expired" | "used", string> = {
  not_found: "Link not found",
  expired: "Link expired",
  used: "Already uploaded",
};

type View =
  | { kind: "loading" }
  | { kind: "load_error" }
  | { kind: "not_found"; message: string }
  | { kind: "expired"; message: string }
  | { kind: "used"; message: string }
  | { kind: "valid"; hcName: string | null }
  | { kind: "success" };

/** Returns a validation message, or null if the selection is upload-ready. */
function validateFiles(files: File[]): string | null {
  if (files.length === 0) return null;
  if (files.length > MAX_FILES) {
    return `You can upload up to ${MAX_FILES} files at a time.`;
  }
  for (const f of files) {
    if (f.size > MAX_FILE_SIZE_BYTES) {
      return `${f.name}: exceeds the ${MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB per-file limit.`;
    }
    // Some browsers/OSes leave `type` empty for recognized files (e.g. HEIC-
    // renamed PDFs on odd configs) — only reject when the browser actually
    // reports a type and it's not one we accept, matching this codebase's
    // existing file-upload validation convention (see
    // `(app)/clients/[clientId]/sessions/[sessionId]/page.tsx`'s `handleFiles`).
    if (f.type && !ACCEPTED_MIME_TYPES.has(f.type)) {
      return `${f.name}: only PDF, JPEG, or PNG files are accepted.`;
    }
  }
  const total = files.reduce((sum, f) => sum + f.size, 0);
  if (total > MAX_TOTAL_SIZE_BYTES) {
    return `Total upload size exceeds the ${MAX_TOTAL_SIZE_BYTES / (1024 * 1024)} MB limit.`;
  }
  return null;
}

export default function UploadPage() {
  const { token } = useParams<{ token: string }>();
  const [view, setView] = useState<View>({ kind: "loading" });
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!token) return;
    getUploadTokenState(token)
      .then((result) => {
        if (result.state === "valid") {
          setView({ kind: "valid", hcName: result.hc_name ?? null });
        } else {
          setView({
            kind: result.state,
            message: result.message ?? DEFAULT_STATE_MESSAGE[result.state],
          });
        }
      })
      .catch(() => setView({ kind: "load_error" }));
  }, [token]);

  function handleFileChange(fileList: FileList | null) {
    const selected = fileList ? Array.from(fileList) : [];
    setFiles(selected);
    setFileError(validateFiles(selected));
    setSubmitError(null);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (files.length === 0 || fileError || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await uploadLeadFiles(token, files);
      if ("state" in result) {
        // The token was consumed/expired between page load and submit (a
        // race, not the common case) — re-render the same state UI the
        // initial GET would have shown.
        setView(
          result.state === "valid"
            ? { kind: "valid", hcName: result.hc_name ?? null }
            : {
                kind: result.state,
                message: result.message ?? DEFAULT_STATE_MESSAGE[result.state],
              }
        );
      } else {
        // Per SPEC-0001's Coach-reviewed gate, the Lead only ever sees this
        // generic confirmation — never the brief itself, and never whether
        // brief generation succeeded or failed server-side.
        setView({ kind: "success" });
      }
    } catch (err) {
      if (
        err instanceof UploadRetryableError ||
        err instanceof UploadRateLimitError ||
        err instanceof UploadValidationError
      ) {
        setSubmitError(err.message);
      } else {
        setSubmitError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (view.kind === "loading") {
    return (
      <main className="mx-auto max-w-md px-4 py-16">
        <p className="font-sans text-sm text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (view.kind === "load_error") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Something went wrong</h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          Could not load this page right now. Please try again in a moment.
        </p>
      </main>
    );
  }

  if (view.kind === "not_found" || view.kind === "expired" || view.kind === "used") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">
          {STATE_HEADING[view.kind]}
        </h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">{view.message}</p>
      </main>
    );
  }

  if (view.kind === "success") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Reports received</h1>
        <p className="mt-3 font-sans text-sm text-foreground">
          Thank you — we&apos;ve received your files. Your health coach will review them ahead of
          your consultation.
        </p>
      </main>
    );
  }

  // view.kind === "valid"
  const hcName = view.hcName ?? "your health coach";

  return (
    <main className="mx-auto max-w-md px-4 py-10">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Upload your blood reports
        </h1>
        <p className="font-sans text-sm text-muted-foreground">
          {hcName} has requested your recent blood test reports ahead of your consultation.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <div
            onClick={() => fileInputRef.current?.click()}
            className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border px-4 py-6 text-center transition-colors duration-150 hover:border-primary/50"
          >
            <p className="font-sans text-sm text-muted-foreground">Click to choose files</p>
            <p className="font-sans text-xs text-muted-foreground">
              PDF, JPG, or PNG · up to {MAX_FILES} files · {MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB
              per file · {MAX_TOTAL_SIZE_BYTES / (1024 * 1024)} MB total
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={FILE_INPUT_ACCEPT}
              className="hidden"
              onChange={(e) => handleFileChange(e.target.files)}
            />
          </div>

          {files.length > 0 && (
            <ul className="mt-3 divide-y divide-border rounded-lg border border-border">
              {files.map((f, i) => (
                <li
                  key={`${f.name}-${i}`}
                  className="flex items-center justify-between px-3 py-2"
                >
                  <span className="font-sans text-sm text-foreground">{f.name}</span>
                  <span className="font-sans text-xs text-muted-foreground">
                    {formatBytes(f.size)}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {fileError && <p className="mt-2 font-sans text-sm text-destructive">{fileError}</p>}
        </div>

        <div className="rounded-md border border-border bg-muted/30 p-3">
          <p className="font-sans text-sm text-foreground">
            Your reports will be shared only with {hcName} to prepare for your consultation. We
            do not share your information with any third party.
          </p>
        </div>

        {submitError && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {submitError}
          </p>
        )}

        <button
          type="submit"
          disabled={files.length === 0 || !!fileError || submitting}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {submitting ? "Uploading…" : "Upload reports"}
        </button>
      </form>
    </main>
  );
}
