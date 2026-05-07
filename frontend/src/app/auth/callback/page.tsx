"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/config";
import { setToken } from "@/lib/auth/tokens";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // The backend has already set the HttpOnly refresh cookie and redirected here.
    // Exchange it for an access token and navigate to the app.
    fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("refresh failed");
        const data = await res.json();
        setToken(data.access_token);
        router.replace("/dashboard");
      })
      .catch(() => {
        setError("Sign-in failed. Redirecting to sign-in…");
        setTimeout(() => router.replace("/sign-in"), 1800);
      });
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="font-heading text-3xl font-black text-foreground">
        Parivarthan
      </h1>
      {error ? (
        <p className="font-sans text-sm text-destructive">{error}</p>
      ) : (
        <p className="font-sans text-sm text-muted-foreground">
          Signing you in…
        </p>
      )}
    </main>
  );
}
