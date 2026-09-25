type Grader = { grader_type: "llm" | "mark_scheme"; mark_scheme_version: string | null };

export function graderKey(g: Grader): string {
  return `${g.grader_type}|${g.mark_scheme_version ?? ""}`;
}

export function graderLabel(g: Grader): string {
  return g.grader_type === "llm" ? "LLM" : `Mark scheme — ${g.mark_scheme_version ?? "unknown version"}`;
}

// LLM first, then mark schemes by version: a stable order, so a grader keeps its colour and column.
export function compareGraders(a: Grader, b: Grader): number {
  if (a.grader_type !== b.grader_type) return a.grader_type === "llm" ? -1 : 1;
  return (a.mark_scheme_version ?? "").localeCompare(b.mark_scheme_version ?? "");
}
