import Link from "next/link";
import { backendGetText } from "@/lib/backend";
import { CopyButton } from "./copy-button";

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
  const yaml = await backendGetText(
    `/grading/schemes/${encodeURIComponent(schemeVersion)}/yaml`,
    { notFound: true },
  );

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
    </main>
  );
}
