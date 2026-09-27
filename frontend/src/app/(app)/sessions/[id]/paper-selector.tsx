"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import { type GradingSession, type QuestionPaper, paperUsable } from "@/lib/types";

export function PaperSelector({
  sessionId,
  attached,
  papers,
}: {
  sessionId: string;
  attached: QuestionPaper | null;
  // The caller's own papers; only extracted ones are offered
  papers: QuestionPaper[];
}) {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const offered = papers.filter(paperUsable);
  // Keep a paper that is attached but unusable visible, so the select shows the truth
  const options = attached && !offered.some((p) => p.id === attached.id) ? [attached, ...offered] : offered;

  async function attach(paperId: string) {
    setError(null);
    setSaving(true);
    const result = await apiRequest<GradingSession>(`/api/grading/sessions/${sessionId}/paper`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_paper_id: paperId || null }),
    });
    setSaving(false);
    if (!result.ok) return setError(result.error);
    startTransition(() => router.refresh());
  }

  const busy = saving || refreshing;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">Question paper</h2>
      <p className={`text-sm ${muted}`}>
        Attaching the paper these questions came from lets the LLM mark against the questions as set,
        rather than inferring them from the script.
      </p>
      {options.length === 0 ? (
        <p className="text-sm">
          You have no extracted question papers.{" "}
          <Link href="/papers" className="underline">
            Upload one
          </Link>
          .
        </p>
      ) : (
        <label className="flex flex-col gap-1 text-sm">
          Paper
          <select
            value={attached?.id ?? ""}
            onChange={(e) => attach(e.target.value)}
            disabled={busy}
            className="min-h-11 rounded border border-zinc-400 bg-background px-3 text-base"
          >
            <option value="">None</option>
            {options.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title} · {p.subject ?? "No subject"}
                {paperUsable(p) ? "" : ` · ${p.status}, not usable yet`}
              </option>
            ))}
          </select>
        </label>
      )}
      {busy && <p className={`text-sm ${muted}`}>Saving…</p>}
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </section>
  );
}
