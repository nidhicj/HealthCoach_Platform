"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { API_URL } from "@/lib/config";
import { getToken, setToken } from "@/lib/auth/tokens";
import { cn } from "@/lib/utils";

type AuthState = "checking" | "authed" | "denied";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/action-items", label: "Action Items" },
  { href: "/settings/diet-chart-templates", label: "Diet Charts" },
  { href: "/settings/sessions", label: "Settings" },
] as const;

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
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
        <nav className="mx-auto flex h-12 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <Link
            href="/dashboard"
            className="shrink-0 font-heading text-lg font-black text-foreground"
          >
            Parivarthan
          </Link>
          {/* overflow-x-auto keeps nav from expanding <html> width on 375px screens */}
          <div className="flex min-w-0 flex-1 items-center justify-end gap-3 overflow-x-auto sm:gap-6">
            {NAV_LINKS.map(({ href, label }) => {
              const active = pathname?.startsWith(href) ?? false;
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "shrink-0 font-sans text-xs font-bold uppercase tracking-widest transition-colors duration-150",
                    active
                      ? "text-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}
