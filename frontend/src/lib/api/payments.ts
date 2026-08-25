import { z } from "zod";
import { API_URL } from "@/lib/config";

/**
 * Public Lead-facing payment API — unauthenticated endpoints via same-origin BFF
 * proxy (mirrors `upload.ts`/`intake.ts`'s pattern: plain `fetch()`, no
 * `fetchWithAuth` wrapper). No auth header is ever attached — these endpoints
 * are resolved by the Lead's raw `id` (a UUID) mailed to them, not a bearer
 * token (see `backend/src/api/payments.py`'s module docstring for why that's a
 * deliberate simplification for this pair of routes specifically).
 *
 * GET  /api/leads/{id}/payment        — payment context for the "book & pay" page
 * POST /api/leads/{id}/payment/order  — create (or return the already-pending)
 *                                        Razorpay Order
 *
 * Mirrors `backend/src/api/payments.py`'s Pydantic response models
 * (`LeadPaymentContextOut`, `CreatePaymentOrderOut`) field-for-field. Keep in
 * sync with that file, not with this comment.
 *
 * Error response bodies, confirmed against the real handlers (not guessed):
 * - GET's only documented failure is 404 `{detail: "Not found"}` — a plain
 *   string `detail`, per `_lead_not_found_error()` (same "generic 404, no
 *   detail leaked" convention as `intake.ts`'s `get_intake_config`).
 * - POST's business-state failures are all `{detail: {error, message}}`:
 *   409 `already_paid` (`_already_paid_error`), 409 `payment_not_available`
 *   (`_payment_not_available_error`), 502 `razorpay_unreachable`
 *   (`_razorpay_unreachable_error`). POST can also 404 the same way GET does
 *   if the Lead itself doesn't resolve.
 *
 * `extractError` below handles both shapes (plain string `detail`, and
 * `{error, message}` object `detail`) so both endpoints can share one error
 * path. `PaymentError.errorCode` is only ever set for the structured 409/502
 * cases above — callers that need to distinguish `already_paid` from
 * `payment_not_available` from `razorpay_unreachable` read it there rather
 * than pattern-matching on `.message` text.
 */

export const LeadPaymentContextSchema = z.object({
  hc_name: z.string(),
  consultation_fee_inr: z.number().nullable(),
  payment_status: z.string(),
  // Present ONLY once payment_status === "paid" (backend withholds it until
  // then — see LeadPaymentContextOut's docstring). Optional AND nullable so a
  // response that omits the field entirely (Pydantic's `= None` default) and
  // one that sends `null` explicitly both parse cleanly.
  scheduling_link: z.string().nullable().optional(),
});

export type LeadPaymentContext = z.infer<typeof LeadPaymentContextSchema>;

export const CreatePaymentOrderSchema = z.object({
  order_id: z.string(),
  key_id: z.string(),
  amount_paise: z.number(),
});

export type CreatePaymentOrder = z.infer<typeof CreatePaymentOrderSchema>;

/**
 * The three structured error codes this pair of routes can return
 * (`POST .../payment/order` only — GET never returns a structured `error`
 * code, only ever a plain-string 404). See module docstring.
 */
export type PaymentErrorCode = "already_paid" | "payment_not_available" | "razorpay_unreachable";

export class PaymentError extends Error {
  constructor(
    public status: number,
    message: string,
    public errorCode?: PaymentErrorCode,
  ) {
    super(message);
    this.name = "PaymentError";
  }
}

async function safeParseJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function extractError(body: unknown, fallbackStatus: number): { message: string; errorCode?: PaymentErrorCode } {
  const detail = (body as { detail?: unknown } | null)?.detail;

  if (typeof detail === "string" && detail.trim() !== "") {
    return { message: detail };
  }

  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as { error?: unknown; message?: unknown };
    const message =
      typeof d.message === "string" && d.message.trim() !== ""
        ? d.message
        : `Request failed: ${fallbackStatus}`;
    const errorCode =
      d.error === "already_paid" || d.error === "payment_not_available" || d.error === "razorpay_unreachable"
        ? d.error
        : undefined;
    return { message, errorCode };
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === "string" && first.msg.trim() !== "") return { message: first.msg };
  }

  return { message: `Request failed: ${fallbackStatus}` };
}

/**
 * Fetch payment context for the Lead's "book & pay" page. Safe to call any
 * number of times — read-only, no order-creation side effect (per the
 * backend's own docstring for this route).
 *
 * Throws `PaymentError` on a network failure, non-2xx response (404 if the
 * Lead doesn't resolve), or an unparseable body. `errorCode` is never set on
 * errors from this function (see module docstring).
 */
export async function getLeadPaymentContext(leadId: string): Promise<LeadPaymentContext> {
  const url = `${API_URL}/api/leads/${encodeURIComponent(leadId)}/payment`;
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    throw new PaymentError(0, "Network error loading payment details");
  }

  if (!res.ok) {
    const body = await safeParseJson(res);
    const { message } = extractError(body, res.status);
    throw new PaymentError(res.status, message);
  }

  const body = await safeParseJson(res);
  if (body === null) throw new PaymentError(res.status, "Invalid response loading payment details");
  return LeadPaymentContextSchema.parse(body);
}

/**
 * Create a Razorpay Order for this Lead's consultation fee, or fetch the
 * already-pending one back (backend's reload-idempotency — see
 * `create_payment_order`'s docstring). Never mints a second real order once
 * `payment_status == "paid"` — that case comes back as a `PaymentError` with
 * `errorCode === "already_paid"` instead.
 *
 * Throws `PaymentError` with `errorCode` set to `"already_paid"`,
 * `"payment_not_available"`, or `"razorpay_unreachable"` for the three
 * documented business-state failures; unset for a 404 (Lead doesn't resolve),
 * network error, or any other unexpected status.
 */
export async function createPaymentOrder(leadId: string): Promise<CreatePaymentOrder> {
  const url = `${API_URL}/api/leads/${encodeURIComponent(leadId)}/payment/order`;
  let res: Response;
  try {
    res = await fetch(url, { method: "POST" });
  } catch {
    throw new PaymentError(0, "Network error starting payment");
  }

  if (!res.ok) {
    const body = await safeParseJson(res);
    const { message, errorCode } = extractError(body, res.status);
    throw new PaymentError(res.status, message, errorCode);
  }

  const body = await safeParseJson(res);
  if (body === null) throw new PaymentError(res.status, "Invalid response starting payment");
  return CreatePaymentOrderSchema.parse(body);
}
