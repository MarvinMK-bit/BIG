"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { muted } from "@/components/ui";
import { postJson } from "@/lib/api-client";

export function ExtractGuideButton({ guideId }: { guideId: string }) {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function extract() {
    setError(null);
    setPending(true);
    const result = await postJson(`/api/guides/${guideId}/extract`);
    setPending(false);
    if (!result.ok) return setError(result.error);
    startTransition(() => router.refresh());
  }

  const busy = pending || refreshing;
  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={extract}
        disabled={busy}
        className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start"
      >
        {busy ? "Extracting…" : "Extract text"}
      </button>
      {busy && <p className={`text-sm ${muted}`}>This can take a while.</p>}
      {error && (
        <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
