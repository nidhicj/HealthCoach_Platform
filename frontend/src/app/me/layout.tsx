"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/config";
import { getToken, setToken } from "@/lib/auth/tokens";

type AuthState = "checking" | "authed" | "denied";

export default function ClientPortalLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [auth, setAuth] = useState<AuthState>("checking");

  useEffect(() => {
    if (getToken()) {
      setAuth("authed");
      return;
    }
    fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("unauthenticated");
        const data = await res.json();
        setToken(data.access_token);
        setAuth("authed");
      })
      .catch(() => {
        setAuth("denied");
        router.replace("/sign-in");
      });
  }, [router]);

  if (auth === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-sans text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (auth === "denied") return null;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-background">
        <nav className="mx-auto flex h-12 max-w-2xl items-center px-4 sm:px-6">
          <span className="font-heading text-lg font-black text-foreground">Tapas</span>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}
