"use client";

import { notFound } from "next/navigation";
import { useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import "@/styles/motion.css";

// Gated: only visible when NEXT_PUBLIC_DEV_ROUTES=true
if (process.env.NEXT_PUBLIC_DEV_ROUTES !== "true") {
  notFound();
}

const PALETTE = [
  { name: "Parchment",   hex: "#F7F4EE", textClass: "text-dark-ink",   role: "Base — never swap for white" },
  { name: "Moss Shadow", hex: "#5C6652", textClass: "text-parchment",  role: "Voice — bounded blocks only" },
  { name: "Dark Ink",    hex: "#2C2C1E", textClass: "text-parchment",  role: "Fierce — one fill per screen max" },
  { name: "Marigold",    hex: "#E8C547", textClass: "text-dark-ink",   role: "Once only — the focal point" },
];

const FUNCTIONAL = [
  { name: "Success", hex: "#3F7D4B" },
  { name: "Warning", hex: "#B8722C" },
  { name: "Error",   hex: "#A23E2E" },
];

function BrandRulesChecker() {
  const [results, setResults] = useState<string[]>([]);

  function runCheck() {
    const items: string[] = [];
    const all = document.querySelectorAll("*");
    let marigoldCount = 0;
    let darkInkFillCount = 0;
    let whiteBgCount = 0;

    all.forEach((el) => {
      const bg = getComputedStyle(el).backgroundColor;
      if (bg === "rgb(232, 197, 71)") marigoldCount++;
      if (bg === "rgb(44, 44, 30)")   darkInkFillCount++;
      if (bg === "rgb(255, 255, 255)") whiteBgCount++;
    });

    const h = document.querySelectorAll("h1,h2,h3");
    let headingFontOk = true;
    h.forEach((el) => {
      if (!getComputedStyle(el).fontFamily.toLowerCase().includes("fraunces")) headingFontOk = false;
    });
    const bodyFont = getComputedStyle(document.body).fontFamily.toLowerCase().includes("manrope");

    items.push(`Marigold elements: ${marigoldCount} ${marigoldCount <= 1 ? "✓" : "✗ (must be ≤ 1)"}`);
    items.push(`Dark Ink fills: ${darkInkFillCount} ${darkInkFillCount <= 1 ? "✓" : "✗ (must be ≤ 1)"}`);
    items.push(`White backgrounds: ${whiteBgCount} ${whiteBgCount === 0 ? "✓" : "✗ (must be 0)"}`);
    items.push(`Headings font Fraunces: ${headingFontOk ? "✓" : "✗"}`);
    items.push(`Body font Manrope: ${bodyFont ? "✓" : "✗"}`);
    setResults(items);
  }

  return (
    <section className="space-y-4">
      <h2 className="text-2xl font-heading">§7 Brand-rules checker</h2>
      <p className="text-sm text-muted-foreground">Live DOM scan of this page against brand rules.</p>
      <Button onClick={runCheck} variant="outline">Run check</Button>
      {results.length > 0 && (
        <ul className="font-mono text-sm space-y-1 p-4 bg-secondary rounded-lg">
          {results.map((r, i) => (
            <li key={i} className={r.includes("✗") ? "text-destructive" : "text-foreground"}>{r}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function MotionLab() {
  // Second gate at render time (belt-and-suspenders for static export)
  if (process.env.NEXT_PUBLIC_DEV_ROUTES !== "true") return null;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);

  return (
    <TooltipProvider>
      <main className="min-h-screen p-8 md:p-16 space-y-16 max-w-4xl mx-auto animate-page-in">

        {/* Header */}
        <div className="border-b border-border pb-6">
          <Badge variant="outline" className="mb-4 font-mono text-xs">dev only · NEXT_PUBLIC_DEV_ROUTES=true</Badge>
          <h1 className="text-4xl font-heading">Motion Lab</h1>
          <p className="mt-2 text-muted-foreground">
            Every motion primitive and brand element on one page. Sign off before Stage 2 begins.
          </p>
        </div>

        {/* §1 Palette swatches */}
        <section className="space-y-4">
          <h2 className="text-2xl font-heading">§1 Palette swatches</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {PALETTE.map((c) => (
              <div key={c.name} className="rounded-lg overflow-hidden border border-border">
                <div
                  className={`h-24 flex items-end p-3 ${c.textClass}`}
                  style={{ backgroundColor: c.hex }}
                >
                  <span className="font-mono text-xs font-bold">{c.hex}</span>
                </div>
                <div className="p-3 bg-card">
                  <p className="font-bold text-sm">{c.name}</p>
                  <p className="text-xs text-muted-foreground">{c.role}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            {FUNCTIONAL.map((c) => (
              <div key={c.name} className="flex items-center gap-2">
                <div className="w-5 h-5 rounded" style={{ backgroundColor: c.hex }} />
                <span className="text-xs font-mono">{c.name} {c.hex}</span>
              </div>
            ))}
          </div>
        </section>

        {/* §2 Type scale */}
        <section className="space-y-4">
          <h2 className="text-2xl font-heading">§2 Type scale</h2>
          <div className="space-y-3 p-6 bg-card rounded-lg border border-border">
            <p className="font-heading" style={{ fontSize: "48px", fontWeight: 900, color: "#5C6652" }}>Display 900 · Moss</p>
            <p className="font-heading" style={{ fontSize: "48px", fontWeight: 900, fontStyle: "italic" }}>900 Italic · one punch per headline</p>
            <p className="font-heading" style={{ fontSize: "32px", fontWeight: 700 }}>Secondary 700 · section opener</p>
            <p className="font-heading" style={{ fontSize: "18px", fontWeight: 700, fontStyle: "italic", color: "#5C6652" }}>700 Italic · pull quote on Moss</p>
            <hr className="border-border my-2" />
            <p className="font-sans" style={{ fontSize: "15px", fontWeight: 400 }}>Body Manrope 400 · 15px · minimum 13px on screen</p>
            <p className="font-sans font-bold text-xs uppercase tracking-widest text-primary">Eyebrow Label · Manrope 700 · 11px</p>
            <p className="font-sans" style={{ fontSize: "14px", fontWeight: 800 }}>Bold callout Manrope 800 · shout without size increase</p>
          </div>
        </section>

        {/* §3 State change demo */}
        <section className="space-y-4">
          <h2 className="text-2xl font-heading">§3 State change (150ms ease-out)</h2>
          <p className="text-sm text-muted-foreground">Hover, focus, and click each button. Feel the 150ms response.</p>
          <div className="flex flex-wrap gap-3">
            <Button>Moss Shadow (default)</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="accent">Marigold accent ← the once-per-screen CTA</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button disabled>Disabled</Button>
          </div>
        </section>

        {/* §4 Reveal demo */}
        <section className="space-y-4">
          <h2 className="text-2xl font-heading">§4 Reveal (200ms ease-out)</h2>
          <p className="text-sm text-muted-foreground">Dropdowns, tooltips, and popovers.</p>
          <div className="flex flex-wrap gap-3 items-center">
            <DropdownMenu>
              <DropdownMenuTrigger className={cn(buttonVariants({ variant: "outline" }))}>
                Dropdown ↓
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem>View client</DropdownMenuItem>
                <DropdownMenuItem>New session</DropdownMenuItem>
                <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Tooltip>
              <TooltipTrigger className={cn(buttonVariants({ variant: "outline" }))}>
                Hover for tooltip
              </TooltipTrigger>
              <TooltipContent>
                <p>200ms reveal — feels instant but not jarring</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </section>

        {/* §5 Sheet / Dialog demo */}
        <section className="space-y-4">
          <h2 className="text-2xl font-heading">§5 Sheet + Dialog (250ms / 200ms)</h2>
          <p className="text-sm text-muted-foreground">Sheet slides from the right edge. Dialog fades and scales from centre.</p>
          <div className="flex gap-3">
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetTrigger className={cn(buttonVariants({ variant: "outline" }))}>
                Open sheet
              </SheetTrigger>
              <SheetContent>
                <SheetHeader>
                  <SheetTitle>Session notes</SheetTitle>
                </SheetHeader>
                <p className="mt-4 text-muted-foreground text-sm">
                  This slides in at 250ms ease-out and slides out at 200ms ease-in.
                  Feel how it arrives with authority and exits cleanly.
                </p>
                <Button className="mt-6" onClick={() => setSheetOpen(false)}>Close</Button>
              </SheetContent>
            </Sheet>

            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger className={cn(buttonVariants({ variant: "outline" }))}>
                Open dialog
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Confirm action</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-muted-foreground mt-2">
                  Dialog fades and scales from 0.96 → 1 at 200ms ease-out.
                  This feels decisive, not floaty.
                </p>
                <div className="flex gap-2 mt-4">
                  <Button onClick={() => setDialogOpen(false)}>Confirm</Button>
                  <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </section>

        {/* §6 Page transition demo */}
        <section className="space-y-4">
          <h2 className="text-2xl font-heading">§6 Page transition (300ms ease-in-out)</h2>
          <p className="text-sm text-muted-foreground">
            This entire page entered with a 300ms fade + 6px upward slide (see <code>.animate-page-in</code>).{" "}
            View Transitions API status:{" "}
            <span className="font-mono">
              {typeof document !== "undefined" && "startViewTransition" in document
                ? "✓ native (your browser supports it)"
                : "CSS fallback (not supported in this browser)"}
            </span>
          </p>
          <Card className="border-border">
            <CardHeader>
              <CardTitle className="font-heading text-lg">The Marigold carries the eye</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              In real screens, the Marigold CTA carries a stable{" "}
              <code>view-transition-name</code> so it morphs as a single element across
              route changes — the brand-faithful version of "Marigold marks the eye."
            </CardContent>
          </Card>
        </section>

        {/* §7 Brand-rules checker */}
        <BrandRulesChecker />

        <footer className="border-t border-border pt-6 text-xs text-muted-foreground font-mono">
          Parivarthan Motion Lab · Stage 1 · gated on NEXT_PUBLIC_DEV_ROUTES=true
        </footer>
      </main>
    </TooltipProvider>
  );
}
