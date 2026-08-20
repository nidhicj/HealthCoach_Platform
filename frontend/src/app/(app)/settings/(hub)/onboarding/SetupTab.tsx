"use client";

import { useState } from "react";
import { patchLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";

export function SetupTab({ config, onUpdate }: { config: LeadgenConfigStatus; onUpdate: (c: LeadgenConfigStatus) => void }) {
  const [fee, setFee] = useState(config.consultation_fee_inr?.toString() ?? "");
  const [duration, setDuration] = useState(config.consultation_duration_min?.toString() ?? "45");
  const [schedulingLink, setSchedulingLink] = useState(config.scheduling_link ?? "");
  const [expiryDays, setExpiryDays] = useState(config.lead_expiry_days?.toString() ?? "60");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await patchLeadgenConfig({
        consultation_fee_inr: fee ? Number(fee) : null,
        consultation_duration_min: Number(duration),
        scheduling_link: schedulingLink || null,
        lead_expiry_days: Number(expiryDays),
      });
      onUpdate(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-md">
      <label className="block">
        <span className="text-sm font-medium">Consultation fee (INR)</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={fee} onChange={(e) => setFee(e.target.value)} type="number" />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Duration (minutes)</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={duration} onChange={(e) => setDuration(e.target.value)} type="number" />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Scheduling link</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={schedulingLink} onChange={(e) => setSchedulingLink(e.target.value)} placeholder="https://calendly.com/..." />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Lead expiry (days)</span>
        <input className="mt-1 w-full rounded-md border px-3 py-2 text-sm" value={expiryDays} onChange={(e) => setExpiryDays(e.target.value)} type="number" />
      </label>
      <button onClick={handleSave} disabled={saving} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
