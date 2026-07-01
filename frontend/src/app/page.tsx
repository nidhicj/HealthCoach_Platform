"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { silentRefresh } from "@/lib/auth/client";

// ── Nav ───────────────────────────────────────────────────────────────────────

function Nav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <span className="font-heading text-xl font-black tracking-tight text-foreground">
          Tapas
        </span>
        <Link
          href="/sign-in"
          className="font-sans text-sm font-bold text-primary transition-colors hover:text-foreground"
        >
          Sign in →
        </Link>
      </div>
    </nav>
  );
}

// ── Diet chart card (signature element — no screenshot needed) ────────────────

function DietChartCard() {
  const meals = [
    { time: "Breakfast",   dish: "Poha with methi seeds",          kcal: 280 },
    { time: "Mid-morning", dish: "Chaas (buttermilk)",             kcal:  50 },
    { time: "Lunch",       dish: "Dal + 2 rotis + sabzi + curd",   kcal: 540 },
    { time: "Evening",     dish: "Roasted makhana",                kcal:  80 },
    { time: "Dinner",      dish: "Khichdi + raita",                kcal: 380 },
  ];
  const total = meals.reduce((s, m) => s + m.kcal, 0);

  return (
    <div className="relative flex items-center justify-center py-10">
      {/* Ghost card — depth effect */}
      <div
        className="absolute inset-4 rounded-xl bg-white shadow-md"
        style={{ transform: "rotate(3.5deg) translateY(6px)", opacity: 0.45 }}
        aria-hidden
      />

      {/* Main card */}
      <div
        className="relative w-full max-w-sm rounded-xl bg-white shadow-xl"
        style={{ transform: "rotate(-1.5deg)" }}
      >
        {/* Header */}
        <div className="rounded-t-xl bg-primary px-5 py-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="font-heading text-lg font-black text-primary-foreground">
                Priya S.
              </p>
              <p className="mt-0.5 font-sans text-xs text-primary-foreground/70">
                12-week weight management
              </p>
            </div>
            <div className="text-right">
              <p className="font-sans text-xs font-bold text-primary-foreground/70">
                Week 3
              </p>
              <p className="font-sans text-xs text-primary-foreground/50">
                Monday
              </p>
            </div>
          </div>
        </div>

        {/* Meal rows */}
        <div className="px-5 py-1">
          {meals.map((meal, i) => (
            <div
              key={meal.time}
              className={`flex items-start justify-between gap-3 py-2.5 ${
                i < meals.length - 1 ? "border-b border-border" : ""
              }`}
            >
              <div className="min-w-0">
                <p className="font-sans text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  {meal.time}
                </p>
                <p className="mt-0.5 font-sans text-sm text-foreground">
                  {meal.dish}
                </p>
              </div>
              <p className="whitespace-nowrap font-sans text-sm font-bold text-primary">
                {meal.kcal} kcal
              </p>
            </div>
          ))}
        </div>

        {/* Total */}
        <div className="mx-5 flex items-center justify-between border-t border-border py-3">
          <p className="font-sans text-sm font-bold text-foreground">Total</p>
          <p className="font-sans text-sm font-bold text-foreground">
            {total.toLocaleString()} kcal
          </p>
        </div>

        {/* Footer tag */}
        <div className="rounded-b-xl bg-section-fill-01 px-5 py-2.5">
          <p className="font-sans text-xs text-primary">
            ⚡ Generated from your template · 2 min ago
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────

function HeroSection() {
  return (
    <section className="bg-background py-16 md:py-24">
      <div className="mx-auto max-w-5xl px-6">
        <div className="grid items-center gap-12 md:grid-cols-2">
          <div className="flex flex-col gap-6">
            <h1 className="font-heading text-4xl font-black leading-[1.1] text-foreground md:text-5xl">
              One place to run a solo health-coaching practice in India.
            </h1>
            <p className="font-sans text-lg leading-relaxed text-muted-foreground">
              Turn every session into a client-ready plan in minutes, not hours.
            </p>
            <div>
              <Link
                href="/sign-in"
                className="inline-flex items-center rounded-md bg-accent px-6 py-3 font-sans text-sm font-bold text-foreground transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
              >
                Get started
              </Link>
            </div>
          </div>
          <DietChartCard />
        </div>
      </div>
    </section>
  );
}

// ── Problem ───────────────────────────────────────────────────────────────────

function ProblemSection() {
  return (
    <section className="bg-section-fill-01 py-16 md:py-20">
      <div className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="font-heading text-3xl font-black italic leading-tight text-foreground md:text-4xl">
          The session ends. Then the real work begins.
        </h2>
        <p className="mt-6 font-sans text-base leading-relaxed text-muted-foreground">
          After every client, you turn your notes into a diet chart. Write the
          follow-ups. Type it all out. Then do it again for the next client, and
          the next — every week. The coaching is the easy part. The admin is
          what eats your evenings.
        </p>
      </div>
    </section>
  );
}

// ── How it works ──────────────────────────────────────────────────────────────

const STEPS = [
  {
    n: "01",
    title: "Capture the session",
    body: "Notes, a saved template, or a Zoom AI summary — start from wherever you are.",
  },
  {
    n: "02",
    title: "Generate",
    body: "AI builds the diet chart and follow-ups in your method, with the foods your clients actually eat.",
  },
  {
    n: "03",
    title: "Send and track",
    body: "Deliver the plan, then watch each action item move from open to done.",
  },
];

function HowItWorksSection() {
  return (
    <section className="bg-background py-16 md:py-20">
      <div className="mx-auto max-w-5xl px-6">
        <h2 className="font-heading text-3xl font-black text-foreground md:text-4xl">
          Three steps, every client.
        </h2>
        <div className="mt-10 grid gap-10  md:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.n} className="flex flex-col gap-2">
              <span
                className="font-heading text-6xl font-black leading-none select-none"
                style={{ color: "var(--color-marigold)" }}
                aria-hidden
              >
                {s.n}
              </span>
              <h3 className="mt-1 font-heading text-xl font-black text-foreground">
                {s.title}
              </h3>
              <p className="font-sans text-sm leading-relaxed text-muted-foreground">
                {s.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Who it's for ──────────────────────────────────────────────────────────────

function WhoSection() {
  return (
    <section className="bg-section-fill-02 py-16 md:py-20">
      <div className="mx-auto max-w-2xl px-6">
        <h2 className="font-heading text-3xl font-black text-foreground md:text-4xl">
          Made for solo coaches.
        </h2>
        <p className="mt-6 font-sans text-base leading-relaxed text-muted-foreground">
          For independent health coaches and nutritionists in India running
          their own practice. If you see every client yourself and do your own
          admin, this is for you.
        </p>
        <p className="mt-3 font-sans text-sm text-muted-foreground">
          Not built for large clinics or multi-coach teams — yet.
        </p>
      </div>
    </section>
  );
}

// ── Final CTA ─────────────────────────────────────────────────────────────────

function FinalCtaSection() {
  return (
    <section className="bg-background py-20 md:py-28">
      <div className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="font-heading text-4xl font-black text-foreground md:text-5xl">
          Get your evenings back.
        </h2>
        <p className="mt-4 font-sans text-base text-muted-foreground">
          Sessions, diet charts, and client accountability — handled.
        </p>
        <div className="mt-8">
          <Link
            href="/sign-in"
            className="inline-flex items-center rounded-md bg-primary px-6 py-3 font-sans text-sm font-bold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            Sign in to get started
          </Link>
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="border-t border-border bg-background py-8">
      <div className="mx-auto max-w-5xl px-6">
        <p className="font-sans text-xs text-muted-foreground">
          © 2025 Tapas. For independent health coaches in India.
        </p>
      </div>
    </footer>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    silentRefresh().then((ok) => {
      if (ok) router.replace("/dashboard");
      else setReady(true);
    });
  }, [router]);

  if (!ready) {
    return <div className="min-h-screen bg-background" />;
  }

  return (
    <main className="animate-page-in">
      <Nav />
      <HeroSection />
      <ProblemSection />
      <HowItWorksSection />
      <WhoSection />
      <FinalCtaSection />
      <Footer />
    </main>
  );
}
