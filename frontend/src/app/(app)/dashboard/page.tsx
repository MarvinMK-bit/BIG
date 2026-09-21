import Link from "next/link";
import { LocalTime } from "@/components/local-time";
import { StatusBadge } from "@/components/status-badge";
import { backendGet } from "@/lib/backend";
import type { GradingSession } from "@/lib/types";
import { UploadForm } from "./upload-form";

export default async function DashboardPage() {
  const sessions = (await backendGet<GradingSession[]>("/grading/sessions")).toSorted(
    (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
  );

  return (
    <main className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h1 className="text-xl font-semibold">Upload</h1>
        <UploadForm />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Sessions</h2>
        {sessions.length === 0 ? (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">No sessions yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {sessions.map((s) => (
              <li key={s.id}>
                <Link
                  href={`/sessions/${s.id}`}
                  className="flex flex-col gap-1 rounded border border-zinc-300 p-3 hover:bg-black/[.04] sm:flex-row sm:items-center sm:justify-between sm:gap-4 dark:border-zinc-700 dark:hover:bg-white/[.06]"
                >
                  <span className="min-w-0">
                    <span className="block break-all font-medium">{s.original_filename}</span>
                    <span className="block text-sm text-zinc-600 dark:text-zinc-400">
                      {s.subject ?? "No subject"}
                    </span>
                  </span>
                  <span className="flex items-center gap-3 text-sm text-zinc-600 dark:text-zinc-400">
                    <StatusBadge status={s.status} />
                    <LocalTime iso={s.created_at} />
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
