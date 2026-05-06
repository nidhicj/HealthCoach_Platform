import { notFound } from "next/navigation";
import type { ReactNode } from "react";

export default function DevLayout({ children }: { children: ReactNode }) {
  if (process.env.NEXT_PUBLIC_DEV_ROUTES !== "true") {
    notFound();
  }
  return <>{children}</>;
}
