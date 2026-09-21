"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { apiRequest } from "@/lib/api-client";

// No `capture` attribute: with several accepted types, mobile browsers offer camera, photo library
// and files. `capture` would force the camera and block picking an existing file or PDF.
const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";

export function UploadForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);

    const data = new FormData(event.currentTarget);
    if (!(data.get("subject") as string)?.trim()) data.delete("subject");

    const result = await apiRequest("/api/grading/upload", { method: "POST", body: data });
    setPending(false);
    if (!result.ok) return setError(result.error);

    formRef.current?.reset();
    router.refresh();
  }

  return (
    <form ref={formRef} onSubmit={onSubmit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        Work to grade (photo, image or PDF)
        <input
          name="file"
          type="file"
          accept={ACCEPT}
          required
          className="rounded border border-zinc-400 p-2 text-base file:mr-3 file:rounded file:border-0 file:bg-zinc-200 file:px-3 file:py-2 file:text-sm dark:file:bg-zinc-700"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Subject (optional)
        <input
          name="subject"
          placeholder="e.g. mathematics"
          className="min-h-11 rounded border border-zinc-400 bg-transparent px-3 text-base"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start"
      >
        {pending ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}
