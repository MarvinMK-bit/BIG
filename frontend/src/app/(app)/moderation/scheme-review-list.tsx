"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { MarkSymbols } from "@/components/mark-symbols";
import { RelativeTime } from "@/components/relative-time";
import { formatSats } from "@/components/reward-bits";
import { muted } from "@/components/ui";
import { apiRequest, postJson } from "@/lib/api-client";
import { formatMark, questionLabel } from "@/lib/script";
import type {
  PendingScheme,
  SchemeGradeResponse,
  SchemeQuestionSummary,
  SchemeReview,
  SchemeReviewStatus,
} from "@/lib/types";

type Decision = Exclude<SchemeReviewStatus, "pending">;

// One of the admin's own sessions with completed OCR, to try a scheme against.
export type TestSession = {
  id: string;
  original_filename: string;
  subject: string | null;
  created_at: string;
};

const ACTIONS: { status: Decision; label: string; className: string }[] = [
  { status: "accepted", label: "Accept", className: "border-green-700 text-green-800 dark:border-green-500 dark:text-green-300" },
  { status: "declined", label: "Decline", className: "border-red-600 text-red-700 dark:text-red-400" },
];

const input = "min-h-11 rounded border border-zinc-400 bg-background px-3 text-base";

function QuestionLine({ question }: { question: SchemeQuestionSummary }) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 text-sm">
      <span className="font-medium">{questionLabel(question.number, question.sub_part)}</span>
      {question.matcher === "procedure" ? (
        <>
          <span>procedure {question.procedure ?? "unnamed"}</span>
          <span className="font-mono text-xs">{question.mark_codes?.join(" ")}</span>
        </>
      ) : (
        <span>{question.matcher} match</span>
      )}
      <span className={`text-xs ${muted}`}>
        {formatMark(question.max_mark)} {question.max_mark === 1 ? "mark" : "marks"}
      </span>
    </li>
  );
}

