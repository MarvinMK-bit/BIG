"use client";

import { useState } from "react";

export function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      // Only available in secure contexts (https or localhost)
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
    }
    setTimeout(() => setState("idle"), 2000);
  }

  return (
    <button onClick={copy} className="min-h-9 rounded border border-zinc-400 px-3 text-sm">
      {state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : "Copy YAML"}
    </button>
  );
}
