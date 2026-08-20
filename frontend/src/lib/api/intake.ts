import { z } from "zod";
import { API_URL } from "@/lib/config";

/**
 * Public intake API — unauthenticated endpoints via same-origin BFF proxy.
 *
 * GET  /api/intake/{hc_slug}  — fetch HC name, photo, and questionnaire config
 * POST /api/intake/{hc_slug}  — submit intake form responses (creates a Lead)
 *
 * Error handling distinguishes 404 (not found), 409 (duplicate email),
 * 422 (validation error), 429 (rate limited), and generic network/5xx errors.
 *
 * Error response bodies (404, 409, 429) follow FastAPI's format: {detail: string}.
 * 422 responses can be either:
 * - {detail: string} — from our custom IntakeSubmissionIn validation
 * - {detail: string[]} — from our custom _validate_intake_responses errors
 * - {detail: [{type, loc, msg, input}, ...]} — from FastAPI's native RequestValidationError
 *   when Pydantic validation fails (e.g., malformed JSON, bad consent_ack type)
 * The detail field is unwrapped into each error's message and detail properties
 * so callers can render backend-specific copy without re-parsing the response body.
 */

const QuestionSchema = z.object({
  key: z.string(),
  text: z.string(),
  type: z.enum(["free_text", "multiple_choice", "scale"]),
  required: z.boolean(),
  removable: z.boolean(),
  options: z.array(z.string()).optional(),
});

export type Question = z.infer<typeof QuestionSchema>;

const IntakeConfigSchema = z.object({
  hc_name: z.string(),
  hc_photo_url: z.string().nullable(),
  questionnaire: z.array(QuestionSchema),
});

export type IntakeConfig = z.infer<typeof IntakeConfigSchema>;

const IntakeSubmissionResponseSchema = z.object({
  lead_id: z.string().uuid(),
  status: z.string(),
});

export type IntakeSubmissionResponse = z.infer<typeof IntakeSubmissionResponseSchema>;

/**
 * Helper to safely parse JSON from a response, returning the body or null on parse failure.
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
 * Handles three possible detail shapes:
 * 1. string — from 404/409/429 or some 422 responses
 * 2. string[] — from our custom validation error list
 * 3. {msg: string, type?, loc?, input?}[] — from FastAPI's RequestValidationError
 *
 * Returns:
 * - string: a single message
 * - string[]: array of message strings (for structured error access)
 * - null: if detail field is missing or unparseable
 *
 * Never returns [object Object] strings; invalid shapes are treated as null.
 */
function extractDetailMessage(
  body: unknown
): string | string[] | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as Record<string, unknown>).detail;

  // Case 1: string
  if (typeof detail === "string") return detail;

  // Case 2 & 3: array — could be string[] or validation error object[]
  if (Array.isArray(detail)) {
    // Check if it's a string array (our custom validation errors)
    if (detail.every((d) => typeof d === "string")) {
      return detail;
    }

    // Check if it's FastAPI's RequestValidationError shape: array of {msg, type, loc, input}
    if (detail.every((d) => typeof d === "object" && d !== null && "msg" in d)) {
      const messages = (detail as Array<{ msg?: unknown }>)
        .map((err) => (typeof err.msg === "string" ? err.msg : "Invalid request"))
        .filter((msg) => msg);
      return messages.length > 0 ? messages : null;
    }

    // Array but neither all-strings nor validation errors — treat as unparseable
    return null;
  }

  return null;
}

/**
 * Error subclasses to allow fine-grained error handling by status code.
 * Each class unwraps the `detail` field from the FastAPI response body
 * and sets it as the error's message and detail property.
 */

export class IntakeError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: string | string[] | null
  ) {
    super(message);
    this.name = "IntakeError";
  }
}

export class IntakeNotFoundError extends IntakeError {
  constructor(body?: unknown) {
    const detail = extractDetailMessage(body);
    const message = typeof detail === "string" ? detail : "Coach not found";
    super(404, message, detail);
    this.name = "IntakeNotFoundError";
  }
}

