"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";
import { logout, revokeAuthSession } from "@/lib/api/auth";
import { clearToken } from "@/lib/auth/tokens";

const AuthSessionSchema = z.object({
  id: z.string(),
  user_agent: z.string().nullable(),
  last_used_at: z.string().nullable(),
  created_at: z.string(),
});
type AuthSession = z.infer<typeof AuthSessionSchema>;

async function listAuthSessions(): Promise<AuthSession[]> {
  const res = await fetchWithAuth(`${API_URL}/api/auth/sessions`);
  if (!res.ok) throw new Error(`List auth sessions failed: ${res.status}`);
  return z.array(AuthSessionSchema).parse(await res.json());
}

export default function SettingsSessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<AuthSession[] | null>(null);
  const [notImplemented, setNotImplemented] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    listAuthSessions()
      .then(setSessions)
      .catch((err: Error) => {
        if (err.message.includes("404") || err.message.includes("405") || err.message.includes("501")) {
          setNotImplemented(true);
        } else {
          setLoadError(true);
        }
      });
  }, []);

  async function handleRevoke(id: string) {
    setRevokingId(id);
    try {
      await revokeAuthSession(id);
      setSessions((prev) => prev?.filter((s) => s.id !== id) ?? prev);
    } finally {
      setRevokingId(null);
    }
  }

  async function handleSignOutEverywhere() {
    setSigningOut(true);
    try {
      await logout();
      clearToken();
      router.replace("/sign-in");
    } catch {
      setSigningOut(false);
    }
  }

  const loading = sessions === null && !notImplemented && !loadError;

  return (
    <div className="max-w-2xl space-y-8">
      {/* Page header */}
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Account
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Active sessions
        </h1>
      </div>

      {/* Sign-out-everywhere — always visible */}
      <div>
        <Button
          variant="outline"
          onClick={handleSignOutEverywhere}
          disabled={signingOut}
        >
          {signingOut ? "Signing out…" : "Sign out everywhere"}
        </Button>
      </div>

      <Separator />

      {/* Session table */}
      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : loadError ? (
        <p className="font-sans text-sm text-destructive">
          Could not load sessions.
        </p>
      ) : notImplemented ? (
        <p className="font-sans text-sm text-muted-foreground">
          Session management is not yet available. Use &ldquo;Sign out everywhere&rdquo; above to clear all sessions.
        </p>
      ) : sessions!.length === 0 ? (
        <p className="font-heading text-lg font-black text-muted-foreground">
          No active sessions found.
        </p>
      ) : (
        <div className="space-y-3">
          <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            {sessions!.length} active {sessions!.length === 1 ? "session" : "sessions"}
          </p>
          <ul className="divide-y divide-border rounded-lg border border-border">
            {sessions!.map((sess) => (
              <li
                key={sess.id}
                className="flex items-center justify-between px-4 py-3 gap-4"
              >
                <div className="space-y-0.5 min-w-0">
                  <p className="font-sans text-sm text-foreground truncate">
                    {sess.user_agent ?? "Unknown device"}
                  </p>
                  <p className="font-sans text-xs text-muted-foreground">
                    {sess.last_used_at
                      ? `Last active ${new Date(sess.last_used_at).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}`
                      : `Created ${new Date(sess.created_at).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}`}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleRevoke(sess.id)}
                  disabled={revokingId === sess.id}
                >
                  {revokingId === sess.id ? "Revoking…" : "Revoke"}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
