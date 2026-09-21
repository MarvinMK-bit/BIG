"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { AnnotatedScript } from "@/components/annotated-script";
import { LocalTime } from "@/components/local-time";
import { postJson } from "@/lib/api-client";
import type { ScriptBlock } from "@/lib/script";
import type { RunView, Scheme } from "@/lib/types";

type Path = "scheme" | "llm";

const muted = "text-sm text-zinc-600 dark:text-zinc-400";

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
  const selected = schemes.find((s) => s.scheme_version === schemeVersion);

  const busy = posting || refreshing;
  const running = (path: Path) => busy && active === path;

  async function grade(path: Path) {
    setActive(path);
    setErrors((e) => ({ ...e, [path]: undefined }));
    setPosting(true);
    const result =
      path === "scheme"
        ? await postJson(`/api/grading/sessions/${sessionId}/grade/scheme`, {
            scheme_version: schemeVersion,
          })
        : await postJson(`/api/grading/sessions/${sessionId}/grade/llm`);
    setPosting(false);
    if (!result.ok) return setErrors((e) => ({ ...e, [path]: result.error }));
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
          <p className={muted}>No mark schemes available.</p>
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
                    {s.scheme_version} · {s.subject} · {s.question_count} questions
                  </option>
                ))}
              </select>
            </label>
            {selected?.description && <p className={muted}>{selected.description}</p>}
          </>
        )}
        <button
          onClick={() => grade("scheme")}
          disabled={!enabled || busy || !schemeVersion}
          className={button}
        >
          {running("scheme") ? "Grading…" : "Grade with Mark Scheme"}
        </button>
        {error("scheme")}
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
