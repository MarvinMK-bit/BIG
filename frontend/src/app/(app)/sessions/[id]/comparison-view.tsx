"use client";

import { useState } from "react";
import { MarkSymbols } from "@/components/mark-symbols";
import { ScriptText } from "@/components/script-text";
import { muted } from "@/components/ui";
import {
  formatMark,
  indexBlocks,
  indexResults,
  questionKey,
  questionLabel,
  type ScriptBlock,
} from "@/lib/script";
import type { QuestionResult, RunComparison } from "@/lib/types";
import { graderCall, type GraderCall } from "@/lib/verdict";
import { VerdictControl } from "./verdict-control";

function Call({ name, call }: { name: string; call: GraderCall }) {
  if (call === "ungraded") return <span className={muted}>{name}: not graded</span>;
  return (
    <span>
      {name}:{" "}
      {call === "right" ? (
        <span className="font-medium text-green-700 dark:text-green-400">right ✓</span>
      ) : (
        <span className="font-medium text-red-700 dark:text-red-400">wrong ✗</span>
      )}
    </span>
  );
}

export function ComparisonView({
  comparison,
  blocks,
  schemeResults,
  llmResults,
}: {
  comparison: RunComparison;
  blocks: ScriptBlock[];
  schemeResults: QuestionResult[];
  llmResults: QuestionResult[];
}) {
  const [onlyDisagreements, setOnlyDisagreements] = useState(false);
  const blockByKey = indexBlocks(blocks);
  const schemeByKey = indexResults(schemeResults);
  const llmByKey = indexResults(llmResults);

  const rows = comparison.questions.map((q) => {
    const key = questionKey(q.question_number, q.sub_part);
    return {
      q,
      key,
      label: questionLabel(q.question_number, q.sub_part),
      block: blockByKey.get(key) ?? null,
      scheme: schemeByKey.get(key) ?? null,
      llm: llmByKey.get(key) ?? null,
    };
  });
  const visible = onlyDisagreements ? rows.filter((r) => r.q.agree === false) : rows;

  const comparable = rows.filter((r) => r.q.agree !== null).length;
  const agreeing = rows.filter((r) => r.q.agree === true).length;
  const total = (mark: number | null) =>
    mark === null || comparison.max_total === null
      ? "—"
      : `${formatMark(mark)}/${formatMark(comparison.max_total)}`;

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-1 gap-3 rounded border border-zinc-300 p-3 text-sm sm:grid-cols-3 dark:border-zinc-700">
        <div>
          <dt className={muted}>Agreement rate</dt>
          <dd className="text-lg font-semibold">
            {comparison.agreement_rate === null
              ? "—"
              : `${Math.round(comparison.agreement_rate * 100)}%`}
          </dd>
          <dd className={`text-xs ${muted}`}>
            {agreeing} of {comparable} comparable question{comparable === 1 ? "" : "s"}
          </dd>
        </div>
        <div>
          <dt className={muted}>Mark scheme total{comparison.scheme_version && ` (${comparison.scheme_version})`}</dt>
          <dd className="text-lg font-semibold">{total(comparison.scheme_total)}</dd>
        </div>
        <div>
          <dt className={muted}>LLM total</dt>
          <dd className="text-lg font-semibold">{total(comparison.llm_total)}</dd>
        </div>
      </dl>

      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input
          type="checkbox"
          checked={onlyDisagreements}
          onChange={(e) => setOnlyDisagreements(e.target.checked)}
          className="size-5"
        />
        Show disagreements only
      </label>

      {visible.length === 0 ? (
        <p className={`text-sm ${muted}`}>
          No disagreements — the graders agree on every comparable question.
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {visible.map(({ q, key, label, block, scheme, llm }) => {
            const disagree = q.agree === false;
            const resultId = (scheme ?? llm)?.id;
            return (
              <li
                key={key}
                className={`flex flex-col gap-3 rounded border p-3 ${
                  disagree
                    ? "border-amber-500 bg-amber-100 dark:border-amber-600 dark:bg-amber-950/50"
                    : "border-zinc-300 dark:border-zinc-700"
                }`}
              >
                {disagree && (
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-900 dark:text-amber-200">
                    Graders disagree
                  </p>
                )}

                <ScriptText label={label} text={block?.text ?? null} />
                {q.extracted_answer && (
                  <p className={`text-xs ${muted}`}>
                    Extracted answer: <span className="font-mono">{q.extracted_answer}</span>
                  </p>
                )}

                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1">
                    <span className={`text-xs font-medium ${muted}`}>Mark scheme</span>
                    <MarkSymbols result={scheme} />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className={`text-xs font-medium ${muted}`}>LLM</span>
                    <MarkSymbols result={llm} />
                  </div>
                </div>

                {resultId && <VerdictControl resultId={resultId} verdict={q.human_verdict} />}

                {q.human_verdict !== null && (
                  <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                    <Call name="Mark scheme" call={graderCall(scheme, q.human_verdict)} />
                    <Call name="LLM" call={graderCall(llm, q.human_verdict)} />
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
