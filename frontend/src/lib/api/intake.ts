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
 * Error subclasses to allow fine-grained error handling by status code.
 */

export class IntakeError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown
  ) {
    super(message);
    this.name = "IntakeError";
  }
}

export class IntakeNotFoundError extends IntakeError {
  constructor(detail?: unknown) {
    super(404, "Coach not found", detail);
    this.name = "IntakeNotFoundError";
  }
}

export class IntakeDuplicateEmailError extends IntakeError {
  constructor(detail?: unknown) {
    super(409, "Duplicate email submission", detail);
    this.name = "IntakeDuplicateEmailError";
  }
}

export class IntakeValidationError extends IntakeError {
  constructor(detail?: unknown) {
    super(422, "Validation failed", detail);
    this.name = "IntakeValidationError";
  }
}

export class IntakeRateLimitError extends IntakeError {
  constructor(detail?: unknown) {
    super(429, "Rate limit exceeded", detail);
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
      err
    );
  }

  if (res.status === 404) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = null;
    }
    throw new IntakeNotFoundError(detail);
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = null;
    }
    throw new IntakeError(
      res.status,
      `Failed to fetch intake config: HTTP ${res.status}`,
      detail
    );
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch (err) {
    throw new IntakeError(
      res.status,
      `Invalid JSON in intake config response`,
      err
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
      err
    );
  }

  if (res.status === 404) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = null;
    }
    throw new IntakeNotFoundError(detail);
  }

  if (res.status === 409) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = null;
    }
    throw new IntakeDuplicateEmailError(detail);
  }

  if (res.status === 422) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = null;
    }
    throw new IntakeValidationError(detail);
  }

  if (res.status === 429) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = null;
    }
    throw new IntakeRateLimitError(detail);
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = null;
    }
    throw new IntakeError(
      res.status,
      `Failed to submit intake: HTTP ${res.status}`,
      detail
    );
  }

  let responseBody: unknown;
  try {
    responseBody = await res.json();
  } catch (err) {
    throw new IntakeError(
      res.status,
      `Invalid JSON in intake submission response`,
      err
    );
  }

  return IntakeSubmissionResponseSchema.parse(responseBody);
}
