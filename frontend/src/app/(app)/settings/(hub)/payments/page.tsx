"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  connectPaymentAccount,
  getPaymentAccountStatus,
  PaymentAccountError,
} from "@/lib/api/payment_accounts";

// Nav placement for this page is PROVISIONAL — see the comment on
// SETTINGS_SECTIONS in `(hub)/layout.tsx` and the PHASE-05 Task 7 report.
export default function SettingsPaymentsPage() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getPaymentAccountStatus()
      .then((s) => setConnected(s.connected))
      .catch(() => setLoadError(true));
  }, []);

  const trimmedKeyId = keyId.trim();
  const trimmedKeySecret = keySecret.trim();
  const trimmedWebhookSecret = webhookSecret.trim();
  const canSubmit =
    trimmedKeyId !== "" && trimmedKeySecret !== "" && trimmedWebhookSecret !== "" && !saving;

  async function handleConnect() {
    if (!canSubmit) return;
    setSaving(true);
    setSaveErrorMessage(null);
    setSaved(false);
    try {
      const result = await connectPaymentAccount(trimmedKeyId, trimmedKeySecret, trimmedWebhookSecret);
      setConnected(result.connected);
      setSaved(true);
      // Credentials are write-only from the backend's perspective (never
      // returned back) — clear local field state after a successful save so
      // they don't linger in this component beyond the single POST.
      setKeyId("");
      setKeySecret("");
      setWebhookSecret("");
    } catch (err) {
      setSaveErrorMessage(
        err instanceof PaymentAccountError ? err.message : "Could not connect. Try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  const loading = connected === null && !loadError;

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Account
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">Payments</h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          Connect your Razorpay account so Leads can pay their consultation fee online before
          scheduling.
        </p>
      </div>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : loadError ? (
        <p className="font-sans text-sm text-destructive">Could not load payment account status.</p>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                connected ? "bg-primary" : "bg-muted-foreground"
              }`}
              aria-hidden="true"
            />
            <p className="font-sans text-sm font-bold text-foreground">
              {connected ? "Connected" : "Not connected"}
            </p>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <label
                htmlFor="razorpay-key-id"
                className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
              >
                Key ID
              </label>
              <Input
                id="razorpay-key-id"
                value={keyId}
                onChange={(e) => setKeyId(e.target.value)}
                placeholder="rzp_test_..."
                maxLength={200}
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="razorpay-key-secret"
                className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
              >
                Key Secret
              </label>
              <Input
                id="razorpay-key-secret"
                type="password"
                value={keySecret}
                onChange={(e) => setKeySecret(e.target.value)}
                maxLength={200}
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="razorpay-webhook-secret"
                className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground"
              >
                Webhook Secret
              </label>
              <Input
                id="razorpay-webhook-secret"
                type="password"
                value={webhookSecret}
                onChange={(e) => setWebhookSecret(e.target.value)}
                maxLength={200}
                autoComplete="off"
              />
            </div>

            <Button onClick={handleConnect} disabled={!canSubmit}>
              {saving ? "Connecting…" : connected ? "Reconnect" : "Connect"}
            </Button>
            {saveErrorMessage ? (
              <p className="font-sans text-xs text-destructive">{saveErrorMessage}</p>
            ) : saved ? (
              <p className="font-sans text-xs text-muted-foreground">Connected</p>
            ) : null}
          </div>

          <p className="font-sans text-xs text-muted-foreground">
            Credentials are sent directly to Razorpay for verification and then stored encrypted.
            They are never shown again after saving — reconnecting overwrites what&apos;s on file.
          </p>
        </>
      )}
    </div>
  );
}
