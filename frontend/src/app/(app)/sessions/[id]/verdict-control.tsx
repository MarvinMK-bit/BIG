"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { apiRequest } from "@/lib/api-client";
import { muted } from "@/components/ui";

// "Was the student's answer correct?" — a verdict on the answer itself, not on either grader.
// The backend mirrors it across every run of this question, so either result id will do.
export function VerdictControl({ resultId, verdict }: { resultId: string; verdict: boolean | null }) {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [saving, setSaving] = useState(false);
  const [choice, setChoice] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const busy = saving || refreshing;
  // Show the pending choice straight away; once the refresh lands the server value takes over.
  const shown = busy ? choice : verdict;

  async function save(next: boolean | null) {
    setError(null);
    setChoice(next);
    setSaving(true);
    const result = await apiRequest(`/api/grading/results/${resultId}/verdict`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_correct: next }),
    });
    setSaving(false);
    if (!result.ok) return setError(result.error);
    startTransition(() => router.refresh());
  }

  const button = (active: boolean) =>
    `min-h-11 min-w-16 flex-1 rounded border px-4 text-sm disabled:opacity-50 sm:flex-none ${
      active
        ? "border-foreground bg-foreground text-background"
        : "border-zinc-400 bg-transparent"
    }`;

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium" id={`verdict-${resultId}`}>
        Was the student&apos;s answer correct?
      </p>
      <div role="group" aria-labelledby={`verdict-${resultId}`} className="flex gap-2">
        <button onClick={() => save(true)} disabled={busy} aria-pressed={shown === true} className={button(shown === true)}>
          Yes
        </button>
        <button onClick={() => save(false)} disabled={busy} aria-pressed={shown === false} className={button(shown === false)}>
          No
        </button>
        <button onClick={() => save(null)} disabled={busy || shown === null} className={button(false)}>
          Clear
        </button>
      </div>
      <p role="status" className={`text-xs ${muted}`}>
        {busy ? "Saving…" : shown === null ? "No verdict yet" : `Saved: ${shown ? "Yes" : "No"}`}
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
