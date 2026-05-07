"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  listActionItems,
  patchActionItem,
  type ActionItemOut,
} from "@/lib/api/actionItems";

const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  missed: "Missed",
  completed: "Completed",
};

const NEXT_STATUS: Record<string, string> = {
  open: "in_progress",
  in_progress: "completed",
};

function isOverdue(dateStr: string | null): boolean {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date(new Date().toDateString());
}

function ActionItemRow({
  item,
  onStatusChange,
}: {
  item: ActionItemOut;
  onStatusChange: (updated: ActionItemOut) => void;
}) {
  const [transitioning, setTransitioning] = useState(false);
  const next = NEXT_STATUS[item.status];

  async function handleAdvance() {
    if (!next) return;
    setTransitioning(true);
    try {
      const updated = await patchActionItem(item.id, { status: next });
      onStatusChange(updated);
    } finally {
      setTransitioning(false);
    }
  }

  return (
    <li className="flex items-start justify-between py-3 gap-4">
      <div className="space-y-0.5 min-w-0">
        <p className="font-sans text-sm text-foreground">{item.description}</p>
        {item.due_date && (
          <p
            className={cn(
              "font-sans text-xs",
              isOverdue(item.due_date)
                ? "font-bold text-destructive"
                : "text-muted-foreground",
            )}
          >
            Due {new Date(item.due_date).toLocaleDateString("en-IN")}
            {isOverdue(item.due_date) && " · Overdue"}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link href={`/clients/${item.client_id}`}>
          <Badge variant="outline" className="cursor-pointer">
            View client
          </Badge>
        </Link>
        {next && (
          <button
            onClick={handleAdvance}
            disabled={transitioning}
            className="font-sans text-xs text-primary underline-offset-4 hover:underline disabled:opacity-50"
          >
            {transitioning ? "…" : `Mark ${STATUS_LABEL[next]?.toLowerCase()}`}
          </button>
        )}
      </div>
    </li>
  );
}

function Section({
  title,
  items,
  loading,
  empty,
  onStatusChange,
}: {
  title: string;
  items: ActionItemOut[];
  loading: boolean;
  empty: string;
  onStatusChange: (updated: ActionItemOut) => void;
}) {
  return (
    <section className="space-y-4">
      <h2 className="font-heading text-xl font-bold text-foreground">{title}</h2>
      <Separator />
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : items.length === 0 ? (
        <p className="py-2 font-heading text-lg font-black text-muted-foreground">
          {empty}
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((item) => (
            <ActionItemRow key={item.id} item={item} onStatusChange={onStatusChange} />
          ))}
        </ul>
      )}
    </section>
  );
}

export default function ActionItemsPage() {
  const [items, setItems] = useState<ActionItemOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    Promise.all([
      listActionItems({ status: "open", limit: 50 }),
      listActionItems({ status: "in_progress", limit: 50 }),
      listActionItems({ status: "missed", limit: 50 }),
    ])
      .then(([open, inProgress, missed]) => {
        setItems([...open.items, ...inProgress.items, ...missed.items]);
      })
      .catch(() => setLoadError(true));
  }, []);

  function handleStatusChange(updated: ActionItemOut) {
    setItems((prev) =>
      prev ? prev.map((i) => (i.id === updated.id ? updated : i)) : prev,
    );
  }

  const loading = items === null && !loadError;

  const open = (items ?? []).filter((i) => i.status === "open");
  const inProgress = (items ?? []).filter((i) => i.status === "in_progress");
  const missed = (items ?? []).filter((i) => i.status === "missed");

  return (
    <div className="space-y-10">
      {/* Page header */}
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Accountability
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Action items
        </h1>
      </div>

      {loadError ? (
        <p className="font-sans text-sm text-destructive">
          Could not load action items.
        </p>
      ) : (
        <div className="space-y-10">
          <Section
            title="Open"
            items={open}
            loading={loading}
            empty="All clear. Nothing open."
            onStatusChange={handleStatusChange}
          />
          <Section
            title="In progress"
            items={inProgress}
            loading={loading}
            empty="Nothing in progress."
            onStatusChange={handleStatusChange}
          />
          <Section
            title="Missed"
            items={missed}
            loading={loading}
            empty="No missed items."
            onStatusChange={handleStatusChange}
          />
        </div>
      )}
    </div>
  );
}
