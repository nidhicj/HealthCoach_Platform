import type { Metadata } from "next";

/**
 * Server Component wrapper for the public blood-report upload route
 * (`/upload/:token`).
 *
 * The page itself is a Client Component (`"use client"` + `useParams`, this
 * codebase's page-data-fetching convention — see
 * `(public)/intake/[slug]/page.tsx`), and the `metadata` export is only
 * supported in Server Components. This layout exists solely to carry it:
 * DPDP requires these public, unauthenticated Lead-facing pages to be
 * excluded from search indexing (PHASE-03's plan, mirroring
 * `(public)/intake/layout.tsx`'s rationale for `/intake/:slug`).
 *
 * `title` is deliberately generic/unbranded, matching `intake/layout.tsx`:
 * no platform branding that could confuse the Lead about who they're
 * engaging with, and this Server Component can't fetch the HC's name to
 * personalize it.
 */
export const metadata: Metadata = {
  title: "Upload Blood Reports",
  robots: { index: false, follow: false },
};

export default function UploadLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
