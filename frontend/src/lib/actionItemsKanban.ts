import type { ClientOut } from "@/lib/api/clients";
import type { ActionItemOut } from "@/lib/api/actionItems";

export const MOVE_FORWARD: Record<string, string> = {
  open:        "in_progress",
  missed:      "in_progress",
  in_progress: "completed",
};

export const MOVE_BACK: Record<string, string> = {
  in_progress: "open",
  completed:   "in_progress",
};

export type ClientRow = {
  client: ClientOut;
  open: ActionItemOut[];
  in_progress: ActionItemOut[];
  done: ActionItemOut[];
};

export function groupByClient(
  clients: ClientOut[],
  items: ActionItemOut[],
): ClientRow[] {
  return clients
    .map((client) => ({
      client,
      open: items.filter(
        (i) => i.client_id === client.id && (i.status === "open" || i.status === "missed"),
      ),
      in_progress: items.filter(
        (i) => i.client_id === client.id && i.status === "in_progress",
      ),
      done: items.filter(
        (i) => i.client_id === client.id && i.status === "completed",
      ),
    }))
    .filter((row) => row.open.length + row.in_progress.length + row.done.length > 0);
}
