"use client";

import { useEffect, useState } from "react";
import { muted } from "@/components/ui";
import { filenameFrom, saveBlob } from "@/lib/save-blob";

type Style = "symbols" | "codes";
type Placement = "lines" | "margin";

// Set by the backend to the placement it actually used (api/v1/grading.py, PLACEMENT_HEADER)
const PLACEMENT_HEADER = "X-Annotation-Placement";

const FALLBACK_NOTE =
  "Line positions could not be matched confidently — marks are placed in the margin by question.";

type Loaded = { key: string; url: string; blob: Blob; filename: string; placement: Placement };
type Failed = { key: string; error: string };

// The script image with the run's marks drawn in a margin beside it, rendered by the backend.
export function AnnotatedPanel({ sessionId, runId }: { sessionId: string; runId: string }) {
  const [style, setStyle] = useState<Style>("symbols");
  const [placement, setPlacement] = useState<Placement>("lines");
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState<Failed | null>(null);

  const query = new URLSearchParams({ run_id: runId, style, placement }).toString();
  const key = `${sessionId}?${query}`;

  useEffect(() => {
    const controller = new AbortController();
    let url: string | null = null;
    (async () => {
      try {
        const res = await fetch(`/api/grading/sessions/${sessionId}/annotated?${query}`, {
          signal: controller.signal,
        });
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          const detail = (body as { detail?: unknown } | null)?.detail;
          setFailed({ key, error: typeof detail === "string" ? detail : `Request failed (${res.status})` });
          return;
        }
        const blob = await res.blob();
        url = URL.createObjectURL(blob);
        setLoaded({
          key,
          url,
          blob,
          filename: filenameFrom(res.headers.get("Content-Disposition"), "annotated-script.png"),
          placement: res.headers.get(PLACEMENT_HEADER) === "margin" ? "margin" : "lines",
        });
      } catch {
        if (!controller.signal.aborted) setFailed({ key, error: "Could not reach the server" });
      }
    })();
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [sessionId, query, key]);

  // Anything loaded for other settings is stale: it stays on screen, dimmed, until the new one lands
  const error = failed?.key === key ? failed.error : null;
  const pending = loaded?.key !== key && !error;
  const fellBack = !pending && loaded?.placement === "margin" && placement === "lines";

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Annotated script</h2>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <Toggle
          label="Marks"
          value={style}
          onChange={setStyle}
          options={[
            ["symbols", "✓ and ✗"],
            ["codes", "T/M/A/D codes"],
          ]}
        />
        <Toggle
          label="Placement"
          value={placement}
          onChange={setPlacement}
          options={[
            ["lines", "Beside each line"],
            ["margin", "By question"],
          ]}
        />
        <button
          onClick={() => loaded && saveBlob(loaded.blob, loaded.filename)}
          disabled={!loaded || pending}
          className="min-h-11 rounded bg-foreground px-4 text-sm text-background disabled:opacity-50 sm:ml-auto"
        >
          Download image
        </button>
      </div>

      {fellBack && (
        <p role="status" className="text-sm text-amber-800 dark:text-amber-300">
          {FALLBACK_NOTE}
        </p>
      )}
      {error && (
        <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
          {error}
        </p>
      )}
      {pending && (
        <p role="status" className={`text-sm ${muted}`}>
          Drawing the marks…
        </p>
      )}
      {loaded && !error && (
        // eslint-disable-next-line @next/next/no-img-element -- a blob URL, which next/image can't optimise
        <img
          src={loaded.url}
          alt="The student's script with the marks drawn in a margin on the right"
          className={`w-full rounded border border-zinc-300 dark:border-zinc-700 ${pending ? "opacity-50" : ""}`}
        />
      )}
    </section>
  );
}

function Toggle<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (next: T) => void;
  options: [T, string][];
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm font-medium">{label}</span>
      <div role="group" aria-label={label} className="flex gap-2">
        {options.map(([option, text]) => (
          <button
            key={option}
            onClick={() => onChange(option)}
            aria-pressed={value === option}
            className={`min-h-11 flex-1 rounded border px-4 text-sm sm:flex-none ${
              value === option
                ? "border-foreground bg-foreground text-background"
                : "border-zinc-400 bg-transparent"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
