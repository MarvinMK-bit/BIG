import { formatMark, marksFor } from "@/lib/script";
import type { QuestionResult } from "@/lib/types";
import { muted } from "./ui";

// One ✓ per mark awarded and one ✗ per mark missed. Non-whole marks are shown as a number and
// flagged; a missing result is "not graded".
export function MarkSymbols({ result }: { result: QuestionResult | null }) {
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
