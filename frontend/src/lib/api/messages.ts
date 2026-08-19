import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

export const MessageOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  hc_user_id: z.string(),
  direction: z.enum(["client", "coach"]),
  body: z.string(),
  has_attachment: z.boolean(),
  attachment_original_filename: z.string().nullable(),
  attachment_mime_type: z.string().nullable(),
  sent_at: z.string(),
});

export type MessageOut = z.infer<typeof MessageOutSchema>;

const PaginatedMessagesSchema = z.object({
  items: z.array(MessageOutSchema),
  next_cursor: z.string().nullable(),
});

export async function listClientMessages(clientId: string): Promise<{ items: MessageOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/messages`);
  if (!res.ok) throw new Error(`List messages failed: ${res.status}`);
  return PaginatedMessagesSchema.parse(await res.json());
}

export async function sendClientMessage(
  clientId: string,
  input: { body: string; attachment?: File },
): Promise<MessageOut> {
  const form = new FormData();
  form.append("body", input.body);
  if (input.attachment) form.append("attachment", input.attachment);

  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/messages`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Send message failed: ${res.status}`);
  return MessageOutSchema.parse(await res.json());
}

export function messageAttachmentUrl(clientId: string, messageId: string): string {
  return `${API_URL}/api/clients/${clientId}/messages/${messageId}/attachment`;
}