export class IntakeDuplicateEmailError extends IntakeError {
  constructor(body?: unknown) {
    const detail = extractDetailMessage(body);
    const message = typeof detail === "string" ? detail : "Duplicate email submission";
    super(409, message, detail);
    this.name = "IntakeDuplicateEmailError";
  }
}

export class IntakeValidationError extends IntakeError {
  constructor(body?: unknown) {
    const detail = extractDetailMessage(body);
    // For 422, detail could be a string or array of error messages
    const message = Array.isArray(detail) ? detail.join("; ") : (typeof detail === "string" ? detail : "Validation failed");
    super(422, message, detail);
    this.name = "IntakeValidationError";
  }
}

export class IntakeRateLimitError extends IntakeError {
  constructor(body?: unknown) {
    const detail = extractDetailMessage(body);
    const message = typeof detail === "string" ? detail : "Rate limit exceeded";
    super(429, message, detail);
    this.name = "IntakeRateLimitError";
  }
}

/**
 * Fetch intake config (HC name, photo, questionnaire) for a given coach slug.
 * Throws IntakeNotFoundError on 404, IntakeError on other failures.
 */
export async function getIntakeConfig(slug: string): Promise<IntakeConfig> {
  const url = `${API_URL}/api/intake/${encodeURIComponent(slug)}`;
  let res: Response;
  try {
    res = await fetch(url);
  } catch (err) {
    throw new IntakeError(
      0,
      `Network error fetching intake config for slug "${slug}"`,
      null
    );
  }

  if (res.status === 404) {
    const body = await safeParseJson(res);
    throw new IntakeNotFoundError(body);
  }

  if (!res.ok) {
    const body = await safeParseJson(res);
    const detail = extractDetailMessage(body);
    throw new IntakeError(
      res.status,
      typeof detail === "string" ? detail : `Failed to fetch intake config: HTTP ${res.status}`,
      detail
    );
  }

  const body = await safeParseJson(res);
  if (body === null) {
    throw new IntakeError(
      res.status,
      `Invalid JSON in intake config response`,
      null
    );
  }

  return IntakeConfigSchema.parse(body);
}

/**
 * Submit intake questionnaire responses. Returns lead_id and status on success (201).
 *
 * Throws:
 * - IntakeNotFoundError (404) if slug doesn't resolve
 * - IntakeDuplicateEmailError (409) if email was already submitted to this HC
 * - IntakeValidationError (422) if consent not acknowledged or required field missing
 * - IntakeRateLimitError (429) if rate limited
 * - IntakeError on other failures
 */
export async function submitIntake(
  slug: string,
  body: { consent_ack: boolean; [key: string]: string | boolean }
): Promise<IntakeSubmissionResponse> {
  const url = `${API_URL}/api/intake/${encodeURIComponent(slug)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new IntakeError(
      0,
      `Network error submitting intake for slug "${slug}"`,
      null
    );
  }

  // Handle each error status code with appropriate error class
  if (res.status === 404) {
    const body = await safeParseJson(res);
    throw new IntakeNotFoundError(body);
  }

  if (res.status === 409) {
    const body = await safeParseJson(res);
    throw new IntakeDuplicateEmailError(body);
  }

  if (res.status === 422) {
    const body = await safeParseJson(res);
    throw new IntakeValidationError(body);
  }

  if (res.status === 429) {
    const body = await safeParseJson(res);
    throw new IntakeRateLimitError(body);
  }

  if (!res.ok) {
    const body = await safeParseJson(res);
    const detail = extractDetailMessage(body);
    throw new IntakeError(
      res.status,
      typeof detail === "string" ? detail : `Failed to submit intake: HTTP ${res.status}`,
      detail
    );
  }

  const responseBody = await safeParseJson(res);
  if (responseBody === null) {
    throw new IntakeError(
      res.status,
      `Invalid JSON in intake submission response`,
      null
    );
  }

  return IntakeSubmissionResponseSchema.parse(responseBody);
}
