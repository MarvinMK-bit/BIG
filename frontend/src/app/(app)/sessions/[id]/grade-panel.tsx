"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { AnnotatedScript } from "@/components/annotated-script";
import { muted as mutedColor } from "@/components/ui";
import { LocalTime } from "@/components/local-time";
import { postJson } from "@/lib/api-client";
import type { ScriptBlock } from "@/lib/script";
import { type RunView, type Scheme, schemeOriginLabel } from "@/lib/types";

type Path = "scheme" | "llm";

const muted = "text-sm text-zinc-600 dark:text-zinc-400";

// Start of the backend's NoQuestionMarkersError message (services/grading/errors.py).
const NO_MARKERS_PREFIX = "No question numbers found";

function RunResult({ view, title, blocks }: { view: RunView; title: string; blocks: ScriptBlock[] }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-semibold">
        {title}
        <span className={`ml-2 font-normal ${muted}`}>
          graded <LocalTime iso={view.run.created_at} />
        </span>
      </h3>
      <AnnotatedScript blocks={blocks} results={view.results} />
    </div>
  );
}

export function GradePanel({
  sessionId,
  enabled,
  schemes,
  blocks,
  schemeRun,
  llmRun,
}: {
  sessionId: string;
  enabled: boolean;
  schemes: Scheme[];
  blocks: ScriptBlock[];
  schemeRun: RunView | null;
  llmRun: RunView | null;
}) {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [posting, setPosting] = useState(false);
  const [active, setActive] = useState<Path | null>(null);
  const [errors, setErrors] = useState<Partial<Record<Path, string>>>({});
  const [schemeVersion, setSchemeVersion] = useState(schemes[0]?.scheme_version ?? "");
  const [unnumbered, setUnnumbered] = useState(false);
  const [noMarkers, setNoMarkers] = useState(false);
  const selected = schemes.find((s) => s.scheme_version === schemeVersion);

  const busy = posting || refreshing;
  const running = (path: Path) => busy && active === path;

  async function grade(path: Path) {
    setActive(path);
    setErrors((e) => ({ ...e, [path]: undefined }));
    if (path === "scheme") setNoMarkers(false);
    setPosting(true);
    const result =
      path === "scheme"
        ? await postJson(`/api/grading/sessions/${sessionId}/grade/scheme`, {
            scheme_version: schemeVersion,
            unnumbered_mode: unnumbered,
          })
        : await postJson(`/api/grading/sessions/${sessionId}/grade/llm`);
    setPosting(false);
    if (!result.ok) {
      if (path === "scheme" && result.status === 422 && result.error.startsWith(NO_MARKERS_PREFIX)) {
        setNoMarkers(true);
      }
      return setErrors((e) => ({ ...e, [path]: result.error }));
    }
    // Reload from the server so the annotated view shows the stored run; `refreshing` keeps the
    // button in its loading state until the new results have arrived.
    startTransition(() => router.refresh());
  }

  const button =
    "min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start";
  const error = (path: Path) =>
    errors[path] && (
      <p role="alert" className="text-sm text-red-600">
        {errors[path]}
      </p>
    );

  return (
    <div className="flex flex-col gap-4">
      {!enabled && <p className={muted}>Grading is available once text extraction has completed.</p>}

      <section className="flex flex-col gap-3 rounded border border-zinc-300 p-4 dark:border-zinc-700">
        <h2 className="text-lg font-semibold">Grade with Mark Scheme</h2>
        {schemes.length === 0 ? (
          <div className="flex flex-col gap-1 text-sm">
            <p>
              No mark scheme available for this paper. A deterministic grade needs a scheme that
              matches the questions on this script.
            </p>
            <Link href="/schemes" className="underline sm:self-start">
              Upload a mark scheme
            </Link>
          </div>
        ) : (
          <>
            <label className="flex flex-col gap-1 text-sm">
              Scheme version
              <select
                value={schemeVersion}
                onChange={(e) => setSchemeVersion(e.target.value)}
                disabled={!enabled || busy}
                className="min-h-11 rounded border border-zinc-400 bg-background px-3 text-base"
              >
                {schemes.map((s) => (
                  <option key={s.scheme_version} value={s.scheme_version}>
                    {s.scheme_version} · {schemeOriginLabel(s)} · {s.subject ?? "No subject"} ·{" "}
                    {s.question_count} questions
                  </option>
                ))}
              </select>
            </label>
            {selected?.description && <p className={muted}>{selected.description}</p>}
            <div
              className={`flex flex-col gap-1 ${
                noMarkers ? "rounded outline outline-2 outline-offset-4 outline-amber-500" : ""
              }`}
            >
              <label className="flex min-h-11 items-start gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={unnumbered}
                  onChange={(e) => setUnnumbered(e.target.checked)}
                  disabled={!enabled || busy}
                  className="mt-0.5 size-5 shrink-0"
                />
                <span>This script has no question numbers — treat each line as one question</span>
              </label>
              <p className={`pl-8 text-xs ${mutedColor}`}>
                Only use this for working that isn&apos;t laid out as numbered answers.
              </p>
            </div>
            <button
              onClick={() => grade("scheme")}
              disabled={!enabled || busy || !schemeVersion}
              className={button}
            >
              {running("scheme") ? "Grading…" : "Grade with Mark Scheme"}
            </button>
          </>
        )}
        {noMarkers && errors.scheme ? (
          <div role="alert" className="flex flex-col gap-1 text-sm">
            <p>{errors.scheme}</p>
            <p className="text-amber-800 dark:text-amber-300">
              If this script really has no numbered answers, tick &ldquo;This script has no question
              numbers&rdquo; above and grade again.
            </p>
          </div>
        ) : (
          error("scheme")
        )}
        {schemeRun && (
          <RunResult
            view={schemeRun}
            blocks={blocks}
            title={`Mark scheme result — ${schemeRun.run.mark_scheme_version ?? "unknown scheme"}`}
          />
        )}
      </section>

      <section className="flex flex-col gap-3 rounded border border-zinc-300 p-4 dark:border-zinc-700">
        <h2 className="text-lg font-semibold">Grade with LLM</h2>
        <p className="text-sm text-amber-800 dark:text-amber-300">
          Note: this path uses a paid model. Each run incurs a cost.
        </p>
        <button onClick={() => grade("llm")} disabled={!enabled || busy} className={button}>
          {running("llm") ? "Grading…" : "Grade with LLM"}
        </button>
        {running("llm") && <p className={muted}>This can take a while.</p>}
        {error("llm")}
        {llmRun && <RunResult view={llmRun} blocks={blocks} title="LLM result" />}
      </section>
    </div>
  );
}
