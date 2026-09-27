"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { muted } from "@/components/ui";
import { apiRequest, postJson } from "@/lib/api-client";
import type { QuestionPaper } from "@/lib/types";

export function PaperActions({ paper }: { paper: QuestionPaper }) {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [active, setActive] = useState<"extract" | "delete" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(action: "extract" | "delete") {
    if (
      action === "delete" &&
      !confirm(`Delete "${paper.title}"? Scripts that use it will be detached from it. This can't be undone.`)
    ) {
      return;
    }
    setError(null);
    setActive(action);
    const result =
      action === "extract"
        ? await postJson<QuestionPaper>(`/api/papers/${paper.id}/extract`)
        : await apiRequest(`/api/papers/${paper.id}`, { method: "DELETE" });
    if (!result.ok) {
      setActive(null);
      return setError(result.error);
    }
    startTransition(() => {
      setActive(null);
      router.refresh();
    });
  }

  const busy = active !== null || refreshing;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {paper.status === "pending" && (
          <button
            onClick={() => run("extract")}
            disabled={busy}
            className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50"
          >
            {active === "extract" ? "Extracting…" : "Extract text"}
          </button>
        )}
        <button
          onClick={() => run("delete")}
          disabled={busy}
          className="min-h-11 rounded border border-red-600 px-4 text-sm text-red-700 disabled:opacity-50 dark:text-red-400"
        >
          {active === "delete" ? "Deleting…" : "Delete"}
        </button>
      </div>
      {active === "extract" && <p className={`text-sm ${muted}`}>This can take a while.</p>}
      {error && (
        <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
