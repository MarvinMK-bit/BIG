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
