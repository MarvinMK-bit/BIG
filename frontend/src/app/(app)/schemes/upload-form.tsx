"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { apiRequest } from "@/lib/api-client";

export function SchemeUploadForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);

    const data = new FormData(event.currentTarget);
    const result = await apiRequest("/api/grading/schemes", { method: "POST", body: data });
    setPending(false);
    if (!result.ok) {
      // 422 is the scheme validator's message, which says exactly what's wrong: show it as-is.
      return setError(
        result.status === 409
          ? "A mark scheme with this name and version already exists. Bump the version in your YAML and upload again."
          : result.error,
      );
    }

    formRef.current?.reset();
    router.refresh();
  }

  return (
    <form ref={formRef} onSubmit={onSubmit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        Upload a mark scheme (.yaml or .yml)
        <input
          name="file"
          type="file"
          accept=".yaml,.yml"
          required
          className="rounded border border-zinc-400 p-2 text-base file:mr-3 file:rounded file:border-0 file:bg-zinc-200 file:px-3 file:py-2 file:text-sm dark:file:bg-zinc-700"
        />
      </label>
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
        {pending ? "Uploading…" : "Upload scheme"}
      </button>
    </form>
  );
}
