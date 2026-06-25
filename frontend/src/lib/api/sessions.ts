import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const SessionOutSchema = z.object({
  id: z.string(),
  hc_user_id: z.string(),
  client_id: z.string(),
  session_number: z.number(),
  scheduled_at: z.string(),
  started_at: z.string().nullable(),
  ended_at: z.string().nullable(),
  zoom_meeting_id: z.string().nullable(),
  notes_internal: z.string().nullable(),
  session_notes: z.string().nullable(),
  created_at: z.string(),
});

export const MomOutSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  client_id: z.string(),
  draft_text: z.string(),
  final_text: z.string().nullable(),
  status: z.string(),
  llm_call_id: z.string().nullable(),
  sent_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const BriefOutSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  client_id: z.string(),
  brief_text: z.string(),
  triage_flags: z.array(z.string()).nullable(),
  llm_call_id: z.string().nullable(),
  generated_at: z.string(),
});

const PaginatedSessionsSchema = z.object({
  items: z.array(SessionOutSchema),
  next_cursor: z.string().nullable(),
});

export type SessionOut = z.infer<typeof SessionOutSchema>;
export type MomOut = z.infer<typeof MomOutSchema>;
export type BriefOut = z.infer<typeof BriefOutSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function createSession(input: {
  client_id: string;
  session_number: number;
  scheduled_at: string;
  zoom_meeting_id?: string;
  notes_internal?: string;
}): Promise<SessionOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Create session failed: ${res.status}`);
  return SessionOutSchema.parse(await res.json());
}

export async function listSessions(params?: {
  client_id?: string;
  limit?: number;
  cursor?: string;
}): Promise<{ items: SessionOut[]; next_cursor: string | null }> {
  const qs = new URLSearchParams();
  if (params?.client_id) qs.set("client_id", params.client_id);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.cursor) qs.set("cursor", params.cursor);

  const res = await fetchWithAuth(`${API_URL}/api/sessions${qs.toString() ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`List sessions failed: ${res.status}`);
  return PaginatedSessionsSchema.parse(await res.json());
}

export async function getSession(sessionId: string): Promise<SessionOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Get session failed: ${res.status}`);
  return SessionOutSchema.parse(await res.json());
}

export async function patchSession(
  sessionId: string,
  input: { session_notes?: string },
): Promise<SessionOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Patch session failed: ${res.status}`);
  return SessionOutSchema.parse(await res.json());
}

export async function endSession(sessionId: string): Promise<SessionOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/end`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`End session failed: ${res.status}`);
  return SessionOutSchema.parse(await res.json());
}

export async function getBrief(sessionId: string): Promise<BriefOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/brief`);
  if (!res.ok) throw new Error(`Get brief failed: ${res.status}`);
  return BriefOutSchema.parse(await res.json());
}

export async function getMom(sessionId: string): Promise<MomOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/mom`);
  if (!res.ok) throw new Error(`Get MOM failed: ${res.status}`);
  return MomOutSchema.parse(await res.json());
}

export async function draftMom(
  sessionId: string,
  session_notes: string,
): Promise<MomOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/mom/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_notes }),
  });
  if (!res.ok) throw new Error(`Draft MOM failed: ${res.status}`);
  return MomOutSchema.parse(await res.json());
}

export async function patchMom(
  sessionId: string,
  input: { draft_text?: string; final_text?: string; status?: string },
): Promise<MomOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/mom`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Patch MOM failed: ${res.status}`);
  return MomOutSchema.parse(await res.json());
}

export async function sendMom(sessionId: string): Promise<MomOut> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/mom/send`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Send MOM failed: ${res.status}`);
  return MomOutSchema.parse(await res.json());
}
