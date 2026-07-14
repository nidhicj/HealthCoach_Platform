"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { listMyActionItems, patchMyActionItem } from "@/lib/api/me";
import type { ActionItemOut } from "@/lib/api/actionItems";

export default function ClientHomePage() {
  const router = useRouter();
  const [items, setItems] = useState<ActionItemOut[] | null>(null);
  const [error, setError] = useState(false);
  const [toggleError, setToggleError] = useState(false);
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    listMyActionItems()
      .then((data) => setItems(data.items))
      .catch((err) => {
        // A 403 here means a non-client JWT hit a client-only endpoint
        // (wrong account) — treat like any other auth problem.
        if (err instanceof Error && err.message.includes("403")) {
          router.replace("/sign-in");
          return;
        }
        setError(true);
      });
  }, [router]);

  async function handleToggle(item: ActionItemOut) {
    // Guard against double-click: if already pending, do nothing.
    if (pendingIds.has(item.id)) {
      return;
    }

    setPendingIds((prev) => new Set(prev).add(item.id));
    setToggleError(false);

    try {
      const nextStatus = item.status === "completed" ? "open" : "completed";
      const updated = await patchMyActionItem(item.id, { status: nextStatus });
      setItems((prev) => prev?.map((i) => (i.id === updated.id ? updated : i)) ?? prev);
    } catch (err) {
      // A 403 here means the client's token became invalid mid-session.
      if (err instanceof Error && err.message.includes("403")) {
        router.replace("/sign-in");
        return;
      }
      // Any other error: show inline feedback.
      setToggleError(true);
    } finally {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  }

  const openItems = (items ?? []).filter((i) => i.status !== "completed");

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-3xl font-black text-foreground">
        Your action items
      </h1>

      {error && (
        <p className="font-sans text-sm text-destructive">
          Couldn&rsquo;t load your action items. Try refreshing.
        </p>
      )}

      {toggleError && (
        <p className="font-sans text-sm text-destructive">
          Couldn&rsquo;t update that action item. Try again.
        </p>
      )}

      {!error && items === null && (
        <p className="font-sans text-sm text-muted-foreground">Loading…</p>
      )}

      {!error && items !== null && openItems.length === 0 && (
        <p className="font-sans text-sm text-muted-foreground">
          Nothing open right now — your coach will send new action items after your next session.
        </p>
      )}

      {!error && openItems.length > 0 && (
        <ul className="space-y-3">
          {openItems.map((item) => (
            <li
              key={item.id}
              className="flex items-start justify-between gap-4 rounded-md border p-4"
            >
              <div>
                <p className="font-sans text-sm text-foreground">{item.description}</p>
                {item.due_date && (
                  <p className="mt-1 font-sans text-xs text-muted-foreground">
                    Due {item.due_date}
                  </p>
                )}
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleToggle(item)}
                disabled={pendingIds.has(item.id)}
              >
                {pendingIds.has(item.id) ? "Updating…" : "Mark done"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
