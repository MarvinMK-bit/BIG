"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { CopyButton } from "@/components/copy-button";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import { saveBlob } from "./save-blob";

const field = "min-h-11 rounded border border-zinc-400 bg-transparent px-3 text-base";

export function ToYamlForm({ guideId, guideSubject }: { guideId: string; guideSubject: string | null }) {
  const id = useId();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [yaml, setYaml] = useState<string | null>(null);
  const [schemeName, setSchemeName] = useState("");

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);

    const data = new FormData(event.currentTarget);
    if (!(data.get("subject") as string)?.trim()) data.delete("subject");

    const result = await apiRequest<{ yaml: string }>(`/api/guides/${guideId}/to-yaml`, {
      method: "POST",
      body: data,
    });
    setPending(false);
    // Parse errors name the exact row and column in the table: show them exactly as sent
    if (!result.ok) return setError(result.error);
    setSchemeName(((data.get("name") as string) ?? "").trim());
    setYaml(result.data.yaml);
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Reviewed Word document (.docx)
          <input
            name="file"
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            required
            className="rounded border border-zinc-400 p-2 text-base file:mr-3 file:rounded file:border-0 file:bg-zinc-200 file:px-3 file:py-2 file:text-sm dark:file:bg-zinc-700"
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            Scheme name
            <input
              name="name"
              required
              placeholder="e.g. s3-algebra-june"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              className={field}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Version
            <input
              name="version"
              required
              placeholder="e.g. 0.1.0"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              className={field}
            />
          </label>
        </div>
        <label className="flex flex-col gap-1 text-sm">
          Subject{guideSubject ? " (optional; defaults to the guide's)" : ""}
          <input
            name="subject"
            defaultValue={guideSubject ?? ""}
            required={guideSubject === null}
            placeholder="e.g. mathematics"
            className={field}
          />
        </label>
        {error && (
          <p role="alert" className="whitespace-pre-wrap break-words rounded border border-red-600 p-3 text-sm text-red-700 dark:text-red-400">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50 sm:self-start"
        >
          {pending ? "Converting…" : "Convert to scheme YAML"}
        </button>
      </form>

      {yaml !== null && (
        <section className="flex flex-col gap-3">
          <h3 className="font-semibold">Scheme YAML</h3>
          <p className={`text-sm ${muted}`}>
            Nothing has been saved yet. Check it, edit if needed, then upload it as a .yaml file on{" "}
            <Link href="/schemes" className="underline">
              Mark schemes
            </Link>
            .
          </p>
          <label htmlFor={`${id}-yaml`} className="sr-only">
            Scheme YAML
          </label>
          <textarea
            id={`${id}-yaml`}
            value={yaml}
            onChange={(e) => setYaml(e.target.value)}
            rows={16}
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            className="w-full rounded border border-zinc-400 bg-black/[.03] p-3 font-mono text-sm leading-relaxed dark:border-zinc-600 dark:bg-white/[.05]"
          />
          <div className="flex flex-wrap gap-2">
            <CopyButton text={yaml} />
            <button
              type="button"
              onClick={() => saveBlob(new Blob([yaml], { type: "application/yaml" }), `${schemeName || "scheme"}.yaml`)}
              className="min-h-9 rounded border border-zinc-400 px-3 text-sm"
            >
              Download .yaml
            </button>
            <Link href="/schemes" className="flex min-h-9 items-center rounded border border-zinc-400 px-3 text-sm">
              Go to Mark schemes →
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
