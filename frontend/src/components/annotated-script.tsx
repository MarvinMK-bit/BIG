import {
  annotate,
  formatMark,
  marksFor,
  summarise,
  type AnnotatedItem,
  type ScriptBlock,
} from "@/lib/script";
import type { QuestionResult } from "@/lib/types";

const muted = "text-zinc-600 dark:text-zinc-400";

function MarkSymbols({ item }: { item: AnnotatedItem }) {
  const marks = marksFor(item.result);

  if (marks.kind === "none") {
    return <span className={`text-sm ${muted}`}>not graded</span>;
  }
  if (marks.kind === "numeric") {
    return (
      <span className="flex flex-col gap-0.5 text-sm sm:items-end">
        <span className="font-mono">
          {formatMark(marks.awarded)}/{formatMark(marks.max)}
        </span>
        <span className="text-amber-800 dark:text-amber-300">
          ⚠ Not a whole mark — shown as a number
        </span>
      </span>
    );
  }
  return (
    <span
      role="img"
      aria-label={`${marks.awarded} of ${marks.max} marks`}
      className="flex flex-wrap gap-x-0.5 text-lg leading-tight"
    >
      {Array.from({ length: marks.max }, (_, i) =>
        i < marks.awarded ? (
          <span key={i} aria-hidden className="text-green-600 dark:text-green-400">
            ✓
          </span>
        ) : (
          <span key={i} aria-hidden className="text-red-600 dark:text-red-400">
            ✗
          </span>
        ),
      )}
    </span>
  );
}

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
                <MarkSymbols item={item} />
              </div>
            )}
            <div className="min-w-0 sm:col-start-1 sm:row-start-1">
              {item.label && <p className={`mb-1 text-xs font-medium ${muted}`}>{item.label}</p>}
              {item.text !== null ? (
                <pre className="whitespace-pre-wrap break-words font-mono text-sm">{item.text}</pre>
              ) : (
                <p className={`text-sm italic ${muted}`}>No matching text found in the script.</p>
              )}
            </div>
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
