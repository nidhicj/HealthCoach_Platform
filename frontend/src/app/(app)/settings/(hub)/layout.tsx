"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { logout } from "@/lib/api/auth";
import { clearToken } from "@/lib/auth/tokens";

// "Payments" nav placement is PROVISIONAL (PHASE-05 Task 7) — SoJo's
// confirmation was requested but unavailable during that task's autonomous
// execution run; built at the brief's recommended default (a hub-level entry,
// not nested under /settings/onboarding) so it's reachable by
// Unit_004_OneStopSpot's future F4 work too, per SPEC-0001's Shared surfaces
// convention. Flagged in that task's report — do not treat this placement as
// final without SoJo's sign-off.
const SETTINGS_SECTIONS = [
  { href: "/settings/profile", label: "Profile" },
  { href: "/settings/onboarding", label: "Onboarding" },
  { href: "/settings/payments", label: "Payments" },
] as const;

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    setSigningOut(true);
    try {
      await logout();
      clearToken();
      router.replace("/sign-in");
    } catch {
      setSigningOut(false);
    }
  }

  return (
    <div className="flex flex-col gap-8 sm:flex-row sm:gap-12">
      <aside className="shrink-0 sm:w-48">
        <nav className="flex flex-row gap-1 overflow-x-auto sm:flex-col sm:overflow-visible">
          {SETTINGS_SECTIONS.map(({ href, label }) => {
            const active = pathname?.startsWith(href) ?? false;
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "shrink-0 rounded-md px-3 py-2 font-sans text-sm font-bold transition-colors duration-150",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {label}
              </Link>
            );
          })}
          <div className="my-2 hidden border-t border-border sm:block" />
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className="shrink-0 rounded-md px-3 py-2 text-left font-sans text-sm font-bold text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-destructive disabled:opacity-50"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </nav>
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
