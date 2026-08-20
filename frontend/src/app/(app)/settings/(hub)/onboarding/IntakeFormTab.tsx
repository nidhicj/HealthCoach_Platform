"use client";

import { useState } from "react";
import { patchLeadgenConfig, type LeadgenConfigStatus } from "@/lib/api/leadgen";

type Question = NonNullable<LeadgenConfigStatus["questionnaire"]>[number];

export function IntakeFormTab({ config, onUpdate }: { config: LeadgenConfigStatus; onUpdate: (c: LeadgenConfigStatus) => void }) {
  const [questions, setQuestions] = useState<Question[]>(config.questionnaire ?? []);
  const [saving, setSaving] = useState(false);

  function addCustomQuestion() {
    setQuestions([...questions, { key: `custom_${Date.now()}`, text: "", type: "free_text", required: false, removable: true }]);
  }

  function removeQuestion(key: string) {
    setQuestions(questions.filter((q) => q.key !== key));
  }

  async function handleSave() {
    setSaving(true);
    try {
      onUpdate(await patchLeadgenConfig({ questionnaire: questions }));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 max-w-lg">
      <div>
        <p className="text-sm font-medium mb-2">Required fields (always present)</p>
        {questions.filter((q) => !q.removable).map((q) => (
          <div key={q.key} className="text-sm text-muted-foreground py-1">{q.text}</div>
        ))}
      </div>
      <div>
        <p className="text-sm font-medium mb-2">Custom questions</p>
        {questions.filter((q) => q.removable).map((q) => (
          <div key={q.key} className="flex items-center gap-2 py-1">
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm"
              value={q.text}
              onChange={(e) => setQuestions(questions.map((x) => (x.key === q.key ? { ...x, text: e.target.value } : x)))}
            />
            <button onClick={() => removeQuestion(q.key)} className="text-sm text-destructive">Remove</button>
          </div>
        ))}
        <button onClick={addCustomQuestion} className="mt-2 text-sm underline">+ Add question</button>
      </div>
      <button onClick={handleSave} disabled={saving} className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50">
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
