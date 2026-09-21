import type { QuestionResult } from "./types";

export type GraderCall = "right" | "wrong" | "ungraded";

// Did this grader match the human verdict on the student's answer? Yes + full marks, or
// No + less than full marks (same rule as the backend's accuracy measure).
export function graderCall(result: QuestionResult | null, verdict: boolean): GraderCall {
  if (!result || result.mark_awarded === null) return "ungraded";
  const full = result.mark_awarded === result.max_mark;
  return verdict === full ? "right" : "wrong";
}
