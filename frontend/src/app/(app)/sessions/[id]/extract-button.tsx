"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { postJson } from "@/lib/api-client";

export function ExtractButton({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function extract() {
    setError(null);
    setPending(true);
    const result = await postJson(`/api/grading/sessions/${sessionId}/extract`);
    setPending(false);
    if (!result.ok) return setError(result.error);
    router.refresh();
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={extract}
        disabled={pending}
        className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start"
      >
        {pending ? "Extracting…" : "Extract text"}
      </button>
      {pending && <p className="text-sm text-zinc-600 dark:text-zinc-400">This can take a while.</p>}
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
