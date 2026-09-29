"use client";

import { useEffect, useRef, useState } from "react";
import { muted } from "@/components/ui";
import { filenameFrom, saveBlob } from "@/lib/save-blob";

type Style = "symbols" | "codes";
type Placement = "lines" | "margin";
type View = "annotated" | "mask";

// The backend endpoint for each view (api/v1/grading.py)
const ENDPOINT: Record<View, string> = { annotated: "annotated", mask: "mask" };

// Set by the backend to the placement it actually used (api/v1/grading.py, PLACEMENT_HEADER)
const PLACEMENT_HEADER = "X-Annotation-Placement";

const FALLBACK_NOTE =
  "Line positions could not be matched confidently — marks are placed in the margin by question.";

async function errorFrom(res: Response): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = (body as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : `Request failed (${res.status})`;
}

type Loaded = { key: string; url: string; blob: Blob; filename: string; placement: Placement };
type Failed = { key: string; error: string };

// The script image with the run's marks drawn in a margin beside it, or the Mask of Marks: the
// marks alone, for printing onto the student's original paper. Both are rendered by the backend.
export function AnnotatedPanel({ sessionId, runId }: { sessionId: string; runId: string }) {
  const [view, setView] = useState<View>("annotated");
  const [style, setStyle] = useState<Style>("symbols");
  const [placement, setPlacement] = useState<Placement>("lines");
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState<Failed | null>(null);
  const [pdfPending, setPdfPending] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const printFrame = useRef<HTMLIFrameElement | null>(null);

  const query = new URLSearchParams({ run_id: runId, style, placement }).toString();
  const key = `${view}/${sessionId}?${query}`;

  useEffect(() => {
    const controller = new AbortController();
    let url: string | null = null;
    (async () => {
      try {
        const res = await fetch(`/api/grading/sessions/${sessionId}/${ENDPOINT[view]}?${query}`, {
          signal: controller.signal,
        });
        if (!res.ok) {
          setFailed({ key, error: await errorFrom(res) });
          return;
        }
        const blob = await res.blob();
        url = URL.createObjectURL(blob);
        setLoaded({
          key,
          url,
          blob,
          filename: filenameFrom(res.headers.get("Content-Disposition"), `${view}-script.png`),
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
  }, [sessionId, view, query, key]);

  // The print frame's blob URL goes when the panel does
  useEffect(
    () => () => {
      const frame = printFrame.current;
      if (frame) {
        URL.revokeObjectURL(frame.src);
        frame.remove();
      }
    },
    [],
  );

  async function fetchPdf(): Promise<{ blob: Blob; filename: string } | null> {
    setPdfError(null);
    setPdfPending(true);
    try {
      const res = await fetch(`/api/grading/sessions/${sessionId}/mask.pdf?${query}`);
      if (!res.ok) {
        setPdfError(await errorFrom(res));
        return null;
      }
      const filename = filenameFrom(res.headers.get("Content-Disposition"), "mask-of-marks.pdf");
      return { blob: await res.blob(), filename };
    } catch {
      setPdfError("Could not reach the server");
      return null;
    } finally {
      setPdfPending(false);
    }
  }

  async function downloadPdf() {
    const pdf = await fetchPdf();
    if (pdf) saveBlob(pdf.blob, pdf.filename);
  }

  // Loads the PDF into a hidden frame and opens the print dialog for it. Browsers that won't
  // print a PDF from a frame get it in a new tab instead, to print from there.
  async function printPdf() {
    const pdf = await fetchPdf();
    if (!pdf) return;
    const url = URL.createObjectURL(pdf.blob);
    const previous = printFrame.current;
    if (previous) {
      URL.revokeObjectURL(previous.src);
      previous.remove();
    }
    const frame = document.createElement("iframe");
    frame.style.position = "fixed";
    frame.style.width = "0";
    frame.style.height = "0";
    frame.style.border = "0";
    frame.style.visibility = "hidden";
    frame.onload = () => {
      try {
        frame.contentWindow?.focus();
        frame.contentWindow?.print();
      } catch {
        window.open(url, "_blank", "noopener");
      }
    };
    frame.src = url;
    document.body.appendChild(frame);
    printFrame.current = frame;
  }

  // Anything loaded for other settings is stale: it stays on screen, dimmed, until the new one lands
  const error = failed?.key === key ? failed.error : null;
  const pending = loaded?.key !== key && !error;
  const fellBack = !pending && loaded?.placement === "margin" && placement === "lines";

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">Annotated script</h2>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <Toggle
          label="View"
          value={view}
          onChange={setView}
          options={[
            ["annotated", "Annotated"],
            ["mask", "Mask of Marks"],
          ]}
        />
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
        {view === "annotated" ? (
          <button
            onClick={() => loaded && saveBlob(loaded.blob, loaded.filename)}
            disabled={!loaded || pending}
            className="min-h-11 rounded bg-foreground px-4 text-sm text-background disabled:opacity-50 sm:ml-auto"
          >
            Download image
          </button>
        ) : (
          <div className="flex gap-2 sm:ml-auto">
            <button
              onClick={downloadPdf}
              disabled={pdfPending}
              className="min-h-11 flex-1 rounded bg-foreground px-4 text-sm text-background disabled:opacity-50 sm:flex-none"
            >
              {pdfPending ? "Preparing…" : "Download PDF"}
            </button>
            <button
              onClick={printPdf}
              disabled={pdfPending}
              className="min-h-11 flex-1 rounded border border-zinc-400 px-4 text-sm disabled:opacity-50 sm:flex-none"
            >
              Print
            </button>
          </div>
        )}
      </div>

      {view === "mask" && (
        <p className={`text-sm ${muted}`}>
          The mask prints only the marks, so the student&apos;s original paper can be fed back
          through the printer and keeps their own work. Alignment depends on how the page was
          photographed — check the corner marks before printing a real script.
        </p>
      )}
      {pdfError && (
        <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
          {pdfError}
        </p>
      )}

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
          alt={
            loaded.key.startsWith("mask/")
              ? "The Mask of Marks: the marks alone on white, with a registration cross at each corner"
              : "The student's script with the marks drawn in a margin on the right"
          }
          // The mask is white on white: always framed, and never inverted in dark mode
          className={`w-full rounded border border-zinc-300 bg-white dark:border-zinc-700 ${pending ? "opacity-50" : ""}`}
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
