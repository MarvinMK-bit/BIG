"use client";

import { useState } from "react";
import { filenameFrom, saveBlob } from "./save-blob";

// Fetched rather than linked, so a backend error (e.g. no questions found) shows here verbatim
// instead of replacing the page with raw JSON.
export function DocxDownload({ guideId }: { guideId: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setError(null);
    setPending(true);
    try {
      const res = await fetch(`/api/guides/${guideId}/docx`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const detail = (body as { detail?: unknown } | null)?.detail;
        return setError(typeof detail === "string" ? detail : `Download failed (${res.status})`);
      }
      saveBlob(await res.blob(), filenameFrom(res.headers.get("Content-Disposition"), "marking-guide.docx"));
    } catch {
      setError("Could not reach the server");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={download}
        disabled={pending}
        className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start"
      >
        {pending ? "Preparing…" : "Download Word document"}
      </button>
      {error && (
        <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