function TestPanel({ scheme, sessions }: { scheme: PendingScheme; sessions: TestSession[] }) {
  const [sessionId, setSessionId] = useState(sessions[0]?.id ?? "");
  const [unnumbered, setUnnumbered] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<{ session: TestSession; run: SchemeGradeResponse } | null>(null);

  async function run() {
    const session = sessions.find((s) => s.id === sessionId);
    if (!session) return;
    setRunning(true);
    setError(null);
    const result = await postJson<SchemeGradeResponse>(
      `/api/grading/schemes/${encodeURIComponent(scheme.scheme_version)}/test`,
      { session_id: sessionId, unnumbered_mode: unnumbered },
    );
    setRunning(false);
    if (!result.ok) return setError(result.error);
    setOutcome({ session, run: result.data });
  }

  const results = outcome?.run.results ?? [];
  const awarded = results.reduce((total, r) => total + (r.mark_awarded ?? 0), 0);
  const max = results.reduce((total, r) => total + r.max_mark, 0);

  return (
    <details className="rounded border border-zinc-300 p-3 dark:border-zinc-700">
      <summary className="cursor-pointer text-sm font-medium">Test this scheme</summary>
      <div className="mt-3 flex flex-col gap-3">
        {sessions.length === 0 ? (
          <p className={`text-sm ${muted}`}>
            You have no scripts with completed text extraction to test against.{" "}
            <Link href="/dashboard" className="underline">
              Upload one
            </Link>
            .
          </p>
        ) : (
          <>
            <label className="flex flex-col gap-1 text-sm">
              One of your scripts
              <select
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                disabled={running}
                className={input}
              >
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.original_filename} · {s.subject ?? "No subject"} ·{" "}
                    {new Date(s.created_at).toLocaleDateString("en-GB")}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-h-11 items-start gap-3 text-sm">
              <input
                type="checkbox"
                checked={unnumbered}
                onChange={(e) => setUnnumbered(e.target.checked)}
                disabled={running}
                className="mt-0.5 size-5 shrink-0"
              />
              <span>This script has no question numbers — treat each line as one question</span>
            </label>
            <button
              onClick={run}
              disabled={running || !sessionId}
              className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start"
            >
              {running ? "Grading…" : "Grade with this scheme"}
            </button>
            <p className={`text-xs ${muted}`}>
              Test runs are kept out of accuracy figures and the script&apos;s own grading history.
            </p>
          </>
        )}

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        {outcome && (
          <div className="flex flex-col gap-2" aria-live="polite">
            <p className="text-sm">
              <span className="font-medium">{outcome.session.original_filename}</span>{" "}
              <span className={muted}>
                {formatMark(awarded)}/{formatMark(max)}
              </span>
            </p>
            <ol className="flex flex-col divide-y divide-zinc-200 rounded border border-zinc-300 dark:divide-zinc-800 dark:border-zinc-700">
              {results.map((r) => (
                <li key={r.id} className="flex flex-col gap-1 p-2 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-sm font-medium">{questionLabel(r.question_number, r.sub_part)}</span>
                    {r.reasoning && (
                      <span className={`whitespace-pre-wrap break-words text-xs ${muted}`}>{r.reasoning}</span>
                    )}
                  </div>
                  <MarkSymbols result={r} />
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </details>
  );
}

export function SchemeReviewList({
  initialItems,
  sessions,
}: {
  initialItems: PendingScheme[];
  sessions: TestSession[];
}) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  // Kept client-side, with the scheme itself, so decided schemes stay on screen (with the export
  // reminder) after the refresh that updates the nav badge drops them from initialItems
  const [decided, setDecided] = useState<Record<string, { scheme: PendingScheme; review: SchemeReview }>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function decide(scheme: PendingScheme, status: Decision) {
    const key = scheme.scheme_version;
    setBusy(key);
    setErrors((e) => ({ ...e, [key]: "" }));
    const result = await apiRequest<SchemeReview>(
      `/api/grading/schemes/${encodeURIComponent(key)}/review`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review_status: status, note: notes[key]?.trim() || null }),
      },
    );
    setBusy(null);
    if (!result.ok) return setErrors((e) => ({ ...e, [key]: result.error }));
    setDecided((d) => ({ ...d, [key]: { scheme, review: result.data } }));
    startTransition(() => router.refresh());
  }

  const pendingKeys = new Set(initialItems.map((s) => s.scheme_version));
  const items = [
    ...initialItems,
    ...Object.values(decided)
      .map((d) => d.scheme)
      .filter((s) => !pendingKeys.has(s.scheme_version)),
  ].toSorted((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

  if (items.length === 0) {
    return <p className={`text-sm ${muted}`}>No schemes awaiting review.</p>;
  }

  return (
    <ol className="flex flex-col gap-3">
      {items.map((scheme) => {
        const key = scheme.scheme_version;
        const review = decided[key]?.review;
        return (
          <li
            key={key}
            className={`flex flex-col gap-3 rounded border border-zinc-300 p-3 dark:border-zinc-700 ${
              review?.review_status === "declined" ? "opacity-60" : ""
            }`}
          >
            <header className="flex flex-col gap-1">
              <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <Link href={`/schemes/${encodeURIComponent(key)}`} className="break-all font-medium underline">
                  {scheme.name}
                </Link>
                <span className={`text-sm ${muted}`}>v{scheme.version}</span>
                <span className={`text-xs ${muted}`}>
                  <RelativeTime iso={scheme.created_at} />
                </span>
              </p>
              <p className={`text-sm ${muted}`}>
                by <span className="text-foreground">{scheme.contributor_username}</span>
                {!scheme.attribution_opt_in && " (exported as anonymous)"} · {scheme.subject ?? "No subject"} ·{" "}
                {scheme.question_count} {scheme.question_count === 1 ? "question" : "questions"} · {scheme.source}
              </p>
              {scheme.description && <p className="text-sm">{scheme.description}</p>}
            </header>

            {scheme.parse_error ? (
              <p role="alert" className="text-sm text-amber-800 dark:text-amber-300">
                This scheme no longer parses: {scheme.parse_error}
              </p>
            ) : (
              <ul className="flex flex-col gap-1">
                {scheme.questions.map((q, i) => (
                  <QuestionLine key={i} question={q} />
                ))}
              </ul>
            )}

            <details>
              <summary className="cursor-pointer text-sm">YAML</summary>
              <pre className="mt-2 overflow-x-auto rounded border border-zinc-300 bg-black/[.03] p-3 font-mono text-xs leading-relaxed dark:border-zinc-700 dark:bg-white/[.05]">
                {scheme.yaml_content}
              </pre>
            </details>

            <TestPanel scheme={scheme} sessions={sessions} />

            {review?.review_status === "accepted" ? (
              <div role="status" className="flex flex-col gap-0.5 text-sm">
                <p className="font-medium text-green-800 dark:text-green-300">
                  Accepted — export with{" "}
                  <code className="break-all font-mono text-xs">
                    python -m scripts.export_schemes --version {key}
                  </code>
                  , then commit.
                </p>
                <p className={`text-xs ${muted}`}>
                  {formatSats(review.reward_sats)} payable if this scheme is well designed.
                </p>
              </div>
            ) : review ? (
              <p role="status" className="text-sm font-medium">
                Declined
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                <label className="flex flex-col gap-1 text-sm">
                  Note (optional)
                  <textarea
                    value={notes[key] ?? ""}
                    onChange={(e) => setNotes((n) => ({ ...n, [key]: e.target.value }))}
                    disabled={busy !== null}
                    maxLength={2000}
                    rows={2}
                    className="rounded border border-zinc-400 bg-background px-3 py-2 text-base"
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  {ACTIONS.map((action) => (
                    <button
                      key={action.status}
                      onClick={() => decide(scheme, action.status)}
                      disabled={busy !== null}
                      className={`min-h-11 flex-1 rounded border px-4 text-sm disabled:opacity-50 sm:flex-none ${action.className}`}
                    >
                      {busy === key ? "…" : action.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {errors[key] && (
              <p role="alert" className="text-sm text-red-600">
                {errors[key]}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
