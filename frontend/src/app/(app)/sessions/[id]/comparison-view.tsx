"use client";

import { useState } from "react";
import { MarkSymbols } from "@/components/mark-symbols";
import { ScriptText } from "@/components/script-text";
import { muted } from "@/components/ui";
import {
  formatAward,
  formatMark,
  indexBlocks,
  indexResults,
  questionKey,
  markEarned,
  markLabels,
  questionLabel,
  sameMarkStructure,
  type ScriptBlock,
} from "@/lib/script";
import type {
  Feedback,
  MarkBreakdownItem,
  QuestionComparison,
  QuestionResult,
  RunComparison,
} from "@/lib/types";
import { graderCall, type GraderCall } from "@/lib/verdict";
import { FeedbackToggle } from "./feedback-toggle";
import { VerdictControl } from "./verdict-control";

function Call({ name, call }: { name: string; call: GraderCall }) {
  if (call === "ungraded") return <span className={muted}>{name}: not graded</span>;
  if (call === "invalid") return <span className={muted}>{name}: excluded (impossible mark pattern)</span>;
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

function Award({ item }: { item: MarkBreakdownItem }) {
  return (
    <span title={item.reason} className="inline-flex items-baseline gap-1 whitespace-nowrap">
      <span className="font-mono">{formatAward(item)}</span>
      {markEarned(item) ? (
        <span aria-hidden className="text-green-600 dark:text-green-400">✓</span>
      ) : (
        <span aria-hidden className="text-red-600 dark:text-red-400">✗</span>
      )}
    </span>
  );
}

// How far a grader marked before stopping, e.g. "3 of 4"; "—" when it can't be measured.
function progressText(progress: number | null, max: number | null): string {
  return progress === null || max === null ? "—" : `${progress} of ${max}`;
}

// Both graders used the same mark codes: one row per code with each grader's tick or cross.
// The graders are compared on the progress row at the foot; the codes above it are the detail.
function MarksByCode({
  q,
  scheme,
  llm,
}: {
  q: QuestionComparison;
  scheme: QuestionResult;
  llm: QuestionResult;
}) {
  const schemeMarks = scheme.mark_breakdown ?? [];
  const llmMarks = llm.mark_breakdown ?? [];
  const labels = markLabels(schemeMarks);
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className={`text-left text-xs ${muted}`}>
          <th scope="col" className="py-1 pr-3 font-medium">Code</th>
          <th scope="col" className="py-1 pr-3 font-medium">Mark scheme</th>
          <th scope="col" className="py-1 font-medium">LLM</th>
        </tr>
      </thead>
      <tbody>
        {schemeMarks.map((mark, i) => (
          <tr key={i}>
            <th scope="row" className="py-1 pr-3 pl-1 text-left font-mono font-normal">
              {labels[i] ?? mark.code}
            </th>
            <td className="py-1 pr-3">
              <Award item={mark} />
            </td>
            <td className="py-1">
              <Award item={llmMarks[i]} />
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="border-t border-zinc-300 dark:border-zinc-700">
          <th scope="row" className="py-1 pr-3 pl-1 text-left font-medium">
            Progress
          </th>
          <td className="py-1 pr-3 font-medium">{progressText(q.scheme_progress, q.progress_max)}</td>
          <td className="py-1 font-medium">
            {llm.invalid_mark_pattern ? (
              <span className={muted}>invalid pattern</span>
            ) : (
              progressText(q.llm_progress, q.progress_max)
            )}
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

export function ComparisonView({
  comparison,
  blocks,
  schemeResults,
  llmResults,
  feedbackByResult,
  username,
}: {
  comparison: RunComparison;
  blocks: ScriptBlock[];
  schemeResults: QuestionResult[];
  llmResults: QuestionResult[];
  // Keyed by the mark scheme run's result id, which is what feedback targets
  feedbackByResult: Record<string, Feedback[]>;
  username: string;
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
          {comparison.excluded_invalid_pattern > 0 && (
            <dd className={`text-xs ${muted}`}>
              {comparison.excluded_invalid_pattern} excluded for an invalid mark pattern
            </dd>
          )}
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
            const invalid = q.invalid_mark_pattern;
            const resultId = (scheme ?? llm)?.id;
            return (
              <li
                key={key}
                className={`flex flex-col gap-3 rounded border p-3 ${
                  disagree
                    ? "border-amber-500 bg-amber-100 dark:border-amber-600 dark:bg-amber-950/50"
                    : invalid
                      ? "border-dashed border-zinc-400 dark:border-zinc-600"
                      : "border-zinc-300 dark:border-zinc-700"
                }`}
              >
                {disagree && (
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-900 dark:text-amber-200">
                    Graders disagree
                  </p>
                )}
                {q.progress_note && <p className="text-sm font-medium">{q.progress_note}</p>}
                {invalid && (
                  <p className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>
                    Excluded from agreement: impossible mark pattern
                  </p>
                )}

                <ScriptText label={label} text={block?.text ?? null} />
                {q.extracted_answer && (
                  <p className={`text-xs ${muted}`}>
                    Extracted answer: <span className="font-mono">{q.extracted_answer}</span>
                  </p>
                )}

                {scheme && llm && sameMarkStructure(scheme, llm) ? (
                  <MarksByCode q={q} scheme={scheme} llm={llm} />
                ) : (
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
                )}

                {resultId && <VerdictControl resultId={resultId} verdict={q.human_verdict} />}

                {q.human_verdict !== null && (
                  <p className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                    <Call name="Mark scheme" call={graderCall(scheme, q.human_verdict)} />
                    <Call name="LLM" call={graderCall(llm, q.human_verdict)} />
                  </p>
                )}

                {scheme && (
                  <FeedbackToggle
                    resultId={scheme.id}
                    username={username}
                    initialItems={feedbackByResult[scheme.id] ?? []}
                  />
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
