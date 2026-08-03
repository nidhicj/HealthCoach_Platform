import type { Metadata } from "next";

/**
 * Server Component wrapper for the public intake route (`/intake/:slug`).
 *
 * The page itself is a Client Component (`"use client"` + `useParams`, this
 * codebase's page-data-fetching convention — see `(app)/clients/[clientId]/page.tsx`),
 * and the `metadata` export is only supported in Server Components. This layout
 * exists solely to carry it: DPDP requires these public, unauthenticated Lead
 * intake pages to be excluded from search indexing (SPEC-0001 Stage 2).
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function IntakeLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
