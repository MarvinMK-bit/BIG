"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { apiRequest } from "@/lib/api-client";
import type { MarkingGuide } from "@/lib/types";

// As for scripts: no `capture`, so phones offer camera, photo library and files alike
const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";

const field = "min-h-11 rounded border border-zinc-400 bg-transparent px-3 text-base";

export function GuideUploadForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);

    const data = new FormData(event.currentTarget);
    for (const name of ["subject", "title"]) {
      if (!(data.get(name) as string)?.trim()) data.delete(name);
    }

    const result = await apiRequest<MarkingGuide>("/api/guides", { method: "POST", body: data });
    setPending(false);
    // The backend checks the file's own bytes; its message says exactly what's accepted
    if (!result.ok) return setError(result.error);

    formRef.current?.reset();
    router.push(`/guides/${result.data.id}`);
  }

  return (
    <form ref={formRef} onSubmit={onSubmit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        Marking guide (photo or PDF)
        <input
          name="file"
          type="file"
          accept={ACCEPT}
          required
          className="rounded border border-zinc-400 p-2 text-base file:mr-3 file:rounded file:border-0 file:bg-zinc-200 file:px-3 file:py-2 file:text-sm dark:file:bg-zinc-700"
        />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm">
          Title (optional)
          <input name="title" placeholder="e.g. S3 algebra test, June" className={field} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Subject (optional)
          <input name="subject" placeholder="e.g. mathematics" className={field} />
        </label>
      </div>
      {error && (
        <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start"
      >
        {pending ? "Uploading…" : "Upload guide"}
      </button>
    </form>
  );
}
