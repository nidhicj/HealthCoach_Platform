"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { redirectToClientInviteFlow } from "@/lib/auth/redirect";

function InviteRedirect() {
  const searchParams = useSearchParams();
  const invite = searchParams.get("invite");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!invite) {
      setError("This invite link looks incomplete.");
      return;
    }
    redirectToClientInviteFlow(invite).catch(() => {
      setError("This invite link is invalid or has expired. Please ask your coach for a new one.");
    });
  }, [invite]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10">
      <div className="flex flex-col items-center gap-3 text-center">
        {/* Fraunces 900 wordmark — headline rule */}
        <h1 className="font-heading text-5xl font-black text-foreground">
          Tapas
        </h1>
        {/* Marigold accent line — the ONE Marigold element on this screen (brand §divider) */}
        <div className="h-0.5 w-16 bg-accent" aria-hidden />
        {error ? (
          <p className="font-sans text-sm text-destructive">{error}</p>
        ) : (
          <p className="font-sans text-base text-muted-foreground">Redirecting…</p>
        )}
      </div>
    </main>
  );
}

export default function InvitePage() {
  return (
    <Suspense fallback={null}>
      <InviteRedirect />
    </Suspense>
  );
}
