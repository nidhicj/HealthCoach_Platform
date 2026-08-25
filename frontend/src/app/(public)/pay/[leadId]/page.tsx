"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Script from "next/script";
import { createPaymentOrder, getLeadPaymentContext, PaymentError } from "@/lib/api/payments";

/**
 * Razorpay Checkout.js — a third-party script load. This repo has no CSP
 * configured anywhere (checked `next.config.ts` — no `headers()` entry; no
 * `middleware.ts`; no `Content-Security-Policy` string anywhere under
 * `frontend/src/`) and no prior precedent for loading a third-party script at
 * all (no existing `next/script` usage, e.g. for Google OAuth — that flow is a
 * server-side redirect, not a client-side script). So there is no existing
 * allowlist/convention to extend here, and nothing here needs to fit one —
 * flagged in the task report rather than silently assumed fine. Loaded via
 * `next/script` (Next's documented pattern for a page-scoped third-party
 * script), not a raw `<script>` tag.
 */
const RAZORPAY_CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

interface RazorpayCheckoutOptions {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description?: string;
  theme?: { color?: string };
  handler: (response: {
    razorpay_payment_id: string;
    razorpay_order_id: string;
    razorpay_signature: string;
  }) => void;
  modal?: { ondismiss?: () => void };
}

interface RazorpayCheckoutInstance {
  open: () => void;
  on: (event: "payment.failed", handler: () => void) => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayCheckoutOptions) => RazorpayCheckoutInstance;
  }
}

// Client-side confirmation polling. Razorpay's `handler` callback firing on
// checkout success is NOT authoritative — per the task brief and
// `backend/src/api/payments.py`'s webhook docstring, only
// `POST /api/payments/webhook` (Task 6) ever advances `payment_status`. Once
// the callback fires, poll GET .../payment for the webhook to catch up, with
// a bounded attempt budget rather than polling forever.
const POLL_INTERVAL_MS = 3000;
const POLL_MAX_ATTEMPTS = 15; // ~45s total

type Status =
  | "loading"
  | "load_error"
  | "not_found"
  | "paid"
  | "ready"
  | "starting_order"
  | "confirming"
  | "confirm_timeout"
  | "payment_failed";

const RETRY_SAFE_MESSAGE =
  "Payment didn't go through. Nothing was charged — you can try again.";

