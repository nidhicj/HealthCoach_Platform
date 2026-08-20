import { z } from "zod";
import { API_URL } from "@/lib/config";

/**
 * Public Lead-facing upload API — unauthenticated endpoints via same-origin BFF
 * proxy (mirrors `intake.ts`'s pattern: plain `fetch()`, no `client.ts` auth
 * wrapper). No auth header is ever attached — these endpoints are resolved by
 * the raw upload token mailed to the Lead (see `backend/src/api/upload.py`).
 *
 * GET  /api/upload/{token}        — resolve the token's current state
 * POST /api/upload/{token}/files  — submit blood report files (multipart/form-data)
 *
 * Token state machine (backend's `UploadTokenStateOut`, shared verbatim by both
 * endpoints — see `backend/src/api/upload.py`): exactly four states —
 * "not_found" | "expired" | "used" | "valid". There is no separate "invalid"
 * state; a token that never existed or was tampered with resolves to
 * "not_found". Both the GET check and a POST against a non-"valid" token
 * return this SAME shape at HTTP 200 (never a 4xx) — a Lead-facing state
 * machine, not a tenant-isolation boundary — so the frontend can render "which
 * invalid state occurred" from one discriminated-state renderer shared across
 * both calls. `POST` only ever returns `UploadFilesResponse` on genuine
 * success (201) or a token-state object with state != "valid" (200); it never
 * returns state=="valid".
 *
 * POST failure modes, distinguished by HTTP status (confirmed by reading
 * `backend/src/api/upload.py`'s POST handler, not assumed):
 * - 422 — validation failure (no files, too many files, oversized file/batch,
 *   unrecognized MIME type). `{detail: string}`.
 * - 429 — rate-limited (10 req/hour per IP, `src/main.py`'s
 *   `rate_limit_exception_handler`). `{detail: string}`.
 * - 503 — R2 write failure mid-batch (`s3_put()` raised). Nothing is persisted
 *   (token stays unused, no `LeadFile` rows added) — the Lead's link is still
 *   valid and the upload can be retried as-is. Distinguished from 422/429 as
 *   `UploadRetryableError` so a caller can show retry-safe copy.
 *   `{detail: string}`.
 *
 * Error response bodies (422, 429, 503) follow FastAPI's `{detail: string}`
 * format for this endpoint specifically — unlike `intake.ts`'s POST, this
 * endpoint's 422s are always raised via `HTTPException(detail=<str>)`
 * (never FastAPI's native list-of-errors `RequestValidationError` shape,
 * since `files: list[UploadFile]` has no Pydantic body model to fail
 * validation against before the handler body runs). `extractDetailMessage`
 * still handles the list shapes defensively in case that ever changes.
 */

const UploadTokenStateSchema = z.object({
  state: z.enum(["not_found", "expired", "used", "valid"]),
  message: z.string().nullable().optional(),
  hc_name: z.string().nullable().optional(),
});

export type UploadTokenState = z.infer<typeof UploadTokenStateSchema>;

const UploadFilesResponseSchema = z.object({
  message: z.string(),
});

export type UploadFilesResponse = z.infer<typeof UploadFilesResponseSchema>;

/**
 * Result of a successful `POST /api/upload/{token}/files` call. Either the
 * upload genuinely succeeded (`UploadFilesResponse`, HTTP 201 — has no `state`
 * field), or the token was resolved as not_found/expired/used at the top of
 * the handler before any file was processed (`UploadTokenState`, HTTP 200 —
 * always has a `state` field). Discriminate with `"state" in result`.
 */
export type UploadFilesResult = UploadFilesResponse | UploadTokenState;

/**
 * Helper to safely parse JSON from a response, returning the body or null on
 * parse failure. Mirrors `intake.ts`.
 */
async function safeParseJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Helper to extract and format error detail from FastAPI response body.
 * Mirrors `intake.ts`'s `extractDetailMessage` exactly — handles the same
 * three possible `detail` shapes (string / string[] / FastAPI validation
 * error objects), defensively, even though this endpoint's own error paths
 * only ever produce the plain-string shape (see module docstring).
 */
function extractDetailMessage(body: unknown): string | string[] | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as Record<string, unknown>).detail;

  // Case 1: string
  if (typeof detail === "string") return detail;

  // Case 2 & 3: array — could be string[] or validation error object[]
  if (Array.isArray(detail)) {
    if (detail.every((d) => typeof d === "string")) {
      return detail;
    }

    if (detail.every((d) => typeof d === "object" && d !== null && "msg" in d)) {
      const messages = (detail as Array<{ msg?: unknown }>)
        .map((err) => (typeof err.msg === "string" ? err.msg : "Invalid request"))
        .filter((msg) => msg);
      return messages.length > 0 ? messages : null;
    }

    return null;
  }

  return null;
}

/**
 * Error subclasses to allow fine-grained error handling by status code.
 * Each class unwraps the `detail` field from the FastAPI response body and
 * sets it as the error's message and detail property. Mirrors `intake.ts`'s
 * error-class convention.
 */

