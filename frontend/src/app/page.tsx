"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center">
      <p className="font-sans text-sm text-muted-foreground">Loading…</p>
    </main>
  );
}
