"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { listActionItems, patchActionItem, type ActionItemOut } from "@/lib/api/actionItems";
import { listClients, type ClientOut } from "@/lib/api/clients";
import {
  groupByClient,
  MOVE_FORWARD,
  MOVE_BACK,
  type ClientRow,
} from "@/lib/actionItemsKanban";

function isOverdue(item: ActionItemOut): boolean {
  if (item.status === "missed") return true;
  if (!item.due_date) return false;
  return new Date(item.due_date) < new Date(new Date().toDateString());
}

function ItemCard({
  item,
  onMove,
}: {
  item: ActionItemOut;
  onMove: (id: string, newStatus: string) => void;
}) {
  const [transitioning, setTransitioning] = useState(false);
  const overdue = isOverdue(item);
  const forward = MOVE_FORWARD[item.status];
  const back = MOVE_BACK[item.status];

  async function handleMove(targetStatus: string) {
    const originalStatus = item.status;
    onMove(item.id, targetStatus); // optimistic
    setTransitioning(true);
    try {
      await patchActionItem(item.id, { status: targetStatus });
    } catch {
      onMove(item.id, originalStatus); // revert on error
    } finally {
      setTransitioning(false);
    }
  }

  return (
    <div
      className={cn(
        "rounded-lg border p-3 space-y-1.5 text-sm",
        overdue ? "border-destructive/40 bg-destructive/5" : "border-border bg-background",
      )}
    >
      <p
        className={cn(
          "font-sans font-medium leading-snug",
          item.status === "completed"
            ? "line-through text-muted-foreground"
            : "text-foreground",
        )}
      >
        {item.description}
      </p>
      <p
        className={cn(
          "font-sans text-xs",
          overdue ? "font-bold text-destructive" : "text-muted-foreground",
        )}
      >
        {new Date(item.created_at).toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
          year: "numeric",
        })}
        {overdue && " · Overdue"}
      </p>
      {transitioning ? (
        <p className="font-sans text-xs text-muted-foreground">Moving…</p>
      ) : (
        <div className="flex flex-wrap gap-3 pt-0.5">
          {back && (
            <button
              onClick={() => handleMove(back)}
              className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
            >
              {back === "open" ? "← Back to Open" : "← Reopen"}
            </button>
          )}
          {forward && (
            <button
              onClick={() => handleMove(forward)}
              className="font-sans text-xs text-primary underline-offset-4 hover:underline"
            >
              {forward === "in_progress" ? "Move to In Progress →" : "Mark Done →"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Cell({
  items,
  onMove,
}: {
  items: ActionItemOut[];
  onMove: (id: string, newStatus: string) => void;
}) {
  if (items.length === 0)
    return <span className="font-sans text-sm text-muted-foreground">—</span>;
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <ItemCard key={item.id} item={item} onMove={onMove} />
      ))}
    </div>
  );
}

export default function ActionItemsPage() {
  const [allItems, setAllItems] = useState<ActionItemOut[] | null>(null);
  const [clients, setClients] = useState<ClientOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    Promise.all([
      listActionItems({ status: "open",        limit: 100 }),
      listActionItems({ status: "in_progress", limit: 100 }),
      listActionItems({ status: "missed",      limit: 100 }),
      listActionItems({ status: "completed",   limit: 100 }),
      listClients({ limit: 100 }),
    ])
      .then(([open, inProgress, missed, done, clientsResult]) => {
        setAllItems([
          ...open.items,
          ...inProgress.items,
          ...missed.items,
          ...done.items,
        ]);
        setClients(clientsResult.items);
      })
      .catch(() => setLoadError(true));
  }, []);

  const handleMove = useCallback((id: string, newStatus: string) => {
    setAllItems((prev) =>
      prev ? prev.map((i) => (i.id === id ? { ...i, status: newStatus } : i)) : prev,
    );
  }, []);

  const loading = allItems === null && clients === null && !loadError;
  const rows: ClientRow[] =
    allItems && clients ? groupByClient(clients, allItems) : [];

  return (
    <div className="space-y-10">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Accountability
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Action items
        </h1>
      </div>

      {loadError && (
        <p className="font-sans text-sm text-destructive">
          Could not load action items.
        </p>
      )}

      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      )}

      {!loading && !loadError && rows.length === 0 && (
        <p className="py-2 font-heading text-xl font-black text-muted-foreground">
          All clear. <em>No active items.</em>
        </p>
      )}

      {!loading && !loadError && rows.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-muted">
                <th className="w-36 p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                  Client
                </th>
                <th className="p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground border-l border-border">
                  Open
                </th>
                <th className="p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground border-l border-border">
                  In Progress
                </th>
                <th className="p-4 text-left font-sans text-xs font-bold uppercase tracking-widest text-foreground border-l border-border">
                  Done
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.client.id}
                  className="border-b border-border last:border-0 align-top"
                >
                  <td className="p-4">
                    <Link
                      href={`/clients/${row.client.id}`}
                      className="font-heading text-sm font-bold text-foreground underline-offset-4 hover:underline"
                    >
                      {row.client.full_name}
                    </Link>
                  </td>
                  <td className="p-4 border-l border-border">
                    <Cell items={row.open} onMove={handleMove} />
                  </td>
                  <td className="p-4 border-l border-border">
                    <Cell items={row.in_progress} onMove={handleMove} />
                  </td>
                  <td className="p-4 border-l border-border">
                    <Cell items={row.done} onMove={handleMove} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
