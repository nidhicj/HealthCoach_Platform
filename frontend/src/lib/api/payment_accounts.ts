import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

/**
 * HC-authenticated payment-account connection API. Mirrors `settings.ts`'s
 * pattern (`fetchWithAuth`, no `client.ts`-style error subclass hierarchy
 * beyond what's needed here).
 *
 * GET  /api/hc/payment-account          — {"connected": bool}
 * POST /api/hc/payment-account/connect  — verify + store the HC's own
 *                                          Razorpay key_id/key_secret/webhook_secret
 *
 * Mirrors `backend/src/api/payment_accounts.py`'s Pydantic models
 * (`PaymentAccountStatusOut`, `ConnectPaymentAccountIn`) field-for-field. Keep
 * in sync with that file, not with this comment.
 *
 * `credentials` (key_secret, webhook_secret) are write-only from the backend's
 * perspective — no route here ever returns them back, in a success or error
 * response. This client never persists them beyond the single POST body
 * (no localStorage, no logging) — the caller (the settings form) is
 * responsible for clearing its own field state after a successful connect.
 *
 * Error response bodies, confirmed against the real handlers:
 * - POST /connect: 422 `{detail: {error: "invalid_credentials", message}}`,
 *   502 `{detail: {error: "razorpay_unreachable", message}}`. Both structured
 *   `{error, message}` shapes, same convention as `payments.ts`.
 */

export const PaymentAccountStatusSchema = z.object({
  connected: z.boolean(),
});

export type PaymentAccountStatus = z.infer<typeof PaymentAccountStatusSchema>;

export type PaymentAccountErrorCode = "invalid_credentials" | "razorpay_unreachable";

export class PaymentAccountError extends Error {
  constructor(
    public status: number,
    message: string,
    public errorCode?: PaymentAccountErrorCode,
  ) {
    super(message);
    this.name = "PaymentAccountError";
  }
}

async function safeParseJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function extractError(
  body: unknown,
  fallbackStatus: number,
): { message: string; errorCode?: PaymentAccountErrorCode } {
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
      d.error === "invalid_credentials" || d.error === "razorpay_unreachable" ? d.error : undefined;
    return { message, errorCode };
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === "string" && first.msg.trim() !== "") return { message: first.msg };
  }

  return { message: `Request failed: ${fallbackStatus}` };
}

export async function getPaymentAccountStatus(): Promise<PaymentAccountStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/hc/payment-account`);
  if (!res.ok) {
    const body = await safeParseJson(res);
    const { message } = extractError(body, res.status);
    throw new PaymentAccountError(res.status, message);
  }
  return PaymentAccountStatusSchema.parse(await res.json());
}

/**
 * Verify + store the HC's Razorpay credentials. Reconnecting (a second call)
 * overwrites the previously stored credentials — there is no separate
 * "disconnect" flow at this scope, matching the backend's documented
 * behavior.
 *
 * Throws `PaymentAccountError` with `errorCode === "invalid_credentials"`
 * (422) or `"razorpay_unreachable"` (502) for the two documented failure
 * modes; unset for any other unexpected status or network error.
 */
export async function connectPaymentAccount(
  keyId: string,
  keySecret: string,
  webhookSecret: string,
): Promise<PaymentAccountStatus> {
  let res: Response;
  try {
    res = await fetchWithAuth(`${API_URL}/api/hc/payment-account/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key_id: keyId, key_secret: keySecret, webhook_secret: webhookSecret }),
    });
  } catch {
    throw new PaymentAccountError(0, "Network error connecting payment account");
  }

  if (!res.ok) {
    const body = await safeParseJson(res);
    const { message, errorCode } = extractError(body, res.status);
    throw new PaymentAccountError(res.status, message, errorCode);
  }

  return PaymentAccountStatusSchema.parse(await res.json());
}
