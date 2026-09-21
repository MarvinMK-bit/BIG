import Link from "next/link";
import { LocalTime } from "@/components/local-time";
import { StatusBadge } from "@/components/status-badge";
import { backendGet } from "@/lib/backend";
import { splitScript } from "@/lib/script";
import type { GradingRun, GradingSession, QuestionResult, RunView, Scheme } from "@/lib/types";
import { ExtractButton } from "./extract-button";
import { GradePanel } from "./grade-panel";

// Newest run for one grader path, with its results, so results survive a page refresh.
async function latestRun(
  runs: GradingRun[],
  path: GradingRun["grader_type"],
  sessionId: string,
): Promise<RunView | null> {
  const run = runs.find((r) => r.grader_type === path);
  if (!run) return null;
  const results = await backendGet<QuestionResult[]>(
    `/grading/sessions/${sessionId}/runs/${run.grading_run_id}/results`,
  );
  return { run, results };
}

export default async function SessionPage(props: PageProps<"/sessions/[id]">) {
  const { id } = await props.params;
  const sid = encodeURIComponent(id);
  const [session, schemes, runs] = await Promise.all([
    backendGet<GradingSession>(`/grading/sessions/${sid}`, { notFound: true }),
    backendGet<Scheme[]>("/grading/schemes"),
    backendGet<GradingRun[]>(`/grading/sessions/${sid}/runs`),
  ]);
  const completed = session.status === "completed";

  const newestFirst = runs.toSorted((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  const [schemeRun, llmRun] = await Promise.all([
    latestRun(newestFirst, "mark_scheme", sid),
    latestRun(newestFirst, "llm", sid),
  ]);
  const blocks = splitScript(session.ocr_markdown ?? "");

  return (
    <main className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard" className="text-sm underline">
          ← Sessions
        </Link>
      </div>

      <header className="flex flex-col gap-1">
        <h1 className="break-all text-xl font-semibold">{session.original_filename}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-zinc-600 dark:text-zinc-400">
          <StatusBadge status={session.status} />
          <span>{session.subject ?? "No subject"}</span>
          <LocalTime iso={session.created_at} />
        </div>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Extracted text</h2>
        {session.status === "pending" && <ExtractButton sessionId={session.id} />}
        {session.status === "processing" && (
          <p className="text-sm">Extraction is in progress. Reload this page in a moment.</p>
        )}
        {session.status === "failed" && (
          <p role="alert" className="text-sm text-red-600">
            Extraction failed{session.error_message ? `: ${session.error_message}` : "."}
          </p>
        )}
        {completed && session.ocr_markdown !== null && (
          <details open={!schemeRun && !llmRun}>
            <summary className="cursor-pointer text-sm underline">Show raw text</summary>
            <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded border border-zinc-300 bg-black/[.03] p-3 font-mono text-sm dark:border-zinc-700 dark:bg-white/[.05]">
              {session.ocr_markdown}
            </pre>
          </details>
        )}
      </section>

      <GradePanel
        sessionId={session.id}
        enabled={completed}
        schemes={schemes}
        blocks={blocks}
        schemeRun={schemeRun}
        llmRun={llmRun}
      />
    </main>
  );
}
