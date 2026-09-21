import { annotate, formatMark, summarise, type ScriptBlock } from "@/lib/script";
import type { QuestionResult } from "@/lib/types";
import { MarkSymbols } from "./mark-symbols";
import { ScriptText } from "./script-text";
import { muted } from "./ui";

export function AnnotatedScript({
  blocks,
  results,
}: {
  blocks: ScriptBlock[];
  results: QuestionResult[];
}) {
  const items = annotate(blocks, results);
  const s = summarise(items);
  const totalSymbols = s.ticks + s.crosses;

  const summary = [
    `${s.ticks} tick${s.ticks === 1 ? "" : "s"} out of ${totalSymbols} — ${formatMark(s.awarded)}/${formatMark(s.max)}`,
    s.numeric > 0 &&
      `${s.numeric} question${s.numeric === 1 ? "" : "s"} shown as numbers, not counted in ticks`,
    s.notGraded > 0 && `${s.notGraded} not graded`,
  ].filter(Boolean);

  return (
    <div className="flex flex-col gap-3">
      <ol className="flex flex-col divide-y divide-zinc-300 rounded border border-zinc-300 dark:divide-zinc-700 dark:border-zinc-700">
        {items.map((item, i) => (
          <li
            key={i}
            className="grid grid-cols-1 gap-x-4 gap-y-2 p-3 sm:grid-cols-[minmax(0,1fr)_auto]"
          >
            {item.kind !== "preamble" && (
              <div className="max-sm:order-first sm:col-start-2 sm:row-start-1 sm:text-right">
                <MarkSymbols result={item.result} />
              </div>
            )}
            <ScriptText
              label={item.label}
              text={item.text}
              className="sm:col-start-1 sm:row-start-1"
            />
            {item.result?.reasoning && (
              <p className={`text-xs ${muted} sm:col-span-2`}>{item.result.reasoning}</p>
            )}
          </li>
        ))}
      </ol>
      <p role="status" className="text-sm font-medium">
        {summary.join(" · ")}
      </p>
    </div>
  );
}
