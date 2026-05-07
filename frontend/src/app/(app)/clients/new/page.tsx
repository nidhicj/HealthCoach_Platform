"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { buttonVariants } from "@/components/ui/button";
import { createClient } from "@/lib/api/clients";

const JOURNEY_STAGES = [
  { value: "onboarding", label: "Onboarding" },
  { value: "active", label: "Active" },
  { value: "plateau", label: "Plateau" },
  { value: "off_track", label: "Off track" },
  { value: "completed", label: "Completed" },
];

export default function NewClientPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const fd = new FormData(e.currentTarget);
    const full_name = (fd.get("full_name") as string).trim();

    if (!full_name) {
      setError("Name is required.");
      setSubmitting(false);
      return;
    }

    try {
      const client = await createClient({
        full_name,
        email: (fd.get("email") as string).trim() || undefined,
        phone: (fd.get("phone") as string).trim() || undefined,
        journey_stage: (fd.get("journey_stage") as string) || "onboarding",
        course_goal: (fd.get("course_goal") as string).trim() || undefined,
      });
      router.push(`/clients/${client.id}`);
    } catch {
      setError("Could not create client. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-lg space-y-8">
      {/* Page header */}
      <div>
        <Link
          href="/clients"
          className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
        >
          ← Clients
        </Link>
        <h1 className="mt-3 font-heading text-4xl font-black text-foreground">
          New client
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Full name */}
        <div className="space-y-1.5">
          <Label htmlFor="full_name" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Full name *
          </Label>
          <Input id="full_name" name="full_name" required placeholder="e.g. Ananya Krishnan" />
        </div>

        {/* Email */}
        <div className="space-y-1.5">
          <Label htmlFor="email" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Email
          </Label>
          <Input id="email" name="email" type="email" placeholder="client@example.com" />
        </div>

        {/* Phone */}
        <div className="space-y-1.5">
          <Label htmlFor="phone" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Phone
          </Label>
          <Input id="phone" name="phone" type="tel" placeholder="+91 98765 43210" />
        </div>

        {/* Journey stage */}
        <div className="space-y-1.5">
          <Label htmlFor="journey_stage" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Journey stage
          </Label>
          <select
            id="journey_stage"
            name="journey_stage"
            defaultValue="onboarding"
            className="flex h-8 w-full rounded-lg border border-input bg-background px-3 py-1 font-sans text-sm text-foreground outline-none focus:border-ring focus:ring-3 focus:ring-ring/50"
          >
            {JOURNEY_STAGES.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* Course goal */}
        <div className="space-y-1.5">
          <Label htmlFor="course_goal" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Goal
          </Label>
          <Input
            id="course_goal"
            name="course_goal"
            placeholder="e.g. Lose 8 kg and build a sustainable routine"
          />
        </div>

        {error && (
          <p className="font-sans text-sm text-destructive">{error}</p>
        )}

        <div className="flex items-center gap-3 pt-2">
          {/* Marigold on the primary submit — the keystone action on this screen */}
          <Button type="submit" variant="accent" disabled={submitting}>
            {submitting ? "Creating…" : "Create client"}
          </Button>
          <Link
            href="/clients"
            className={buttonVariants({ variant: "ghost" })}
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
