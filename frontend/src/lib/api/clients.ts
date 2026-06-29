import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const ClientOutSchema = z.object({
  id: z.string(),
  hc_user_id: z.string(),
  full_name: z.string(),
  code: z.string().nullable(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  timezone: z.string().nullable(),
  journey_stage: z.string(),
  course_start_date: z.string().nullable(),
  course_end_date: z.string().nullable(),
  course_goal: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

const ActionItemOutSchema = z.object({
  id: z.string(),
  description: z.string(),
  due_date: z.string().nullable(),
  status: z.string(),
  created_at: z.string(),
});

export const ClientDetailOutSchema = ClientOutSchema.extend({
  ast: z.null(),
  open_action_items_count: z.number(),
  last_session_at: z.string().nullable(),
});

export const AstOutSchema = z.object({
  open_items: z.array(ActionItemOutSchema),
  missed_items: z.array(ActionItemOutSchema),
  status_summary: z.string(),
  trend_tags: z.array(z.string()),
  triage_flags: z.array(z.string()),
});

export const InviteOutSchema = z.object({
  invite_token: z.string(),
  expires_at: z.string(),
  invite_url: z.string(),
});

const PaginatedClientsSchema = z.object({
  items: z.array(ClientOutSchema),
  next_cursor: z.string().nullable(),
});

export type ClientOut = z.infer<typeof ClientOutSchema>;
export type ClientDetailOut = z.infer<typeof ClientDetailOutSchema>;
export type AstOut = z.infer<typeof AstOutSchema>;
export type InviteOut = z.infer<typeof InviteOutSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export interface CreateClientInput {
  full_name: string;
  email?: string;
  phone?: string;
  timezone?: string;
  journey_stage?: string;
  course_start_date?: string;
  course_end_date?: string;
  course_goal?: string;
}

export async function createClient(input: CreateClientInput): Promise<ClientOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Create client failed: ${res.status}`);
  return ClientOutSchema.parse(await res.json());
}

export async function listClients(params?: {
  limit?: number;
  cursor?: string;
  journey_stage?: string;
}): Promise<{ items: ClientOut[]; next_cursor: string | null }> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.cursor) qs.set("cursor", params.cursor);
  if (params?.journey_stage) qs.set("journey_stage", params.journey_stage);

  const res = await fetchWithAuth(`${API_URL}/api/clients${qs.toString() ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`List clients failed: ${res.status}`);
  return PaginatedClientsSchema.parse(await res.json());
}

export async function getClient(clientId: string): Promise<ClientDetailOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}`);
  if (!res.ok) throw new Error(`Get client failed: ${res.status}`);
  return ClientDetailOutSchema.parse(await res.json());
}

export async function getClientAst(clientId: string): Promise<AstOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/ast`);
  if (!res.ok) throw new Error(`Get AST failed: ${res.status}`);
  return AstOutSchema.parse(await res.json());
}

export async function patchClient(
  clientId: string,
  input: { journey_stage?: string },
): Promise<ClientOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Patch client failed: ${res.status}`);
  return ClientOutSchema.parse(await res.json());
}

export async function createInvite(clientId: string): Promise<InviteOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/invite`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Create invite failed: ${res.status}`);
  return InviteOutSchema.parse(await res.json());
}
