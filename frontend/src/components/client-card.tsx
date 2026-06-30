import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ClientOut } from "@/lib/api/clients";

const STAGE_LABEL: Record<string, string> = {
  onboarding: "Onboarding",
  active: "Active",
  plateau: "Plateau",
  off_track: "Off track",
  completed: "Completed",
};

interface ClientCardProps {
  client: ClientOut;
  relativeDate: string;
  hasFlags: boolean;
  dim?: boolean;
  metrics?: Array<{ id?: string; name: string; value: string; unit: string }>;
}

export function ClientCard({ client, relativeDate, hasFlags, dim = false, metrics }: ClientCardProps) {
  return (
    <Link
      href={`/clients/${client.id}`}
      className={cn(
        "block rounded-2xl border p-4 space-y-2 transition-colors duration-150 hover:border-primary",
        hasFlags
          ? "border-destructive/50 bg-destructive/5"
          : "border-border bg-muted",
        dim && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-heading text-base font-bold text-foreground leading-tight">
          {client.full_name}
        </p>
        {hasFlags && <span className="shrink-0 text-sm" aria-label="Needs attention">🚩</span>}
      </div>
      <Badge variant="secondary">
        {STAGE_LABEL[client.journey_stage] ?? client.journey_stage}
      </Badge>
      <p className="font-sans text-xs text-muted-foreground">{relativeDate}</p>
      {metrics && metrics.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {metrics.map(m => (
            <span key={m.id ?? m.name} className="text-xs text-muted-foreground">
              {m.name}:{" "}
              <span className="font-medium text-foreground">{m.value} {m.unit}</span>
            </span>
          ))}
        </div>
      )}
    </Link>
  );
}
