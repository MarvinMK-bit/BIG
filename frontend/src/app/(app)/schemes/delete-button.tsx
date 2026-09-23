"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { apiRequest } from "@/lib/api-client";

export function DeleteSchemeButton({ schemeVersion }: { schemeVersion: string }) {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!confirm(`Delete mark scheme ${schemeVersion}? This can't be undone.`)) return;
    setError(null);
    setPending(true);
    const result = await apiRequest(`/api/grading/schemes/${encodeURIComponent(schemeVersion)}`, {
      method: "DELETE",
    });
    setPending(false);
    if (!result.ok) return setError(result.error);
    startTransition(() => router.refresh());
  }

  const busy = pending || refreshing;
  return (
    <div className="flex flex-col gap-1 sm:items-end">
      <button
        onClick={onDelete}
        disabled={busy}
        className="min-h-9 rounded border border-red-600 px-3 text-sm text-red-700 disabled:opacity-50 sm:self-end dark:text-red-400"
      >
        {busy ? "Deleting…" : "Delete"}
      </button>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
