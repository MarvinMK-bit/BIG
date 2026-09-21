import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import type { GraderAccuracy } from "@/lib/types";

const MIN_JUDGED = 30;

export default async function AccuracyPage() {
  const rows = await backendGet<GraderAccuracy[]>("/grading/accuracy");

  return (
    <main className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">Accuracy</h1>
        <p className={`text-sm ${muted}`}>
          How often each grader agreed with your verdicts on the student&apos;s answer.
        </p>
      </div>

      {rows.length === 0 ? (
        <p className={`text-sm ${muted}`}>
          No judged questions yet. Give a verdict on a question in a session&apos;s comparison view.
        </p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {rows.map((r) => (
            <li
              key={`${r.grader_type}|${r.mark_scheme_version ?? ""}`}
              className="flex flex-col gap-3 rounded border border-zinc-300 p-4 dark:border-zinc-700"
            >
              <h2 className="break-all font-semibold">
                {r.grader_type === "llm"
                  ? "LLM"
                  : `Mark scheme — ${r.mark_scheme_version ?? "unknown version"}`}
              </h2>
              <p className="text-3xl font-semibold">
                {r.accuracy === null ? "—" : `${Math.round(r.accuracy * 1000) / 10}%`}
              </p>
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <dt className={muted}>Judged questions</dt>
                  <dd className="font-medium">{r.judged_questions}</dd>
                </div>
                <div>
                  <dt className={muted}>Correct decisions</dt>
                  <dd className="font-medium">{r.correct_decisions}</dd>
                </div>
              </dl>
              {r.judged_questions < MIN_JUDGED && (
                <p className="text-sm text-amber-800 dark:text-amber-300">
                  Based on {r.judged_questions} judged question{r.judged_questions === 1 ? "" : "s"} —
                  too few to draw conclusions.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
