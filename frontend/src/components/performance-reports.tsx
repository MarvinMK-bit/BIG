"use client";

import { useId, useRef, useState } from "react";
import { RelativeTime } from "@/components/relative-time";
import { muted } from "@/components/ui";
import { apiRequest, postJson } from "@/lib/api-client";
import { reportListPath, type PerformanceReport, type ReportWithDisputes } from "@/lib/types";

const linkButton = "min-h-9 text-sm underline disabled:opacity-50";
const field =
  "w-full rounded border border-zinc-400 bg-transparent px-3 py-2 text-base sm:text-sm dark:border-zinc-600";
const primaryButton =
  "min-h-11 rounded bg-foreground px-4 text-sm text-background disabled:opacity-50";
const selfBadge =
  "inline-block rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-900 dark:text-amber-100";

function percent(accuracy: number): string {
  return `${(accuracy * 100).toFixed(1).replace(/\.0$/, "")}%`;
}

export function PerformanceReports({
  schemeVersion,
  initialItems,
}: {
  schemeVersion: string;
  // Fetched by the server component, so the section renders without a loading state
  initialItems: ReportWithDisputes[];
}) {
  const [items, setItems] = useState(initialItems);
  // The top-level report the form is disputing, if any
  const [disputing, setDisputing] = useState<PerformanceReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const formRef = useRef<HTMLDivElement>(null);

  async function reload() {
    const result = await apiRequest<ReportWithDisputes[]>(`/api${reportListPath(schemeVersion)}`, {
      method: "GET",
    });
    if (!result.ok) return setError(result.error);
    setError(null);
    setItems(result.data);
  }

  function startDispute(report: PerformanceReport) {
    setDisputing(report);
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="flex flex-col gap-4">
      {items.length === 0 ? (
        <p className={`text-sm ${muted}`}>No reports yet.</p>
      ) : (
        <ol className="flex flex-col gap-4">
          {items.map((report) => (
            <li key={report.id} className="flex flex-col gap-3">
              <ReportItem report={report} onDispute={() => startDispute(report)} />
              {report.disputed_by.length > 0 && (
                <ol className="ml-3 flex flex-col gap-3 border-l-2 border-zinc-300 pl-3 sm:ml-4 sm:pl-4 dark:border-zinc-700">
                  {report.disputed_by.map((dispute) => (
                    <li key={dispute.id}>
                      <ReportItem report={dispute} />
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ol>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      <div
        ref={formRef}
        className="flex scroll-mt-4 flex-col gap-3 border-t border-zinc-300 pt-4 dark:border-zinc-700"
      >
        <p className={`text-sm ${muted}`}>
          Reports are self-reported and unverified. Anyone may test the same scheme and publish a
          conflicting report — disputes stand alongside what they dispute, and the community decides
          what to make of them. Never include student names, scripts, or any identifying data. Sats
          currently reward well-designed schemes, not reports. Whether validation work should also
          earn sats is an open question — say so in the feedback thread.
        </p>
        <ReportForm
          // Remount on a new target so the form starts clean
          key={disputing?.id ?? "new"}
          schemeVersion={schemeVersion}
          disputing={disputing}
          onCancelDispute={() => setDisputing(null)}
          onDone={async () => {
            setDisputing(null);
            await reload();
          }}
        />
      </div>
    </div>
  );
}

function ReportItem({ report, onDispute }: { report: PerformanceReport; onDispute?: () => void }) {
  return (
    <article className="flex flex-col gap-1">
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
        <span className={`font-mono text-xs ${muted}`}>{report.public_ref}</span>
        <span className="font-medium">{report.author_username}</span>
        {report.tester_context && <span className={muted}>{report.tester_context}</span>}
        <span className={`text-xs ${muted}`}>
          <RelativeTime iso={report.created_at} />
        </span>
        {report.is_author_self_report && <span className={selfBadge}>self-report by scheme author</span>}
      </header>

      {report.disputes_public_ref && (
        <p className={`text-xs ${muted}`}>Disputes {report.disputes_public_ref}</p>
      )}

      <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="text-lg font-semibold tabular-nums">{percent(report.accuracy)}</span>
        <span className={`tabular-nums ${muted}`}>
          {report.correct_decisions} / {report.questions_judged} decisions correct ·{" "}
          {report.scripts_tested} {report.scripts_tested === 1 ? "script" : "scripts"}
        </span>
      </p>

      <p className="text-sm">
        {report.paper_type}
        {report.level && <span className={muted}> · {report.level}</span>}
      </p>

      {report.method_notes && (
        <p className="whitespace-pre-wrap break-words text-sm">{report.method_notes}</p>
      )}

      {onDispute && (
        <div>
          <button onClick={onDispute} className={linkButton}>
            Dispute this report
          </button>
        </div>
      )}
    </article>
  );
}

// Empty number inputs stay "" so the field can be cleared while typing.
type Counts = { scripts: string; judged: string; correct: string };

function ReportForm({
  schemeVersion,
  disputing,
  onCancelDispute,
  onDone,
}: {
  schemeVersion: string;
  disputing: PerformanceReport | null;
  onCancelDispute: () => void;
  onDone: () => Promise<void>;
}) {
  const id = useId();
  const [counts, setCounts] = useState<Counts>({ scripts: "", judged: "", correct: "" });
  const [paperType, setPaperType] = useState(disputing?.paper_type ?? "");
  const [level, setLevel] = useState(disputing?.level ?? "");
  const [context, setContext] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const judged = Number(counts.judged);
  const correct = Number(counts.correct);
  const tooMany = counts.judged !== "" && counts.correct !== "" && correct > judged;
  const ready = counts.scripts !== "" && counts.judged !== "" && counts.correct !== "" && paperType.trim();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const result = await postJson<PerformanceReport>("/api/reports", {
      mark_scheme_version: schemeVersion,
      disputes_id: disputing?.id ?? null,
      scripts_tested: Number(counts.scripts),
      questions_judged: judged,
      correct_decisions: correct,
      paper_type: paperType,
      level: level.trim() || null,
      tester_context: context.trim() || null,
      method_notes: notes.trim() || null,
    });
    setSaving(false);
    if (!result.ok) return setError(result.error);
    setCounts({ scripts: "", judged: "", correct: "" });
    setNotes("");
    await onDone();
  }

  const count = (key: keyof Counts, label: string, min: number, hint?: string) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={`${id}-${key}`} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={`${id}-${key}`}
        type="number"
        inputMode="numeric"
        min={min}
        step={1}
        required
        value={counts[key]}
        onChange={(e) => setCounts({ ...counts, [key]: e.target.value })}
        className={field}
      />
      {hint && <span className={`text-xs ${muted}`}>{hint}</span>}
    </div>
  );

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <h3 className="text-base font-semibold">
        {disputing ? `Dispute ${disputing.public_ref}` : "Report performance"}
      </h3>

      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-version`} className="text-sm font-medium">
          Mark scheme version
        </label>
        <input id={`${id}-version`} value={schemeVersion} readOnly className={`${field} ${muted}`} />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {count("scripts", "Scripts tested", 1)}
        {count("judged", "Questions judged", 1)}
        {count("correct", "Correct decisions", 0, "Where the scheme's verdict was right")}
      </div>
      {tooMany && (
        <p role="alert" className="text-sm text-red-600">
          Correct decisions can&apos;t exceed questions judged.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-paper`} className="text-sm font-medium">
            Paper type
          </label>
          <input
            id={`${id}-paper`}
            value={paperType}
            onChange={(e) => setPaperType(e.target.value)}
            required
            maxLength={200}
            placeholder="e.g. UNEB S4 Mathematics"
            className={field}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-level`} className="text-sm font-medium">
            Level <span className={`font-normal ${muted}`}>(optional)</span>
          </label>
          <input
            id={`${id}-level`}
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            maxLength={200}
            placeholder="e.g. S4"
            className={field}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-context`} className="text-sm font-medium">
          About you <span className={`font-normal ${muted}`}>(optional)</span>
        </label>
        <input
          id={`${id}-context`}
          value={context}
          onChange={(e) => setContext(e.target.value)}
          maxLength={200}
          placeholder="e.g. Teacher, 12 years"
          className={field}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-notes`} className="text-sm font-medium">
          Method <span className={`font-normal ${muted}`}>(optional)</span>
        </label>
        <textarea
          id={`${id}-notes`}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          maxLength={10000}
          placeholder="How you decided whether each verdict was correct"
          className={field}
        />
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <button type="submit" disabled={saving || !ready || tooMany} className={primaryButton}>
          {saving ? "Publishing…" : disputing ? "Publish dispute" : "Publish report"}
        </button>
        {disputing && (
          <button type="button" onClick={onCancelDispute} className={linkButton}>
            Cancel dispute
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </form>
  );
}
