import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const ClientFileOutSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  original_filename: z.string(),
  storage_path: z.string(),
  mime_type: z.string(),
  size_bytes: z.number(),
  uploaded_at: z.string(),
  is_zoom_summary: z.boolean(),
});

export type ClientFileOut = z.infer<typeof ClientFileOutSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function uploadFiles(
  sessionId: string,
  files: File[],
  isZoomSummary = false,
): Promise<ClientFileOut[]> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  form.append("is_zoom_summary", String(isZoomSummary));

  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/files`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Upload files failed: ${res.status}`);
  return z.array(ClientFileOutSchema).parse(await res.json());
}

export async function listFiles(sessionId: string): Promise<ClientFileOut[]> {
  const res = await fetchWithAuth(`${API_URL}/api/sessions/${sessionId}/files`);
  if (!res.ok) throw new Error(`List files failed: ${res.status}`);
  return z.array(ClientFileOutSchema).parse(await res.json());
}

export async function deleteFile(
  sessionId: string,
  fileId: string,
): Promise<void> {
  const res = await fetchWithAuth(
    `${API_URL}/api/sessions/${sessionId}/files/${fileId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Delete file failed: ${res.status}`);
}
