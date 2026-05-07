"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { buttonVariants } from "@/components/ui/button";
import { createSession } from "@/lib/api/sessions";
import { getClient, type ClientDetailOut } from "@/lib/api/clients";
import { useEffect } from "react";

export default function NewSessionPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const router = useRouter();
  const [client, setClient] = useState<ClientDetailOut | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientId) return;
    getClient(clientId).then(setClient).catch(() => {});
  }, [clientId]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const fd = new FormData(e.currentTarget);
    const scheduledRaw = fd.get("scheduled_at") as string;
    const sessionNumberRaw = (fd.get("session_number") as string).trim();

    if (!scheduledRaw || !sessionNumberRaw) {
      setError("All fields are required.");
      setSubmitting(false);
      return;
    }

    const session_number = parseInt(sessionNumberRaw, 10);
    if (isNaN(session_number) || session_number < 1) {
      setError("Session number must be a positive integer.");
      setSubmitting(false);
      return;
    }

    try {
      const session = await createSession({
        client_id: clientId,
        session_number,
        scheduled_at: new Date(scheduledRaw).toISOString(),
      });
      router.push(`/clients/${clientId}/sessions/${session.id}`);
    } catch {
      setError("Could not create session. Please try again.");
      setSubmitting(false);
    }
  }

  const now = new Date();
  const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);

  return (
    <div className="max-w-lg space-y-8">
      <div>
        <Link
          href={`/clients/${clientId}`}
          className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
        >
          ← {client?.full_name ?? "Client"}
        </Link>
        <h1 className="mt-3 font-heading text-4xl font-black text-foreground">
          New session
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-1.5">
          <Label
            htmlFor="session_number"
            className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
          >
            Session number *
          </Label>
          <Input
            id="session_number"
            name="session_number"
            type="number"
            min="1"
            required
            placeholder="e.g. 1"
          />
        </div>

        <div className="space-y-1.5">
          <Label
            htmlFor="scheduled_at"
            className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
          >
            Scheduled at *
          </Label>
          <Input
            id="scheduled_at"
            name="scheduled_at"
            type="datetime-local"
            required
            defaultValue={localIso}
          />
        </div>

        {error && <p className="font-sans text-sm text-destructive">{error}</p>}

        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" variant="accent" disabled={submitting}>
            {submitting ? "Creating…" : "Start session"}
          </Button>
          <Link
            href={`/clients/${clientId}`}
            className={buttonVariants({ variant: "ghost" })}
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
