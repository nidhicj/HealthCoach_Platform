"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { listMyMessages, sendMyMessage, myMessageAttachmentUrl } from "@/lib/api/me";
import type { MessageOut } from "@/lib/api/messages";
import { AuthedImage } from "@/components/authed-image";

export default function ChatPage() {
  const [messages, setMessages] = useState<MessageOut[] | null>(null);
  const [body, setBody] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    listMyMessages().then((data) => setMessages(data.items.slice().reverse())).catch(() => setMessages([]));
  }, []);

  async function handleSend() {
    if (!body.trim()) return;
    setSending(true);
    setSendError(null);
    try {
      const sent = await sendMyMessage({ body, attachment: attachment ?? undefined });
      setMessages((prev) => [...(prev ?? []), sent]);
      setBody("");
      setAttachment(null);
    } catch {
      setSendError("Message failed to send. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-3xl font-black text-foreground">Chat</h1>

      <div className="max-h-[60vh] space-y-3 overflow-y-auto">
        {messages === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}
        {messages !== null && messages.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">No messages yet — say hello!</p>
        )}
        {messages?.map((m) => (
          <div
            key={m.id}
            className={`max-w-[85%] rounded-md border p-3 font-sans text-sm ${
              m.direction === "client" ? "ml-auto border-primary/30 bg-primary/5" : "border-border"
            }`}
          >
            <p>{m.body}</p>
            {m.has_attachment && (
              <AuthedImage
                url={myMessageAttachmentUrl(m.id)}
                alt={m.attachment_original_filename ?? "attachment"}
                className="mt-2 max-h-48 rounded"
              />
            )}
            <p className="mt-1 text-xs text-muted-foreground">{new Date(m.sent_at).toLocaleString()}</p>
          </div>
        ))}
      </div>

      {sendError && <p className="font-sans text-sm text-destructive">{sendError}</p>}

      <div className="flex gap-2">
        <input
          type="text" value={body} onChange={(e) => setBody(e.target.value)}
          placeholder="Type a message…"
          className="flex-1 rounded-md border border-border px-3 py-2 font-sans text-sm"
        />
        <input
          type="file" accept="image/jpeg,image/png,image/webp,image/heic"
          onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
          className="w-32 font-sans text-xs"
        />
        <Button onClick={handleSend} disabled={sending || !body.trim()}>
          {sending ? "Sending…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
