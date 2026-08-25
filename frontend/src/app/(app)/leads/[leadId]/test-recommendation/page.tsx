"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getLeadTestRecommendation,
  sendLeadTestRecommendation,
  type LeadTestRecommendationOut,
  type TestAdditionIn,
} from "@/lib/api/leads";

// Local-only editing shape for one addition row. `origin` and `original` never
// leave this component — the wire format the send endpoint accepts is just
// `{test, rationale}` (TestAdditionIn). They exist purely to drive the
// "AI suggested" vs. "added by you" vs. "edited" visual distinction below,
// which SoJo left to implementer judgment (task brief, item 6).
interface EditableAddition {
  id: string;
  test: string;
  rationale: string;
  origin: "ai" | "hc";
  original?: { test: string; rationale: string };
}

let nextRowId = 0;
function newRowId(): string {
  nextRowId += 1;
  return `addition-${nextRowId}`;
}

function fromDraft(a: { test: string; rationale: string }): EditableAddition {
  return {
    id: newRowId(),
    test: a.test,
    rationale: a.rationale,
    origin: "ai",
    original: { test: a.test, rationale: a.rationale },
  };
}

export default function LeadTestRecommendationPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const [data, setData] = useState<LeadTestRecommendationOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [additions, setAdditions] = useState<EditableAddition[]>([]);
  const [newTest, setNewTest] = useState("");
  const [newRationale, setNewRationale] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sendSuccess, setSendSuccess] = useState(false);

  useEffect(() => {
    if (!leadId) return;
    getLeadTestRecommendation(leadId)
      .then((res) => {
        setData(res);
        if (res.ready && res.draft_test_recommendation) {
          setAdditions(res.draft_test_recommendation.additions.map(fromDraft));
        }
      })
      .catch((err) =>
        setLoadError(err instanceof Error ? err.message : "Could not load this Lead."),
      );
  }, [leadId]);

  function updateAddition(id: string, field: "test" | "rationale", value: string) {
    setAdditions((prev) => prev.map((a) => (a.id === id ? { ...a, [field]: value } : a)));
    setSendSuccess(false);
  }

  function removeAddition(id: string) {
    setAdditions((prev) => prev.filter((a) => a.id !== id));
    setSendSuccess(false);
  }

  function addAddition() {
    const test = newTest.trim();
    if (!test) return;
    setAdditions((prev) => [
      ...prev,
      { id: newRowId(), test, rationale: newRationale.trim(), origin: "hc" },
    ]);
    setNewTest("");
    setNewRationale("");
    setSendSuccess(false);
  }

  async function handleSend() {
    setSending(true);
    setSendError(null);
    setSendSuccess(false);
    try {
      const payload: TestAdditionIn[] = additions.map((a) => ({
        test: a.test.trim(),
        rationale: a.rationale.trim(),
      }));
      const result = await sendLeadTestRecommendation(leadId, payload);
      setSendSuccess(true);
      // Reflect the finalized panel back so `status` / baseline on screen
      // matches what was just sent, without a second round-trip.
      setData((prev) =>
        prev
          ? { ...prev, status: result.status, draft_test_recommendation: result.test_recommendation }
          : prev,
      );
      // Clear the "edited" diff marker on AI-suggested rows now that their
      // current text is what was actually sent. Provenance (`origin`) is left
      // alone — an item the HC added is still "added by you" after sending it.
      setAdditions((prev) =>
        prev.map((a) =>
          a.origin === "ai" ? { ...a, original: { test: a.test, rationale: a.rationale } } : a,
        ),
      );
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Send failed");
    } finally {
      setSending(false);
    }
  }

  const loading = data === null && !loadError;
  const draft = data?.ready ? data.draft_test_recommendation : null;
  const hasBlankTest = additions.some((a) => a.test.trim() === "");

  return (
    <div className="max-w-3xl space-y-8">
      <Link
        href="/dashboard"
        className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
      >
        ← Dashboard
      </Link>

      <div>
        <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Lead review
        </p>
        <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
          Test recommendation
        </h1>
      </div>

      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {loadError && (
        <p className="font-sans text-sm text-destructive">{loadError}</p>
      )}

      {data && (
        <>
          {/* Lead summary header */}
          <div className="space-y-2 rounded-2xl border border-border bg-muted p-6">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-heading text-xl font-black text-foreground">
                {data.full_name}
              </h2>
              <Badge variant="outline">{data.status}</Badge>
            </div>
            <p className="font-sans text-sm text-muted-foreground">
              {data.email}
              {data.phone ? ` · ${data.phone}` : ""}
            </p>
          </div>

          {/* Questionnaire summary — read-only */}
          <section className="space-y-4">
            <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
              Questionnaire responses
            </h2>
            <Separator />
            {data.questionnaire_responses.length === 0 ? (
              <p className="font-sans text-sm text-muted-foreground">
                No questionnaire responses on file for this Lead.
              </p>
            ) : (
              <dl className="space-y-3">
                {data.questionnaire_responses.map((qa) => (
                  <div key={qa.question_key}>
                    <dt className="font-sans text-sm font-bold text-foreground">
                      {qa.question_text}
                    </dt>
                    <dd className="font-sans text-sm text-muted-foreground">
                      {qa.response_text?.trim() ? qa.response_text : "No response"}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </section>

          {!data.ready && (
            <section className="rounded-2xl border border-border bg-muted p-6">
              <p className="font-sans text-sm text-foreground">
                This Lead&rsquo;s AI-drafted test recommendation isn&rsquo;t ready yet. Check
                back shortly — this page can be reopened any time from the review email.
              </p>
            </section>
          )}

          {draft && (
            <>
              {/* Standard baseline — read-only per D-4, never editable here */}
              <section className="space-y-4">
                <div>
                  <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                    Standard baseline
                  </h2>
                  <p className="font-sans text-xs text-muted-foreground">
                    Set in your Test Panel settings. Not editable from this screen.
                  </p>
                </div>
                <Separator />
                {draft.standard.length === 0 ? (
                  <p className="font-sans text-sm text-muted-foreground">
                    No standard baseline tests configured.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {draft.standard.map((test) => (
                      <Badge key={test} variant="secondary">
                        {test}
                      </Badge>
                    ))}
                  </div>
                )}
              </section>

              {/* Additions — editable */}
              <section className="space-y-4">
                <div>
                  <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                    AI-suggested additions
                  </h2>
                  <p className="font-sans text-xs text-muted-foreground">
                    Condition-specific tests drafted from this Lead&rsquo;s answers. Edit,
                    remove, or add your own before sending.
                  </p>
                </div>
                <Separator />

                {additions.length === 0 ? (
                  <p className="font-sans text-sm text-muted-foreground">
                    No additions — only the standard baseline will be sent.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {additions.map((a) => {
                      const edited =
                        a.origin === "ai" &&
                        a.original &&
                        (a.original.test !== a.test || a.original.rationale !== a.rationale);
                      return (
                        <li
                          key={a.id}
                          className="space-y-2 rounded-lg border border-border bg-background p-4"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex flex-wrap items-center gap-2">
                              {a.origin === "ai" ? (
                                <Badge variant={edited ? "outline" : "secondary"}>
                                  {edited ? "AI suggested · edited" : "AI suggested"}
                                </Badge>
                              ) : (
                                <Badge variant="default">Added by you</Badge>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() => removeAddition(a.id)}
                              className="shrink-0 rounded p-1 text-muted-foreground hover:text-destructive"
                              aria-label={`Remove ${a.test || "addition"}`}
                              title="Remove"
                            >
                              <X className="size-4" />
                            </button>
                          </div>
                          <div className="space-y-1">
                            <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                              Test
                            </label>
                            <Input
                              value={a.test}
                              onChange={(e) => updateAddition(a.id, "test", e.target.value)}
                              placeholder="Test name"
                              aria-invalid={a.test.trim() === ""}
                            />
                            {a.test.trim() === "" && (
                              <p className="font-sans text-xs text-destructive">
                                Test name cannot be blank.
                              </p>
                            )}
                          </div>
                          <div className="space-y-1">
                            <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                              Rationale
                            </label>
                            <Textarea
                              value={a.rationale}
                              onChange={(e) => updateAddition(a.id, "rationale", e.target.value)}
                              placeholder="Why this test is recommended"
                              rows={2}
                            />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}

                {/* Add a new addition */}
                <div className="space-y-2 rounded-lg border border-dashed border-border p-4">
                  <label className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
                    Add a test
                  </label>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input
                      value={newTest}
                      onChange={(e) => setNewTest(e.target.value)}
                      placeholder="Test name"
                      className="sm:max-w-xs"
                    />
                    <Input
                      value={newRationale}
                      onChange={(e) => setNewRationale(e.target.value)}
                      placeholder="Rationale (optional)"
                      onKeyDown={(e) => e.key === "Enter" && addAddition()}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={addAddition}
                      disabled={!newTest.trim()}
                      className="shrink-0"
                    >
                      + Add
                    </Button>
                  </div>
                </div>
              </section>

              {/* Send */}
              <section className="space-y-3">
                <Button
                  onClick={handleSend}
                  disabled={sending || hasBlankTest}
                  variant="accent"
                  size="lg"
                >
                  {sending ? "Sending…" : "Send to Lead"}
                </Button>
                {hasBlankTest && (
                  <p className="font-sans text-xs text-destructive">
                    Remove or fill in the blank test name above before sending.
                  </p>
                )}
                {sendError && (
                  <p className="font-sans text-xs text-destructive">{sendError}</p>
                )}
                {sendSuccess && (
                  <p className="font-sans text-xs text-muted-foreground">
                    Sent — {data.full_name} has been emailed their finalized test
                    recommendation. You can keep editing and send again if needed.
                  </p>
                )}
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
