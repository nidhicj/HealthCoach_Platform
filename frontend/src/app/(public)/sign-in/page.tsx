"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { redirectToGoogle } from "@/lib/auth/redirect";

export default function SignInPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSignIn() {
    setLoading(true);
    setError(null);
    try {
      await redirectToGoogle();
      // Browser navigates away — no need to reset loading
    } catch {
      setError("Could not start sign-in. Please try again.");
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10">
      <div className="flex flex-col items-center gap-3 text-center">
        {/* Fraunces 900 wordmark — headline rule */}
        <h1 className="font-heading text-5xl font-black text-foreground">
          Parivarthan
        </h1>
        {/* Marigold accent line — the ONE Marigold element on this screen (brand §divider) */}
        <div className="h-0.5 w-16 bg-accent" aria-hidden />
        <p className="font-sans text-base text-muted-foreground">
          Your health coaching companion
        </p>
      </div>

      <div className="flex flex-col items-center gap-3">
        <Button
          onClick={handleSignIn}
          disabled={loading}
          size="lg"
          className="min-w-48"
        >
          {loading ? "Redirecting…" : "Continue with Google"}
        </Button>
        {error && (
          <p className="font-sans text-sm text-destructive">{error}</p>
        )}
      </div>
    </main>
  );
}
