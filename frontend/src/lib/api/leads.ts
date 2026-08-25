import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────
// Mirrors backend/src/api/leads.py's Pydantic response models field-for-field
// (Task 5, PHASE-04). Keep in sync with that file, not with this comment.

export const QuestionAnswerOutSchema = z.object({
  question_key: z.string(),
  question_text: z.string(),
  response_text: z.string().nullable(),
});

export const TestAdditionOutSchema = z.object({
  test: z.string(),
  rationale: z.string(),
});

export const TestRecommendationOutSchema = z.object({
  standard: z.array(z.string()),
  additions: z.array(TestAdditionOutSchema),
  all_tests: z.array(z.string()),
});

export const LeadTestRecommendationOutSchema = z.object({
  lead_id: z.string(),
  full_name: z.string(),
  email: z.string(),
  phone: z.string().nullable(),
  status: z.string(),
  questionnaire_responses: z.array(QuestionAnswerOutSchema),
  // False when `leads.draft_test_recommendation` is still null server-side —
  // shouldn't happen in practice by the time the HC review email fires, but
  // the backend returns a structured response instead of crashing, so this
  // client must handle it too rather than assuming `draft_test_recommendation`
  // is always present.
  ready: z.boolean(),
  draft_test_recommendation: TestRecommendationOutSchema.nullable(),
});

export const SendTestRecommendationOutSchema = z.object({
  lead_id: z.string(),
  status: z.string(),
  test_recommendation: TestRecommendationOutSchema,
});

export type QuestionAnswerOut = z.infer<typeof QuestionAnswerOutSchema>;
export type TestAdditionOut = z.infer<typeof TestAdditionOutSchema>;
export type TestRecommendationOut = z.infer<typeof TestRecommendationOutSchema>;
export type LeadTestRecommendationOut = z.infer<typeof LeadTestRecommendationOutSchema>;
export type SendTestRecommendationOut = z.infer<typeof SendTestRecommendationOutSchema>;

// The HC's edited addition — same shape as `TestAdditionOut` on the wire, kept
// as a separate input type since callers build this list locally (it's not
// something ever parsed off a response).
export interface TestAdditionIn {
  test: string;
  rationale: string;
}

// ── error surfacing ──────────────────────────────────────────────────────────
// FastAPI's two error shapes seen on these routes: the 409 "draft not ready"
// error (`detail: {error, message}` — see `_draft_not_ready_error` in
// leads.py) and the default 422 validation-error shape (`detail: [{msg, ...}]`
// — from `TestAdditionIn`'s `test` field validator). Mirrors the
// `body?.detail?.message` convention from `src/lib/api/leadgen.ts`, extended
// to also read the 422 array shape.
async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message.trim() !== "") return message;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === "string" && first.msg.trim() !== "") return first.msg;
  }
  return `${fallback}: ${res.status}`;
}

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function getLeadTestRecommendation(
  leadId: string,
): Promise<LeadTestRecommendationOut> {
  const res = await fetchWithAuth(`${API_URL}/api/leads/${leadId}/test-recommendation`);
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Get test recommendation failed"));
  return LeadTestRecommendationOutSchema.parse(await res.json());
}

export async function sendLeadTestRecommendation(
  leadId: string,
  additions: TestAdditionIn[],
): Promise<SendTestRecommendationOut> {
  const res = await fetchWithAuth(`${API_URL}/api/leads/${leadId}/test-recommendation/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ additions }),
  });
  if (!res.ok) throw new Error(await extractErrorMessage(res, "Send test recommendation failed"));
  return SendTestRecommendationOutSchema.parse(await res.json());
}
