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

export type GuideStatus = "pending" | "processing" | "extracted" | "failed";

// A photographed marking guide: the correct answers, not a student's script. Admin only.
export type MarkingGuide = {
  id: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  subject: string | null;
  title: string | null;
  status: GuideStatus;
  ocr_engine: string | null;
  ocr_markdown: string | null;
  ocr_confidence: number | null;
  error_message: string | null;
  created_at: string;
  extracted_at: string | null;
};

export function guideTitle(guide: MarkingGuide): string {
  return guide.title ?? guide.original_filename;
}

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

export type Me = { id: string; username: string; is_admin: boolean; blink_address: string | null };

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

// Shown in the feedback prompt. The amount actually recorded comes from the backend's
// FEEDBACK_REWARD_SATS setting; keep the two in step.
export const FEEDBACK_REWARD_SATS = 100;

export function feedbackListPath(target: FeedbackTarget): string {
  return target.kind === "result"
    ? `/feedback/result/${encodeURIComponent(target.id)}`
    : `/feedback/scheme/${encodeURIComponent(target.version)}`;
}

// The approve/reject/mute response: the feedback plus its ledger entry, if it has one.
export type FeedbackReview = Feedback & { reward: Reward | null };

export type RewardReason = "feedback" | "mark_scheme" | "scheme_improvement";
// "paid" is either a Lightning payout Blink reported as sent (payment_ref "blink:…") or a payment
// an admin made outside BIG and recorded by hand.
export type RewardStatus = "owed" | "paid" | "cancelled";

export type Reward = {
  id: string;
  recipient_username: string;
  amount_sats: number;
  reason: RewardReason;
  note: string | null;
  status: RewardStatus;
  mark_scheme_version: string | null;
  // The feedback it was for, when reason is "feedback"
  feedback: {
    id: string;
    public_ref: string;
    mark_scheme_version: string | null;
    question_result_id: string | null;
    session_id: string | null;
    question_number: string | null;
    sub_part: string | null;
  } | null;
  created_at: string;
  paid_at: string | null;
  payment_ref: string | null;
};

export type MyRewards = { total_owed_sats: number; rewards: Reward[] };

export type AttemptStatus = "attempting" | "success" | "failed" | "pending" | "already_paid";

// One try at paying a reward over Lightning, recorded before Blink is called.
export type PayoutAttempt = {
  id: string;
  reward_id: string;
  amount_sats: number;
  lightning_address: string;
  status: AttemptStatus;
  blink_status: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

// Attempts that have, or may have, sent the sats: the backend refuses another Pay while one exists.
export const BLOCKING_ATTEMPTS: ReadonlySet<AttemptStatus> = new Set([
  "attempting",
  "pending",
  "success",
  "already_paid",
]);

export type OwedReward = Reward & { attempts: PayoutAttempt[] };

export type OwedGroup = {
  recipient_id: string;
  recipient_username: string;
  blink_address: string | null;
  total_owed_sats: number;
  rewards: OwedReward[];
};

export type PayoutStatus = {
  enabled: boolean;
  configured: boolean;
  network: "staging" | "mainnet" | "other";
  api_host: string;
  // Why Pay would be refused right now, if it would
  problem: string | null;
};

export type PayoutResult = { attempt: PayoutAttempt; reward: Reward };
