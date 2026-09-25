import Link from "next/link";
import { notFound } from "next/navigation";
import { LocalTime } from "@/components/local-time";
import { StatusBadge } from "@/components/status-badge";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import { guideTitle, type MarkingGuide, type Me } from "@/lib/types";
import { GuideUploadForm } from "./upload-form";

export default async function GuidesPage() {
  // Admin only, matching the backend; everyone else gets the same 404 as any unknown page
  const me = await backendGet<Me>("/auth/me");
  if (!me.is_admin) notFound();

  const guides = (await backendGet<MarkingGuide[]>("/guides")).toSorted(
    (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
  );

  return (
    <main className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h1 className="text-xl font-semibold">Marking guides</h1>
        <p className={`text-sm ${muted}`}>
          Photograph a handwritten marking guide, review the Word document it produces, then convert
          it to a mark scheme. A guide defines the correct answers; it is not a student&apos;s script.
        </p>
        <GuideUploadForm />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Your guides</h2>
        {guides.length === 0 ? (
          <p className={`text-sm ${muted}`}>No guides yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {guides.map((g) => (
              <li key={g.id}>
                <Link
                  href={`/guides/${g.id}`}
                  className="flex flex-col gap-1 rounded border border-zinc-300 p-3 hover:bg-black/[.04] sm:flex-row sm:items-center sm:justify-between sm:gap-4 dark:border-zinc-700 dark:hover:bg-white/[.06]"
                >
                  <span className="min-w-0">
                    <span className="block break-all font-medium">{guideTitle(g)}</span>
                    <span className={`block text-sm ${muted}`}>{g.subject ?? "No subject"}</span>
                  </span>
                  <span className={`flex items-center gap-3 text-sm ${muted}`}>
                    <StatusBadge status={g.status} />
                    <LocalTime iso={g.created_at} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
