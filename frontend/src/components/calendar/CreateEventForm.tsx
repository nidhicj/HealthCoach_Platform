"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createCalendarEvent, type CalendarEvent } from "@/lib/api/calendar";

const FIELD_LABEL_CLASS = "font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground";

export function CreateEventForm({
  onCreated,
  onCancel,
}: {
  onCreated: (event: CalendarEvent) => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const startId = useId();
  const endId = useId();
  const meetId = useId();

  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [addMeet, setAddMeet] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const event = await createCalendarEvent({
        summary: title.trim(),
        start: new Date(start).toISOString(),
        end: new Date(end).toISOString(),
        add_meet: addMeet,
      });
      onCreated(event);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create event. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor={titleId} className={FIELD_LABEL_CLASS}>
          Title
        </Label>
        <Input
          id={titleId}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          placeholder="e.g. 1:1 session"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={startId} className={FIELD_LABEL_CLASS}>
            Start
          </Label>
          <Input
            id={startId}
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={endId} className={FIELD_LABEL_CLASS}>
            End
          </Label>
          <Input
            id={endId}
            type="datetime-local"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            required
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          id={meetId}
          type="checkbox"
          checked={addMeet}
          onChange={(e) => setAddMeet(e.target.checked)}
          className="h-4 w-4 shrink-0 cursor-pointer accent-primary"
        />
        <Label htmlFor={meetId} className="font-sans text-sm font-normal normal-case tracking-normal text-foreground">
          Add Google Meet
        </Label>
      </div>

      {error && <p className="font-sans text-xs text-destructive">{error}</p>}

      <div className="flex items-center gap-2 pt-1">
        <Button type="submit" size="sm" disabled={submitting}>
          {submitting ? "Creating…" : "Create event"}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
