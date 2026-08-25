"use client";

import { useState } from "react";
import { patchLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";

export function TestPanelTab({ config, onUpdate }: { config: LeadgenConfigStatus; onUpdate: (c: LeadgenConfigStatus) => void }) {
  const [standardTests, setStandardTests] = useState<string>((config.test_panel?.standard_tests ?? []).join(", "));
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await patchLeadgenConfig({
        test_panel: {
          standard_tests: standardTests.split(",").map((s) => s.trim()).filter(Boolean),
          condition_rules: config.test_panel?.condition_rules ?? [],
        },
      });
      onUpdate(updated);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-lg">
      <label className="block">
        <span className="text-sm font-medium">Standard baseline tests (comma-separated)</span>
        <textarea
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          rows={3}
          value={standardTests}
          onChange={(e) => setStandardTests(e.target.value)}
          placeholder="CBC, HbA1c, TSH, Lipid Profile"
        />
      </label>
      <p className="text-xs text-muted-foreground">
        Condition-specific test recommendations are now AI-drafted per Lead, based on their
        questionnaire responses, rather than configured here.
      </p>
      <button onClick={handleSave} disabled={saving} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
