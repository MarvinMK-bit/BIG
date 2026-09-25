import Link from "next/link";
import { CopyButton } from "@/components/copy-button";
import { FeedbackThread } from "@/components/feedback-thread";
import { backendGet, backendGetText } from "@/lib/backend";
import { feedbackListPath, type Feedback, type Me } from "@/lib/types";

// Depending on the client, "@" may reach us still percent-encoded; decode defensively.
function decodeParam(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export default async function SchemePage(props: PageProps<"/schemes/[version]">) {
  const schemeVersion = decodeParam((await props.params).version);
  // Schemes are public: no ownership check, anyone signed in can read any scheme.
  const target = { kind: "scheme", version: schemeVersion } as const;
  const [yaml, me, feedback] = await Promise.all([
    backendGetText(`/grading/schemes/${encodeURIComponent(schemeVersion)}/yaml`, { notFound: true }),
    backendGet<Me>("/auth/me"),
    backendGet<Feedback[]>(feedbackListPath(target), { notFound: true }),
  ]);

  return (
    <main className="flex flex-col gap-4">
      <div>
        <Link href="/schemes" className="text-sm underline">
          ← Mark schemes
        </Link>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="break-all text-xl font-semibold">{schemeVersion}</h1>
        <CopyButton text={yaml} />
      </div>
      <pre className="overflow-x-auto rounded border border-zinc-300 bg-black/[.03] p-3 font-mono text-sm leading-relaxed dark:border-zinc-700 dark:bg-white/[.05]">
        {yaml}
      </pre>
      <section className="mt-4 flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Feedback</h2>
        <FeedbackThread target={target} username={me.username} initialItems={feedback} />
      </section>
    </main>
  );
}
