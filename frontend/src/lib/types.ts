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
  scheme_version: string;
  name: string;
  subject: string;
  description: string | null;
  question_count: number;
};

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
