import Link from "next/link";
import { LocalTime } from "@/components/local-time";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import { compareGraders, graderKey, graderLabel } from "@/lib/grader";
import type {
  AccuracyPoint,
  Bucket,
  GraderAccuracy,
  GraderVerdict,
  JudgedQuestion,
  VerdictHistory,
} from "@/lib/types";
import { AccuracyChart } from "./accuracy-chart";

const MIN_JUDGED = 30;
const PAGE_SIZE = 25;
const BUCKETS: Bucket[] = ["day", "week", "month"];

type View = { bucket: Bucket; everyone: boolean; page: number };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function hrefFor(view: View, change: Partial<View>): string {
  const next = { ...view, ...change };
  const params = new URLSearchParams();
  if (next.bucket !== "week") params.set("bucket", next.bucket);
  if (next.everyone) params.set("scope", "all");
  if (next.page > 1) params.set("page", String(next.page));
  const query = params.toString();
  return query ? `/accuracy?${query}` : "/accuracy";
}

function questionLabel(q: JudgedQuestion): string {
  return q.sub_part ? `${q.question_number}(${q.sub_part.replace(/[()]/g, "")})` : q.question_number;
}

function Segmented<T extends string | boolean>({
  label,
  options,
  current,
  href,
}: {
  label: string;
  options: { value: T; text: string }[];
  current: T;
  href: (value: T) => string;
}) {
  return (
    <nav aria-label={label} className="flex overflow-hidden rounded border border-zinc-300 text-sm dark:border-zinc-700">
      {options.map((o) => (
        <Link
          key={String(o.value)}
          href={href(o.value)}
          aria-current={o.value === current ? "page" : undefined}
          className={`px-3 py-1.5 ${
            o.value === current
              ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
              : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          {o.text}
        </Link>
      ))}
    </nav>
  );
}

function Agreement({ grader }: { grader: GraderVerdict | undefined }) {
  if (!grader) {
    return (
      <span className={muted}>
        <span aria-hidden>—</span>
        <span className="sr-only">not graded</span>
      </span>
    );
  }
  return grader.agreed ? (
    <span className="text-green-700 dark:text-green-400">
      <span aria-hidden>✓</span>
      <span className="sr-only">agreed</span>
    </span>
  ) : (
    <span className="text-red-700 dark:text-red-400">
      <span aria-hidden>✗</span>
      <span className="sr-only">disagreed</span>
    </span>
  );
}

function SummaryCards({ rows }: { rows: GraderAccuracy[] }) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {rows.map((r) => (
        <li
          key={graderKey(r)}
          className="flex flex-col gap-3 rounded border border-zinc-300 p-4 dark:border-zinc-700"
        >
          <h2 className="break-all font-semibold">{graderLabel(r)}</h2>
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
  );
}

function VerdictTable({
  history,
  view,
  viewerId,
}: {
  history: VerdictHistory;
  view: View;
  viewerId: string;
}) {
  const graders = [
    ...new Map(history.items.flatMap((q) => q.graders).map((g) => [graderKey(g), g])).values(),
  ].sort(compareGraders);
  const find = (q: JudgedQuestion, key: string) => q.graders.find((g) => graderKey(g) === key);

  // Admins can't open another user's session, so only their own rows link through
  const fileCell = (q: JudgedQuestion) =>
    q.owner_id === viewerId ? (
      <Link href={`/sessions/${q.session_id}`} className="break-all underline">
        {q.original_filename}
      </Link>
    ) : (
      <span className="break-all">{q.original_filename}</span>
    );
  const verdictText = (q: JudgedQuestion) => (q.verdict ? "Correct" : "Incorrect");
  const when = (q: JudgedQuestion) =>
    q.verdict_set_at ? <LocalTime iso={q.verdict_set_at} /> : <span className={muted}>—</span>;

  const lastPage = Math.max(1, Math.ceil(history.total / PAGE_SIZE));

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-lg font-semibold">Verdict history</h2>
        <p className={`text-sm ${muted}`}>
          {history.total} judged question{history.total === 1 ? "" : "s"}, newest verdict first.{" "}
          <span aria-hidden>✓</span> the grader agreed with the verdict, <span aria-hidden>✗</span>{" "}
          it didn&apos;t, — it didn&apos;t grade that question.
        </p>
      </div>

      {history.items.length === 0 ? (
        <p className={`text-sm ${muted}`}>No verdicts on this page.</p>
      ) : (
        <>
          {/* Phone width: one card per question */}
          <ul className="flex flex-col gap-2 sm:hidden">
            {history.items.map((q) => (
              <li
                key={`${q.session_id}|${questionLabel(q)}`}
                className="flex flex-col gap-1 rounded border border-zinc-300 p-3 text-sm dark:border-zinc-700"
              >
                <div className="flex items-baseline justify-between gap-2">
                  {fileCell(q)}
                  <span className="shrink-0 font-medium">Q{questionLabel(q)}</span>
                </div>
                <p className={muted}>
                  {when(q)}
                  {view.everyone ? ` · ${q.owner_username}` : ""}
                </p>
                <p className="break-words">
                  <span className={muted}>Answer:</span> {q.extracted_answer ?? "—"} ·{" "}
                  <span className="font-medium">{verdictText(q)}</span>
                </p>
                <ul className="flex flex-wrap gap-x-3">
                  {graders.map((g) => (
                    <li key={graderKey(g)} className="break-all">
                      {graderLabel(g)} <Agreement grader={find(q, graderKey(g))} />
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className={muted}>
                  <th className="py-2 pr-3 font-normal">Date</th>
                  {view.everyone && <th className="py-2 pr-3 font-normal">Owner</th>}
                  <th className="py-2 pr-3 font-normal">File</th>
                  <th className="py-2 pr-3 font-normal">Question</th>
                  <th className="py-2 pr-3 font-normal">Answer</th>
                  <th className="py-2 pr-3 font-normal">Verdict</th>
                  {graders.map((g) => (
                    <th key={graderKey(g)} className="py-2 pr-3 font-normal" title={graderLabel(g)}>
                      {g.grader_type === "llm" ? "LLM" : (g.mark_scheme_version ?? "Scheme")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.items.map((q) => (
                  <tr
                    key={`${q.session_id}|${questionLabel(q)}`}
                    className="border-t border-zinc-200 align-top dark:border-zinc-800"
                  >
                    <td className="py-2 pr-3">{when(q)}</td>
                    {view.everyone && <td className="py-2 pr-3">{q.owner_username}</td>}
                    <td className="py-2 pr-3">{fileCell(q)}</td>
                    <td className="py-2 pr-3">{questionLabel(q)}</td>
                    <td className="max-w-40 break-words py-2 pr-3">{q.extracted_answer ?? "—"}</td>
                    <td className="py-2 pr-3">{verdictText(q)}</td>
                    {graders.map((g) => (
                      <td key={graderKey(g)} className="py-2 pr-3 text-center text-base">
                        <Agreement grader={find(q, graderKey(g))} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {lastPage > 1 && (
        <nav aria-label="Verdict pages" className="flex items-center justify-between text-sm">
          {view.page > 1 ? (
            <Link href={hrefFor(view, { page: view.page - 1 })} className="underline">
              ← Newer
            </Link>
          ) : (
            <span />
          )}
          <span className={muted}>
            Page {view.page} of {lastPage}
          </span>
          {view.page < lastPage ? (
            <Link href={hrefFor(view, { page: view.page + 1 })} className="underline">
              Older →
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </section>
  );
}

export default async function AccuracyPage(props: PageProps<"/accuracy">) {
  const params = await props.searchParams;
  const me = await backendGet<{ id: string; is_admin: boolean }>("/auth/me");

  const requestedBucket = first(params.bucket);
  const view: View = {
    bucket: BUCKETS.includes(requestedBucket as Bucket) ? (requestedBucket as Bucket) : "week",
    everyone: me.is_admin && first(params.scope) === "all",
    page: Math.max(1, Number.parseInt(first(params.page) ?? "1", 10) || 1),
  };
  const scope = view.everyone ? "/global" : "";
  const offset = (view.page - 1) * PAGE_SIZE;

  const [rows, points, history] = await Promise.all([
    backendGet<GraderAccuracy[]>(`/grading/accuracy${scope}`),
    backendGet<AccuracyPoint[]>(`/grading/accuracy/history${scope}?bucket=${view.bucket}`),
    backendGet<VerdictHistory>(`/grading/verdicts${scope}?limit=${PAGE_SIZE}&offset=${offset}`),
  ]);

  return (
    <main className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Accuracy</h1>
          <p className={`text-sm ${muted}`}>
            How often each grader agreed with {view.everyone ? "everyone's" : "your"} verdicts on
            the student&apos;s answer.
          </p>
        </div>
        {me.is_admin && (
          <Segmented
            label="Whose verdicts"
            options={[
              { value: false, text: "Mine" },
              { value: true, text: "Everyone's" },
            ]}
            current={view.everyone}
            href={(everyone) => hrefFor(view, { everyone, page: 1 })}
          />
        )}
      </div>

      {rows.length === 0 ? (
        <p className={`text-sm ${muted}`}>
          No judged questions yet. Give a verdict on a question in a session&apos;s comparison view.
        </p>
      ) : (
        <>
          <SummaryCards rows={rows} />

          <section className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Accuracy over time</h2>
                <p className={`text-sm ${muted}`}>Cumulative, by when each question was graded.</p>
              </div>
              <Segmented
                label="Group by"
                options={BUCKETS.map((b) => ({ value: b, text: b[0].toUpperCase() + b.slice(1) }))}
                current={view.bucket}
                href={(bucket) => hrefFor(view, { bucket })}
              />
            </div>
            <AccuracyChart points={points} bucket={view.bucket} minJudged={MIN_JUDGED} />
          </section>

          <VerdictTable history={history} view={view} viewerId={me.id} />
        </>
      )}
    </main>
  );
}
