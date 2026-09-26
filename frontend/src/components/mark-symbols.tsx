import { formatAward, formatMark, markEarned, markLabels, marksFor } from "@/lib/script";
import type { MarkBreakdownItem, QuestionResult } from "@/lib/types";
import { muted } from "./ui";

// One ✓ per mark awarded and one ✗ per mark missed. Non-whole marks are shown as a number and
// flagged; a missing result is "not graded". Procedure-marked questions show each mark point with
// the mark it earned, e.g. "T - 1 ✓  M - 1 ✓  A - 1 ✓  D - 0 ✗".
export function MarkSymbols({ result }: { result: QuestionResult | null }) {
  if (result?.mark_breakdown?.length) return <CodedMarks items={result.mark_breakdown} />;
  const marks = marksFor(result);

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

function CodedMarks({ items }: { items: MarkBreakdownItem[] }) {
  const labels = markLabels(items);
  const earned = markEarned;
  const award = formatAward;
  const label = items.map((item, i) => (labels[i] ? `${labels[i]}: ` : "") + award(item)).join(", ");
  return (
    <span role="img" aria-label={label} className="flex flex-wrap gap-x-3 gap-y-1 sm:justify-end">
      {items.map((item, i) => (
        <span
          key={i}
          aria-hidden
          title={(labels[i] ? `${labels[i]}: ` : "") + item.reason}
          className="inline-flex items-baseline gap-1 whitespace-nowrap"
        >
          <span className="font-mono text-xs">{award(item)}</span>
          {earned(item) ? (
            <span className="text-lg leading-tight text-green-600 dark:text-green-400">✓</span>
          ) : (
            <span className="text-lg leading-tight text-red-600 dark:text-red-400">✗</span>
          )}
        </span>
      ))}
    </span>
  );
}
