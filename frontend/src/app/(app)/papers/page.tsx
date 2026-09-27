import { LocalTime } from "@/components/local-time";
import { StatusBadge } from "@/components/status-badge";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import type { QuestionPaper } from "@/lib/types";
import { PaperActions } from "./paper-actions";
import { PaperUploadForm } from "./upload-form";

export default async function PapersPage() {
  const papers = await backendGet<QuestionPaper[]>("/papers"); // the caller's own, newest first

  return (
    <main className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h1 className="text-xl font-semibold">Question papers</h1>
        <p className={`text-sm ${muted}`}>
          Upload the paper your students sat, then attach it to their scripts. The LLM grader then
          marks each answer against the question as set, rather than working out the questions from
          the script. A question paper is never graded and holds no student work.
        </p>
        <PaperUploadForm />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Your papers</h2>
        {papers.length === 0 ? (
          <p className={`text-sm ${muted}`}>No question papers yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {papers.map((paper) => (
              <li
                key={paper.id}
                className="flex flex-col gap-3 rounded border border-zinc-300 p-3 dark:border-zinc-700"
              >
                <div className="flex flex-col gap-1">
                  <span className="break-all font-medium">{paper.title}</span>
                  <span className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-sm ${muted}`}>
                    <StatusBadge status={paper.status} />
                    <span>{paper.subject ?? "No subject"}</span>
                    <span className="break-all">{paper.original_filename}</span>
                    <LocalTime iso={paper.created_at} />
                  </span>
                </div>

                {paper.status === "processing" && (
                  <p className="text-sm">Extraction is in progress. Reload this page in a moment.</p>
                )}
                {paper.status === "failed" && (
                  <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
                    Extraction failed{paper.error_message ? `: ${paper.error_message}` : "."} Upload the
                    paper again to retry.
                  </p>
                )}
                {paper.status === "extracted" && (
                  <details>
                    <summary className="cursor-pointer text-sm underline">
                      Extracted text
                      <span className={muted}>
                        {" "}
                        · {paper.ocr_engine === "docx-text" ? "read from the Word document" : "by OCR"}
                      </span>
                    </summary>
                    <pre className="mt-2 max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded border border-zinc-300 bg-black/[.03] p-3 font-mono text-sm leading-relaxed dark:border-zinc-700 dark:bg-white/[.05]">
                      {paper.ocr_markdown || "No text was found."}
                    </pre>
                  </details>
                )}

                <PaperActions paper={paper} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
