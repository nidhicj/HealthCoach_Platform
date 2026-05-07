"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listClients, type ClientOut } from "@/lib/api/clients";

const JOURNEY_STAGE_LABEL: Record<string, string> = {
  onboarding: "Onboarding",
  active: "Active",
  plateau: "Plateau",
  off_track: "Off track",
  completed: "Completed",
};

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientOut[] | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    listClients({ limit: 20 })
      .then((r) => {
        setClients(r.items);
        setNextCursor(r.next_cursor);
      })
      .catch(() => setLoadError(true));
  }, []);

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
            Roster
          </p>
          <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
            Clients
          </h1>
        </div>
        {/* Primary action — Moss Shadow, NOT Marigold (Marigold reserved for empty state) */}
        <Link href="/clients/new" className={buttonVariants({ variant: "default" })}>
          New client
        </Link>
      </div>

      {/* Table */}
      {clients === null && !loadError ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : loadError ? (
        <p className="font-sans text-sm text-destructive">
          Could not load clients.
        </p>
      ) : clients!.length === 0 ? (
        <div className="flex flex-col items-start gap-5 py-8">
          <p className="font-heading text-2xl font-black text-muted-foreground">
            No clients yet. <em>Add your first one.</em>
          </p>
          {/* Marigold on empty-state CTA */}
          <Link href="/clients/new" className={buttonVariants({ variant: "accent" })}>
            Add client
          </Link>
        </div>
      ) : (
        <div>
          {/* Column headers — Manrope 700 eyebrow style */}
          <div className="grid grid-cols-[1fr_auto_auto] gap-4 border-b border-border pb-2">
            <span className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Name
            </span>
            <span className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Stage
            </span>
            <span className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
              Code
            </span>
          </div>
          <ul>
            {clients!.map((client) => (
              <li key={client.id} className="border-b border-border last:border-0">
                <Link
                  href={`/clients/${client.id}`}
                  className="grid grid-cols-[1fr_auto_auto] items-center gap-4 py-4 transition-colors duration-150 hover:text-primary"
                >
                  {/* Fraunces 700 for client names */}
                  <span className="font-heading text-base font-bold text-foreground">
                    {client.full_name}
                  </span>
                  <Badge variant="secondary">
                    {JOURNEY_STAGE_LABEL[client.journey_stage] ?? client.journey_stage}
                  </Badge>
                  <span className="font-sans text-xs text-muted-foreground">
                    {client.code ?? "—"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {nextCursor && (
            <div className="pt-4 text-center">
              <Button variant="outline" size="sm" disabled>
                Load more
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
