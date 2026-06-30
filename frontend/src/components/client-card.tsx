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
  metrics?: Array<{ id?: string; name: string; value: string; unit: string; target?: string }>;
}

export function ClientCard({ client, relativeDate, hasFlags, dim = false, metrics }: ClientCardProps) {
  return (
    <Link
      href={`/clients/${client.id}`}
      className={cn(
        "block rounded-2xl border p-4 transition-colors duration-150 hover:border-primary",
        hasFlags
          ? "border-destructive/50 bg-destructive/5"
          : "border-border bg-muted",
        dim && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Left: name + stage + date */}
        <div className="flex flex-col gap-1.5 min-w-0">
          <div className="flex items-start gap-2">
            <p className="font-heading text-base font-bold text-foreground leading-tight">
              {client.full_name}
            </p>
            {hasFlags && <span className="shrink-0 text-sm" aria-label="Needs attention">🚩</span>}
          </div>
          <Badge variant="secondary">
            {STAGE_LABEL[client.journey_stage] ?? client.journey_stage}
          </Badge>
          <p className="font-sans text-xs text-muted-foreground">{relativeDate}</p>
        </div>

        {/* Right: metric circles */}
        {metrics && metrics.length > 0 && (
          <div className="flex gap-2 shrink-0">
            {metrics.map(m => (
              <div key={m.id ?? m.name} className="flex flex-col items-center gap-0.5">
                <div className="w-14 h-14 rounded-full border border-border flex flex-col items-center justify-center px-1">
                  {m.target ? (
                    <>
                      <span className="font-sans text-[10px] font-medium text-foreground leading-tight text-center">
                        {m.value}{m.unit ? ` ${m.unit}` : ""}
                      </span>
                      <span className="w-8 border-t border-border my-0.5" />
                      <span className="font-sans text-[10px] text-muted-foreground leading-tight text-center">
                        {m.target}{m.unit ? ` ${m.unit}` : ""}
                      </span>
                    </>
                  ) : (
                    <span className="font-sans text-xs font-medium text-foreground text-center">
                      {m.value}{m.unit ? ` ${m.unit}` : ""}
                    </span>
                  )}
                </div>
                <span className="font-sans text-[9px] text-muted-foreground text-center leading-tight max-w-[56px] truncate">
                  {m.name}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}
