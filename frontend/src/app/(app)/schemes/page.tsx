import Link from "next/link";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import { type Scheme, schemeOriginLabel, schemeVersionPart } from "@/lib/types";
import { DeleteSchemeButton } from "./delete-button";
import { SchemeUploadForm } from "./upload-form";

export default async function SchemesPage() {
  const [schemes, user] = await Promise.all([
    backendGet<Scheme[]>("/grading/schemes"),
    backendGet<{ username: string }>("/auth/me"),
  ]);

  return (
    <main className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <div>
          <h1 className="text-xl font-semibold">Mark schemes</h1>
          <p className={`text-sm ${muted}`}>
            Mark schemes are public, so anyone can read, check and improve them.
          </p>
        </div>
        <SchemeUploadForm />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">All schemes</h2>
        {schemes.length === 0 ? (
          <p className={`text-sm ${muted}`}>No mark schemes yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {schemes.map((s) => {
              const owned = s.origin === "uploaded" && s.owner_username === user.username;
              return (
                <li
                  key={s.scheme_version}
                  className="flex flex-col gap-2 rounded border border-zinc-300 p-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4 dark:border-zinc-700"
                >
                  <Link
                    href={`/schemes/${encodeURIComponent(s.scheme_version)}`}
                    className="flex min-w-0 flex-1 flex-col gap-1 hover:underline"
                  >
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="break-all font-medium">{s.name}</span>
                      <span className={`text-sm ${muted}`}>v{schemeVersionPart(s)}</span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs ${
                          s.origin === "repo"
                            ? "bg-zinc-200 dark:bg-zinc-700"
                            : "bg-sky-100 text-sky-900 dark:bg-sky-900 dark:text-sky-100"
                        }`}
                      >
                        {schemeOriginLabel(s)}
                      </span>
                    </span>
                    <span className={`text-sm ${muted}`}>
                      {s.subject ?? "No subject"} · {s.question_count}{" "}
                      {s.question_count === 1 ? "question" : "questions"}
                    </span>
                    {s.description && <span className="text-sm">{s.description}</span>}
                  </Link>
                  {owned && <DeleteSchemeButton schemeVersion={s.scheme_version} />}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
