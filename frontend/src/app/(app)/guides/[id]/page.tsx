import Link from "next/link";
import { notFound } from "next/navigation";
import { LocalTime } from "@/components/local-time";
import { StatusBadge } from "@/components/status-badge";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import { guideTitle, type MarkingGuide, type Me } from "@/lib/types";
import { DocxDownload } from "./docx-download";
import { ExtractGuideButton } from "./extract-button";
import { ToYamlForm } from "./to-yaml-form";

export default async function GuidePage(props: PageProps<"/guides/[id]">) {
  const me = await backendGet<Me>("/auth/me");
  if (!me.is_admin) notFound();

  const { id } = await props.params;
  const guide = await backendGet<MarkingGuide>(`/guides/${encodeURIComponent(id)}`, { notFound: true });

  return (
    <main className="flex flex-col gap-6">
      <div>
        <Link href="/guides" className="text-sm underline">
          ← Marking guides
        </Link>
      </div>

      <header className="flex flex-col gap-1">
        <h1 className="break-all text-xl font-semibold">{guideTitle(guide)}</h1>
        <div className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-sm ${muted}`}>
          <StatusBadge status={guide.status} />
          <span>{guide.subject ?? "No subject"}</span>
          <LocalTime iso={guide.created_at} />
        </div>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Extracted text</h2>
        {guide.status === "pending" && <ExtractGuideButton guideId={guide.id} />}
        {guide.status === "processing" && (
          <p className="text-sm">Extraction is in progress. Reload this page in a moment.</p>
        )}
        {guide.status === "failed" && (
          <p role="alert" className="whitespace-pre-wrap break-words text-sm text-red-600">
            Extraction failed{guide.error_message ? `: ${guide.error_message}` : "."} Upload the guide
            again to retry.
          </p>
        )}
        {guide.status === "extracted" && (
          <>
            <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded border border-zinc-300 bg-black/[.03] p-3 font-mono text-sm leading-relaxed dark:border-zinc-700 dark:bg-white/[.05]">
              {guide.ocr_markdown || "No text was found."}
            </pre>
            <DocxDownload guideId={guide.id} />
          </>
        )}
      </section>

      {guide.status === "extracted" && (
        <section className="flex flex-col gap-4 border-t-4 border-double border-zinc-300 pt-6 dark:border-zinc-700">
          <h2 className="text-lg font-semibold">Upload reviewed document</h2>
          <div
            role="note"
            className="flex flex-col gap-1 rounded border-2 border-red-700 bg-red-50 p-3 text-red-950 dark:border-red-500 dark:bg-red-950 dark:text-red-50"
          >
            <p className="font-semibold">Review every answer before converting.</p>
            <p className="text-sm">
              A wrong answer here marks every script wrong. Check each row of the Word document against
              the original guide, and correct it there before uploading.
            </p>
          </div>
          <ToYamlForm guideId={guide.id} guideSubject={guide.subject} />
        </section>
      )}
    </main>
  );
}
