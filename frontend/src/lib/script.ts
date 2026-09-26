import type { MarkBreakdownItem, QuestionResult } from "./types";

// Same question markers as the backend parser (backend/app/services/grading/parser.py) — keep the
// two in step. A marker is a line holding nothing but the marker:
//   "1." / "1)" / "(1)" / "Item 1"
//   "3(a)" / "3(a)(ii)" / "3a", each optionally followed by "." or ")"
const QUESTION_RE = new RegExp(
  [
    String.raw`^\s*(?:`,
    String.raw`\((?<parenNumber>\d+)\)`,
    String.raw`|(?:item\s+)?(?<number>\d+)(?:`,
    String.raw`\((?<sub>[a-z]{1,4})\)(?:\((?<nestedSub>[a-z]{1,4})\))?[.)]?`,
    String.raw`|(?<bareSub>[a-z])[.)]?`,
    String.raw`|[.)])`,
    String.raw`|item\s+(?<itemNumber>\d+)[.:]?`,
    String.raw`)\s*$`,
  ].join(""),
  "i",
);

function matchMarker(line: string): { number: string; subPart: string | null } | null {
  const g = QUESTION_RE.exec(line)?.groups;
  if (!g) return null;
  const number = g.parenNumber ?? g.number ?? g.itemNumber;
  if (g.sub && g.nestedSub) return { number, subPart: `${g.sub}(${g.nestedSub})` };
  return { number, subPart: g.sub ?? g.bareSub ?? null };
}
const PAGE_SEPARATOR_RE = /^\s*-{3,}\s*$/;

export type ScriptBlock = { number: string | null; subPart: string | null; text: string };

// Mirrors the backend's question key: trimmed number, sub-part without parentheses, case-folded.
export function questionKey(number: string, subPart: string | null | undefined): string {
  const sub = subPart == null ? "" : subPart.trim().replace(/^[()]+|[()]+$/g, "").toLowerCase();
  return `${number.trim()}|${sub}`;
}

// Splits OCR Markdown into one block per question. Text before the first question (e.g. a name
// header) becomes a block with number null. Page separators are dropped, as the backend does.
export function splitScript(markdown: string): ScriptBlock[] {
  const groups: { number: string | null; subPart: string | null; lines: string[] }[] = [];
  let current: (typeof groups)[number] | null = null;

  for (const line of markdown.split(/\r?\n/)) {
    if (PAGE_SEPARATOR_RE.test(line)) continue;

    const marker = matchMarker(line);
    if (marker) {
      current = { ...marker, lines: [line] };
      groups.push(current);
      continue;
    }
    if (!current) {
      current = { number: null, subPart: null, lines: [] };
      groups.push(current);
    }
    current.lines.push(line);
  }

  return groups
    .map((g) => ({ number: g.number, subPart: g.subPart, text: g.lines.join("\n").trim() }))
    .filter((b) => b.text !== "");
}

// First result per question wins, as in the backend.
export function indexResults(results: QuestionResult[]): Map<string, QuestionResult> {
  const byKey = new Map<string, QuestionResult>();
  for (const r of results) {
    const key = questionKey(r.question_number, r.sub_part);
    if (!byKey.has(key)) byKey.set(key, r);
  }
  return byKey;
}

// First block per question wins, as in the backend.
export function indexBlocks(blocks: ScriptBlock[]): Map<string, ScriptBlock> {
  const byKey = new Map<string, ScriptBlock>();
  for (const b of blocks) {
    if (b.number === null) continue;
    const key = questionKey(b.number, b.subPart);
    if (!byKey.has(key)) byKey.set(key, b);
  }
  return byKey;
}

export type AnnotatedItem = {
  kind: "preamble" | "question" | "unmatched";
  label: string | null;
  text: string | null;
  result: QuestionResult | null;
};

export function questionLabel(number: string, subPart: string | null): string {
  const sub = subPart?.trim().replace(/^[()]+|[()]+$/g, "");
  return `Q${number.trim()}${sub ? `(${sub})` : ""}`;
}

