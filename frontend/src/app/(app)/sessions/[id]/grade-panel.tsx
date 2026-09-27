"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { AnnotatedScript } from "@/components/annotated-script";
import { muted as mutedColor } from "@/components/ui";
import { LocalTime } from "@/components/local-time";
import { postJson } from "@/lib/api-client";
import type { ScriptBlock } from "@/lib/script";
import { type QuestionPaper, type RunView, type Scheme, paperUsable, schemeOriginLabel } from "@/lib/types";

type Path = "scheme" | "llm";

const muted = "text-sm text-zinc-600 dark:text-zinc-400";

// Start of the backend's NoQuestionMarkersError message (services/grading/errors.py).
const NO_MARKERS_PREFIX = "No question numbers found";

// What the LLM run will be given besides the script, stated plainly either way.
function LlmInputs({ paper, schemeVersion }: { paper: QuestionPaper | null; schemeVersion: string }) {
  const usable = paperUsable(paper);
  return (
    <div className="flex flex-col gap-0.5 rounded bg-black/[.03] p-3 text-sm dark:bg-white/[.05]">
      <p className="font-medium">In use for this run</p>
      {!usable && !schemeVersion ? (
        <p>
          Neither a question paper nor a mark scheme is attached. The model works out the questions
          from the script itself and sets its own marks.
        </p>
      ) : (
        <>
          <p>
            Question paper:{" "}
            {usable && paper ? (
              <span className="font-medium">{paper.title}</span>
            ) : (
              "none — the model works out the questions from the script"
            )}
          </p>
          <p>
            Mark scheme:{" "}
            {schemeVersion ? (
              <span className="break-all font-medium">{schemeVersion}</span>
            ) : (
              "none — the model sets its own marks"
            )}
          </p>
        </>
      )}
      {paper && !usable && (
        <p className="text-amber-800 dark:text-amber-300">
          &ldquo;{paper.title}&rdquo; is attached but its text hasn&apos;t been extracted, so it
          won&apos;t be used.
        </p>
      )}
    </div>
  );
}

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
  paper,
  enabled,
  schemes,
  blocks,
  schemeRun,
  llmRun,
}: {
  sessionId: string;
  // The attached question paper, if any; used by the LLM path only
  paper: QuestionPaper | null;
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
  // "" is no scheme: the LLM grades on its own terms, as before
  const [llmScheme, setLlmScheme] = useState("");
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
        : await postJson(`/api/grading/sessions/${sessionId}/grade/llm`, {
            scheme_version: llmScheme || null,
          });
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
        {schemes.length > 0 && (
          <div className="flex flex-col gap-1">
            <label className="flex flex-col gap-1 text-sm">
              Align marks to a scheme (optional)
              <select
                value={llmScheme}
                onChange={(e) => setLlmScheme(e.target.value)}
                disabled={!enabled || busy}
                className="min-h-11 rounded border border-zinc-400 bg-background px-3 text-base"
              >
                <option value="">None</option>
                {schemes.map((s) => (
                  <option key={s.scheme_version} value={s.scheme_version}>
                    {s.scheme_version}
                  </option>
                ))}
              </select>
            </label>
            <p className={`text-xs ${mutedColor}`}>
              This tells the model how many marks to award and what each one is for, but not the
              answers, so the two graders stay independent.
            </p>
          </div>
        )}
        <LlmInputs paper={paper} schemeVersion={llmScheme} />
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
