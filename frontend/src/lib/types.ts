export type SessionStatus = "pending" | "processing" | "completed" | "failed";

export type GradingSession = {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  subject: string | null;
  status: SessionStatus;
  ocr_engine: string | null;
  ocr_confidence: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  ocr_markdown: string | null;
};

export type Scheme = {
  // "name@version"
  scheme_version: string;
  name: string;
  subject: string | null;
  description: string | null;
  question_count: number;
  origin: "repo" | "uploaded";
  // Set for uploaded schemes only
  owner_username: string | null;
};

// The version half of "name@version"; names may contain "@", so split at the last one.
export function schemeVersionPart(scheme: Scheme): string {
  const at = scheme.scheme_version.lastIndexOf("@");
  return at === -1 ? scheme.scheme_version : scheme.scheme_version.slice(at + 1);
}

export function schemeOriginLabel(scheme: Scheme): string {
  return scheme.origin === "repo" ? "repo" : `uploaded by ${scheme.owner_username ?? "unknown"}`;
}

export type QuestionResult = {
  id: string;
  question_number: string;
  sub_part: string | null;
  extracted_answer: string | null;
  mark_awarded: number | null;
  max_mark: number;
  grader_type: "llm" | "mark_scheme";
  mark_scheme_version: string | null;
  confidence: number | null;
  ocr_confidence: number | null;
  reasoning: string | null;
  created_at: string;
};

export type GradingRun = {
  grading_run_id: string;
  grader_type: "llm" | "mark_scheme";
  mark_scheme_version: string | null;
  created_at: string;
};

// A stored run together with its per-question results.
export type RunView = { run: GradingRun; results: QuestionResult[] };

export type QuestionComparison = {
  question_number: string;
  sub_part: string | null;
  extracted_answer: string | null;
  llm_mark: number | null;
  scheme_mark: number | null;
  max_mark: number | null;
  agree: boolean | null;
  human_verdict: boolean | null;
};

export type RunComparison = {
  session_id: string;
  llm_run_id: string | null;
  scheme_run_id: string | null;
  scheme_version: string | null;
  questions: QuestionComparison[];
  agreement_rate: number | null;
  llm_total: number | null;
  scheme_total: number | null;
  max_total: number | null;
};

export type GraderAccuracy = {
  grader_type: "llm" | "mark_scheme";
  mark_scheme_version: string | null;
  judged_questions: number;
  correct_decisions: number;
  accuracy: number | null;
};

export type Bucket = "day" | "week" | "month";

// One grader's accuracy in one time bucket, with running totals up to and including it.
export type AccuracyPoint = {
  period_start: string; // YYYY-MM-DD, UTC
  grader_type: "llm" | "mark_scheme";
  mark_scheme_version: string | null;
  judged_questions: number;
  correct_decisions: number;
  accuracy: number | null;
  cumulative_judged: number;
  cumulative_correct: number;
  cumulative_accuracy: number | null;
};

export type GraderVerdict = {
  grader_type: "llm" | "mark_scheme";
  mark_scheme_version: string | null;
  mark_awarded: number | null;
  max_mark: number;
  agreed: boolean;
};

export type JudgedQuestion = {
  session_id: string;
  owner_id: string;
  owner_username: string;
  original_filename: string;
  subject: string | null;
  question_number: string;
  sub_part: string | null;
  extracted_answer: string | null;
  verdict: boolean;
  verdict_set_at: string | null;
  graders: GraderVerdict[];
};

export type VerdictHistory = {
  items: JudgedQuestion[];
  total: number;
  limit: number;
  offset: number;
};

export type Me = { id: string; username: string; is_admin: boolean };

export type FeedbackStatus = "pending" | "approved" | "rejected" | "muted";

// What a feedback thread hangs off: one question result, or one mark scheme.
export type FeedbackTarget =
  | { kind: "result"; id: string }
  | { kind: "scheme"; version: string };

export type Feedback = {
  id: string;
  public_ref: string; // e.g. "0001a"; replies share the number: "0001b"
  author_username: string;
  author_context: string | null;
  target_type: "question_result" | "mark_scheme";
  question_result_id: string | null;
  // Set for question-result targets, so they can be linked to
  session_id: string | null;
  question_number: string | null;
  sub_part: string | null;
  mark_scheme_version: string | null;
  parent_id: string | null;
  parent_public_ref: string | null;
  body: string;
  status: FeedbackStatus;
  created_at: string;
  edited_at: string | null;
  reviewed_at: string | null;
};

// The approved sats reward for useful feedback; payouts are manual for now.
export const FEEDBACK_REWARD_SATS = 100;

export function feedbackListPath(target: FeedbackTarget): string {
  return target.kind === "result"
    ? `/feedback/result/${encodeURIComponent(target.id)}`
    : `/feedback/scheme/${encodeURIComponent(target.version)}`;
}