export default function PayPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const [status, setStatus] = useState<Status>("loading");
  const [hcName, setHcName] = useState("your health coach");
  const [feeInr, setFeeInr] = useState<number | null>(null);
  const [schedulingLink, setSchedulingLink] = useState<string | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [failureMessage, setFailureMessage] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [scriptError, setScriptError] = useState(false);

  // Guards every async continuation (context load, poll loop) against setting
  // state after unmount — same discipline the poll loop needs regardless,
  // since it spans many seconds of real time across which the Lead could
  // navigate away.
  const cancelledRef = useRef(false);
  useEffect(() => {
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  const applyContext = useCallback((ctx: Awaited<ReturnType<typeof getLeadPaymentContext>>) => {
    if (cancelledRef.current) return;
    setHcName(ctx.hc_name);
    setFeeInr(ctx.consultation_fee_inr);
    if (ctx.payment_status === "paid" && ctx.scheduling_link) {
      setSchedulingLink(ctx.scheduling_link);
      setStatus("paid");
    } else {
      setStatus("ready");
    }
  }, []);

  const loadContext = useCallback(
    async (id: string) => {
      try {
        const ctx = await getLeadPaymentContext(id);
        applyContext(ctx);
      } catch (err) {
        if (cancelledRef.current) return;
        setStatus(err instanceof PaymentError && err.status === 404 ? "not_found" : "load_error");
      }
    },
    [applyContext],
  );

  useEffect(() => {
    if (!leadId) return;
    loadContext(leadId);
  }, [leadId, loadContext]);

  const pollUntilPaid = useCallback(async (id: string) => {
    for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      if (cancelledRef.current) return;
      try {
        const ctx = await getLeadPaymentContext(id);
        if (ctx.payment_status === "paid" && ctx.scheduling_link) {
          if (cancelledRef.current) return;
          setSchedulingLink(ctx.scheduling_link);
          setStatus("paid");
          return;
        }
      } catch {
        // Transient errors while polling are swallowed — keep polling until
        // the attempt budget is exhausted. A genuine outage surfaces via the
        // confirm_timeout state's own "check again" escape hatch below.
      }
    }
    if (!cancelledRef.current) setStatus("confirm_timeout");
  }, []);

  function openCheckout(order: { order_id: string; key_id: string; amount_paise: number }, id: string, name: string) {
    if (!window.Razorpay) {
      setOrderError("Payment page isn't ready yet — please try again in a moment.");
      setStatus("ready");
      return;
    }
    const rzp = new window.Razorpay({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount_paise,
      currency: "INR",
      name,
      description: "Consultation fee",
      theme: { color: "#000000" },
      handler: () => {
        // NOT authoritative — see module comment above. Only the webhook
        // decides this actually succeeded.
        setStatus("confirming");
        pollUntilPaid(id);
      },
      modal: {
        ondismiss: () => {
          if (cancelledRef.current) return;
          setFailureMessage(RETRY_SAFE_MESSAGE);
          setStatus("payment_failed");
        },
      },
    });
    rzp.on("payment.failed", () => {
      if (cancelledRef.current) return;
      setFailureMessage(RETRY_SAFE_MESSAGE);
      setStatus("payment_failed");
    });
    rzp.open();
  }

  async function handlePay() {
    if (!leadId) return;
    setOrderError(null);
    setFailureMessage(null);
    setStatus("starting_order");
    try {
      const order = await createPaymentOrder(leadId);
      openCheckout(order, leadId, hcName);
    } catch (err) {
      if (cancelledRef.current) return;
      if (err instanceof PaymentError && err.errorCode === "already_paid") {
        // Race: payment_status flipped to "paid" (e.g. via the webhook)
        // between page load and this click. Refetch context rather than
        // surfacing a stale "already paid" error — the Lead should just see
        // the paid/scheduling view.
        loadContext(leadId);
        return;
      }
      setOrderError(err instanceof PaymentError ? err.message : "Something went wrong. Please try again.");
      setStatus("ready");
    }
  }

  if (status === "loading") {
    return (
      <main className="mx-auto max-w-md px-4 py-16">
        <p className="font-sans text-sm text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (status === "load_error") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Something went wrong</h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          Could not load this page right now. Please try again in a moment.
        </p>
      </main>
    );
  }

  if (status === "not_found") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Link not found</h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          This payment link doesn&apos;t seem to be valid. Please check the link or contact your
          health coach.
        </p>
      </main>
    );
  }

  if (status === "paid" && schedulingLink) {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Payment received</h1>
        <p className="mt-3 font-sans text-sm text-foreground">
          Thank you — your consultation fee has been received. Use the link below to schedule
          your session with {hcName}.
        </p>
        <a
          href={schedulingLink}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-6 inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Schedule your consultation
        </a>
      </main>
    );
  }

  if (status === "confirming") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Confirming your payment…</h1>
        <p className="mt-3 font-sans text-sm text-muted-foreground">
          This can take a moment — please don&apos;t close this page.
        </p>
      </main>
    );
  }

  if (status === "confirm_timeout") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Still confirming</h1>
        <p className="mt-3 font-sans text-sm text-muted-foreground">
          Your payment is taking longer than expected to confirm. If money was deducted, there&apos;s
          no need to pay again — check back here in a few minutes, or contact {hcName} directly.
        </p>
        <button
          type="button"
          onClick={() => leadId && loadContext(leadId)}
          className="mt-6 rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground"
        >
          Check again
        </button>
      </main>
    );
  }

  // status is "ready" | "starting_order" | "payment_failed"
  const feeUnconfigured = feeInr === null;

  return (
    <main className="mx-auto max-w-md px-4 py-10">
      <Script
        src={RAZORPAY_CHECKOUT_SRC}
        strategy="afterInteractive"
        onLoad={() => setScriptReady(true)}
        onError={() => setScriptError(true)}
      />

      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Book your consultation</h1>
        <p className="font-sans text-sm text-muted-foreground">
          {hcName} is ready to see you. Complete payment below to unlock scheduling and report
          upload.
        </p>
      </div>

      <div className="space-y-5">
        <div className="rounded-md border border-border bg-muted/30 p-4 text-center">
          <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Consultation fee
          </p>
          <p className="mt-1 font-heading text-3xl font-black text-foreground">
            {feeInr !== null ? `₹${feeInr.toLocaleString("en-IN")}` : "—"}
          </p>
        </div>

        {feeUnconfigured ? (
          <p className="rounded-md border border-border bg-muted/30 p-3 text-center font-sans text-sm text-muted-foreground">
            Consultation payment isn&apos;t available yet — please contact {hcName} directly.
          </p>
        ) : (
          <>
            {status === "payment_failed" && failureMessage && (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {failureMessage}
              </p>
            )}

            {orderError && (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {orderError}
              </p>
            )}

            {scriptError && (
              <p className="font-sans text-xs text-destructive">
                Couldn&apos;t load the payment page. Please refresh and try again.
              </p>
            )}

            <button
              type="button"
              onClick={handlePay}
              disabled={status === "starting_order" || !scriptReady || scriptError}
              className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {status === "starting_order"
                ? "Starting payment…"
                : status === "payment_failed"
                  ? "Try again"
                  : !scriptReady
                    ? "Loading…"
                    : "Pay now"}
            </button>
          </>
        )}

        <div className="rounded-md border border-border bg-muted/30 p-3">
          <p className="font-sans text-sm text-foreground">
            Payment is processed securely by Razorpay. We do not store your card or bank details.
          </p>
        </div>
      </div>
    </main>
  );
}
