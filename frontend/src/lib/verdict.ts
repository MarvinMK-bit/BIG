import type { QuestionResult } from "./types";

export type GraderCall = "right" | "wrong" | "ungraded" | "invalid";

// Did this grader match the human verdict on the student's answer? Yes + full progress, or
// No + progress short of full (same rule as the backend's accuracy measure). For a valid
// prefix, full progress is full marks. A result whose marks resume after a zero has no call.
export function graderCall(result: QuestionResult | null, verdict: boolean): GraderCall {
  if (!result || result.mark_awarded === null) return "ungraded";
  if (result.invalid_mark_pattern) return "invalid";
  const full = result.mark_awarded === result.max_mark;
  return verdict === full ? "right" : "wrong";
}
