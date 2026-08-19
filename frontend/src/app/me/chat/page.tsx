"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { listMyMessages, sendMyMessage, myMessageAttachmentUrl } from "@/lib/api/me";
import type { MessageOut } from "@/lib/api/messages";
import { AuthedImage } from "@/components/authed-image";
import {
  listMyMealLogs,
  submitMyMealLog,
  myMealLogPhotoUrl,
  MEAL_SLOTS,
  MEAL_SLOT_LABELS,
  type MealLogOut,
  type MealSlot,
} from "@/lib/api/mealLogs";
import { groupMealLogsByDay, formatDayHeading } from "@/components/meal-logs/groupByDay";
import { MealCard } from "@/components/meal-logs/MealCard";

export default function ChatPage() {
  const [subTab, setSubTab] = useState("text");

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-3xl font-black text-foreground">Chat</h1>

      <Tabs value={subTab} onValueChange={setSubTab}>
        <TabsList variant="line">
          <TabsTrigger value="text">Text</TabsTrigger>
          <TabsTrigger value="meals">Logged Meals</TabsTrigger>
        </TabsList>
        <TabsContent value="text">
          <TextView />
        </TabsContent>
        <TabsContent value="meals">
          <MyMealLogsView />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TextView() {
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

export function MyMealLogsView() {
  const [mealLogs, setMealLogs] = useState<MealLogOut[] | null>(null);
  const [mealSlot, setMealSlot] = useState<MealSlot>("breakfast");
  const [description, setDescription] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMyMealLogs().then((data) => setMealLogs(data.items)).catch(() => setMealLogs([]));
  }, []);

  async function handleSubmit() {
    if (!photo) {
      setError("A photo is required to log a meal.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await submitMyMealLog({ mealSlot, description: description || undefined, photo });
      setMealLogs((prev) => [created, ...(prev ?? [])]);
      setDescription("");
      setPhoto(null);
    } catch {
      setError("Couldn't save that meal log. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const groups = mealLogs ? groupMealLogsByDay(mealLogs) : [];

  return (
    <div className="space-y-8">
      <div className="space-y-3 rounded-md border p-4">
        <p className="font-sans text-sm font-bold text-foreground">Log a meal</p>
        <div className="flex flex-wrap gap-2">
          {MEAL_SLOTS.map((slot) => (
            <button
              key={slot}
              onClick={() => setMealSlot(slot)}
              className={`rounded-full border px-3 py-1 font-sans text-xs ${
                mealSlot === slot ? "border-primary bg-primary text-primary-foreground" : "border-border text-foreground"
              }`}
            >
              {MEAL_SLOT_LABELS[slot]}
            </button>
          ))}
        </div>
        <input
          type="file" accept="image/jpeg,image/png,image/webp,image/heic" capture="environment"
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
          className="font-sans text-xs"
        />
        <textarea
          value={description} onChange={(e) => setDescription(e.target.value)}
          placeholder="What did you eat? (optional)"
          className="w-full rounded-md border border-border p-2 font-sans text-sm"
        />
        {error && <p className="font-sans text-sm text-destructive">{error}</p>}
        {/* Deliberately NOT disabled on !photo (PHASE-03 final review, found while
            writing Finding I2.3's test): handleSubmit's own "A photo is required"
            inline validation is otherwise dead code — a disabled button never
            fires onClick, so a client could never see that message, matching the
            existing (pre-fixme) e2e test's expectation that clicking with no
            photo attached surfaces the inline error. */}
        <Button onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Saving…" : "Log meal"}
        </Button>
      </div>

      <div className="space-y-8">
        {mealLogs === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}
        {mealLogs !== null && mealLogs.length === 0 && (
          <p className="font-sans text-sm italic text-muted-foreground">No meals logged yet.</p>
        )}
        {groups.map(({ day, entries }) => (
          <div key={day} className="space-y-3">
            <h3 className="font-heading text-sm font-bold text-foreground">
              {formatDayHeading(day)}
            </h3>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {entries.map((meal) => (
                // Reaction hidden from clients by default — no product decision has
                // authorized showing it; see PHASE-03 final review Finding I4.
                <MealCard key={meal.id} meal={meal} photoUrl={myMealLogPhotoUrl(meal.id)} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