// Pairs each script block with its result (by question number and sub-part). Like the backend,
// the first block for a repeated question wins. Results with no block are appended so the
// totals always agree with the run.
export function annotate(blocks: ScriptBlock[], results: QuestionResult[]): AnnotatedItem[] {
  const byKey = indexResults(results);

  const matched = new Set<QuestionResult>();
  const items: AnnotatedItem[] = blocks.map((block) => {
    if (block.number === null) {
      return { kind: "preamble", label: null, text: block.text, result: null };
    }
    const result = byKey.get(questionKey(block.number, block.subPart)) ?? null;
    const first = result !== null && !matched.has(result);
    if (result && first) matched.add(result);
    return {
      kind: "question",
      label: questionLabel(block.number, block.subPart),
      text: block.text,
      result: first ? result : null,
    };
  });

  for (const r of results) {
    if (!matched.has(r)) {
      items.push({
        kind: "unmatched",
        label: questionLabel(r.question_number, r.sub_part),
        text: null,
        result: r,
      });
    }
  }
  return items;
}

export type Marks =
  | { kind: "ticks"; awarded: number; max: number }
  | { kind: "numeric"; awarded: number; max: number }
  | { kind: "none" };

// Ticks/crosses only represent whole marks; anything else is shown as a number and flagged.
export function marksFor(result: QuestionResult | null): Marks {
  if (!result || result.mark_awarded === null) return { kind: "none" };
  const awarded = result.mark_awarded;
  const max = result.max_mark;
  const whole =
    Number.isInteger(awarded) && Number.isInteger(max) && max > 0 && awarded >= 0 && awarded <= max;
  return { kind: whole ? "ticks" : "numeric", awarded, max };
}

export type Summary = {
  ticks: number;
  crosses: number;
  awarded: number;
  max: number;
  numeric: number;
  notGraded: number;
};

export function summarise(items: AnnotatedItem[]): Summary {
  const s: Summary = { ticks: 0, crosses: 0, awarded: 0, max: 0, numeric: 0, notGraded: 0 };
  for (const item of items) {
    if (item.kind === "preamble") continue;
    const marks = marksFor(item.result);
    if (marks.kind === "none") {
      s.notGraded++;
      continue;
    }
    s.awarded += marks.awarded;
    s.max += marks.max;
    if (marks.kind === "numeric") s.numeric++;
    else {
      s.ticks += marks.awarded;
      s.crosses += marks.max - marks.awarded;
    }
  }
  return s;
}

// Avoid float noise like 0.30000000000000004 in displayed totals.
export function formatMark(n: number): string {
  return String(Math.round(n * 100) / 100);
}

const ORDINALS = ["first", "second", "third", "fourth"];

// "second M" where a code repeats, so marks are told apart by position; the code is never renamed.
export function markLabels(items: { code: string }[]): (string | null)[] {
  const seen = new Map<string, number>();
  return items.map(({ code }) => {
    const index = seen.get(code) ?? 0;
    seen.set(code, index + 1);
    const repeated = items.filter((item) => item.code === code).length > 1;
    return repeated ? `${ORDINALS[index] ?? `#${index + 1}`} ${code}` : null;
  });
}

// A mark as marked: its code, then what it earned. "T - 1", "M - 0".
export function formatAward(item: MarkBreakdownItem): string {
  return `${item.code} - ${formatMark(item.awarded)}`;
}

export function markEarned(item: MarkBreakdownItem): boolean {
  return item.awarded >= item.max_mark;
}

// Both results broken down into the same codes in the same order, so they can be set side by side.
export function sameMarkStructure(a: QuestionResult | null, b: QuestionResult | null): boolean {
  const x = a?.mark_breakdown;
  const y = b?.mark_breakdown;
  return !!x?.length && !!y?.length && x.length === y.length && x.every((m, i) => m.code === y[i].code);
}
