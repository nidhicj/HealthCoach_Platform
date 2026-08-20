"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import {
  getIntakeConfig,
  submitIntake,
  IntakeNotFoundError,
  IntakeDuplicateEmailError,
  IntakeRateLimitError,
  IntakeValidationError,
  type IntakeConfig,
  type Question,
} from "@/lib/api/intake";

type LoadState = "loading" | "not_found" | "load_error" | "ready";

// The fixed question keys PHASE-01 always seeds (see backend/src/api/intake.py's
// _FULL_NAME_KEY/_EMAIL_KEY/_PHONE_KEY) get purpose-built input types; every other
// free_text question (custom, or the longer-answer fixed ones) gets a textarea.
const SINGLE_LINE_KEYS = new Set(["full_name", "email", "phone", "age"]);

function freeTextInputType(key: string): string {
  if (key === "email") return "email";
  if (key === "phone") return "tel";
  if (key === "age") return "number";
  return "text";
}

function QuestionField({
  question,
  value,
  onChange,
}: {
  question: Question;
  value: string;
  onChange: (value: string) => void;
}) {
  const inputId = `intake-q-${question.key}`;

  if (question.type === "multiple_choice") {
    return (
      <fieldset className="space-y-2">
        <legend className="font-sans text-sm font-medium text-foreground">
          {question.text}
          {question.required && <span className="text-destructive"> *</span>}
        </legend>
        <div className="space-y-1.5">
          {(question.options ?? []).map((option) => (
            <label
              key={option}
              className="flex items-center gap-2 font-sans text-sm text-foreground"
            >
              <input
                type="radio"
                name={question.key}
                value={option}
                checked={value === option}
                required={question.required}
                onChange={(e) => onChange(e.target.value)}
                className="h-4 w-4 accent-primary"
              />
              {option}
            </label>
          ))}
        </div>
      </fieldset>
    );
  }

  if (question.type === "scale") {
    return (
      <label className="block" htmlFor={inputId}>
        <span className="text-sm font-medium">
          {question.text}
          {question.required && <span className="text-destructive"> *</span>}
        </span>
        <select
          id={inputId}
          value={value}
          required={question.required}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
        >
          <option value="" disabled>
            Select a number (1–10)
          </option>
          {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    );
  }

  // free_text
  const longForm = !SINGLE_LINE_KEYS.has(question.key);

  return (
    <label className="block" htmlFor={inputId}>
      <span className="text-sm font-medium">
        {question.text}
        {question.required && <span className="text-destructive"> *</span>}
      </span>
      {longForm ? (
        <textarea
          id={inputId}
          value={value}
          required={question.required}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
        />
      ) : (
        <input
          id={inputId}
          type={freeTextInputType(question.key)}
          value={value}
          required={question.required}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
        />
      )}
    </label>
  );
}

export default function IntakePage() {
  const { slug } = useParams<{ slug: string }>();
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [config, setConfig] = useState<IntakeConfig | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [consentChecked, setConsentChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [confirmedEmail, setConfirmedEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    getIntakeConfig(slug)
      .then((c) => {
        setConfig(c);
        setLoadState("ready");
      })
      .catch((err) => {
        setLoadState(err instanceof IntakeNotFoundError ? "not_found" : "load_error");
      });
  }, [slug]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!config || !consentChecked || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitIntake(slug, { consent_ack: true, ...values });
      setConfirmedEmail(values["email"] || null);
      setConfirmed(true);
    } catch (err) {
      if (
        err instanceof IntakeDuplicateEmailError ||
        err instanceof IntakeRateLimitError ||
        err instanceof IntakeValidationError
      ) {
        setSubmitError(err.message);
      } else {
        setSubmitError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loadState === "loading") {
    return (
      <main className="mx-auto max-w-md px-4 py-16">
        <p className="font-sans text-sm text-muted-foreground">Loading…</p>
      </main>
    );
  }

  if (loadState === "not_found") {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Page not found</h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          This intake link doesn&apos;t seem to be valid. Please check the link or contact
          your health coach.
        </p>
      </main>
    );
  }

  if (loadState === "load_error" || !config) {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Something went wrong</h1>
        <p className="mt-2 font-sans text-sm text-muted-foreground">
          Could not load this page right now. Please try again in a moment.
        </p>
      </main>
    );
  }

  if (confirmed) {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="font-heading text-2xl font-bold text-foreground">Thank you</h1>
        <p className="mt-3 font-sans text-sm text-foreground">
          We&apos;ve received your responses and will send your next steps to{" "}
          <strong>{confirmedEmail ?? "your email"}</strong> shortly.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-md px-4 py-10">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        {config.hc_photo_url && (
          // eslint-disable-next-line @next/next/no-img-element -- no next/image usage
          // exists anywhere else in this app; plain <img> matches convention.
          <img
            src={config.hc_photo_url}
            alt={config.hc_name}
            className="h-20 w-20 rounded-full object-cover"
          />
        )}
        <h1 className="font-heading text-2xl font-bold text-foreground">{config.hc_name}</h1>
        <p className="font-sans text-sm text-muted-foreground">
          Please complete this short questionnaire to get started.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {config.questionnaire.map((q) => (
          <QuestionField
            key={q.key}
            question={q}
            value={values[q.key] ?? ""}
            onChange={(v) => setValues((prev) => ({ ...prev, [q.key]: v }))}
          />
        ))}

        <div className="rounded-md border border-border bg-muted/30 p-3">
          <label className="flex items-start gap-2 font-sans text-sm text-foreground">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(e) => setConsentChecked(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
            />
            <span>
              Your responses will be shared only with {config.hc_name} for the purpose of
              your initial health consultation. We do not share your information with any
              third party.
            </span>
          </label>
        </div>

        {submitError && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {submitError}
          </p>
        )}

        <button
          type="submit"
          disabled={!consentChecked || submitting}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {submitting ? "Submitting…" : "Submit"}
        </button>
      </form>
    </main>
  );
}