export class UploadError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: string | string[] | null
  ) {
    super(message);
    this.name = "UploadError";
  }
}

/** 422 — batch/file validation failure (too many files, oversized, bad MIME type, no files). */
export class UploadValidationError extends UploadError {
  constructor(body?: unknown) {
    const detail = extractDetailMessage(body);
    const message = Array.isArray(detail) ? detail.join("; ") : (typeof detail === "string" ? detail : "Validation failed");
    super(422, message, detail);
    this.name = "UploadValidationError";
  }
}

/** 429 — rate limited (10 uploads/hour per IP). */
export class UploadRateLimitError extends UploadError {
  constructor(body?: unknown) {
    const detail = extractDetailMessage(body);
    const message = typeof detail === "string" ? detail : "Rate limit exceeded";
    super(429, message, detail);
    this.name = "UploadRateLimitError";
  }
}

/**
 * 503 — R2 write failed mid-batch. Nothing was persisted; the Lead's upload
 * link is still valid and the request can be retried as-is. Kept distinct
 * from `UploadValidationError`/`UploadRateLimitError` so a caller can show
 * retry-safe copy instead of a hard failure.
 */
export class UploadRetryableError extends UploadError {
  constructor(body?: unknown) {
    const detail = extractDetailMessage(body);
    const message =
      typeof detail === "string"
        ? detail
        : "We couldn't process your upload. Please try again — your link is still valid.";
    super(503, message, detail);
    this.name = "UploadRetryableError";
  }
}

/**
 * Fetch the current state of an upload token (not_found/expired/used/valid).
 * Always resolves — the backend always returns HTTP 200 for this endpoint
 * (see module docstring), so this never throws on a "bad" token; the caller
 * inspects `result.state` to decide what to render. Only throws `UploadError`
 * on a network failure, non-200 response, or unparseable body.
 */
export async function getUploadTokenState(token: string): Promise<UploadTokenState> {
  const url = `${API_URL}/api/upload/${encodeURIComponent(token)}`;
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    throw new UploadError(0, `Network error fetching upload token state`, null);
  }

  if (!res.ok) {
    const body = await safeParseJson(res);
    const detail = extractDetailMessage(body);
    throw new UploadError(
      res.status,
      typeof detail === "string" ? detail : `Failed to fetch upload token state: HTTP ${res.status}`,
      detail
    );
  }

  const body = await safeParseJson(res);
  if (body === null) {
    throw new UploadError(res.status, `Invalid JSON in upload token state response`, null);
  }

  return UploadTokenStateSchema.parse(body);
}

/**
 * Submit blood report files for a given upload token. Builds a
 * `multipart/form-data` body with one repeated `files` field per file (the
 * shape the backend's `files: list[UploadFile]` parameter expects) and POSTs
 * it unauthenticated to the same-origin BFF proxy — no `Content-Type` header
 * is set explicitly so the browser attaches the correct multipart boundary.
 *
 * Returns:
 * - `UploadFilesResponse` (HTTP 201) — upload genuinely succeeded. Per backend
 *   Decision D-2, this response deliberately never reveals whether
 *   pre-consultation brief generation succeeded — from the Lead's point of
 *   view the upload always succeeded once this is returned.
 * - `UploadTokenState` (HTTP 200) — the token was not_found/expired/used;
 *   no files were processed. `state` is never "valid" in this branch.
 *
 * Throws:
 * - `UploadValidationError` (422) — batch/file validation failure.
 * - `UploadRateLimitError` (429) — rate limited.
 * - `UploadRetryableError` (503) — R2 write failed mid-batch; link still valid, retry-safe.
 * - `UploadError` — network error, other non-2xx status, or unparseable body.
 */
export async function uploadLeadFiles(token: string, files: File[]): Promise<UploadFilesResult> {
  const url = `${API_URL}/api/upload/${encodeURIComponent(token)}/files`;

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new UploadError(0, `Network error uploading files for token`, null);
  }

  if (res.status === 422) {
    const body = await safeParseJson(res);
    throw new UploadValidationError(body);
  }

  if (res.status === 429) {
    const body = await safeParseJson(res);
    throw new UploadRateLimitError(body);
  }

  if (res.status === 503) {
    const body = await safeParseJson(res);
    throw new UploadRetryableError(body);
  }

  if (!res.ok) {
    const body = await safeParseJson(res);
    const detail = extractDetailMessage(body);
    throw new UploadError(
      res.status,
      typeof detail === "string" ? detail : `Failed to upload files: HTTP ${res.status}`,
      detail
    );
  }

  const body = await safeParseJson(res);
  if (body === null) {
    throw new UploadError(res.status, `Invalid JSON in upload response`, null);
  }

  if (res.status === 201) {
    return UploadFilesResponseSchema.parse(body);
  }

  // res.status === 200 — token resolved to not_found/expired/used before any
  // file was processed (see module docstring). Shares the GET endpoint's schema.
  return UploadTokenStateSchema.parse(body);
}
