import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.grading_session import GradingStatus
from app.models.mark_scheme import SchemeReviewStatus
from app.models.question_result import GraderType


class GradingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    subject: str | None
    status: GradingStatus
    ocr_engine: str | None
    ocr_confidence: float | None
    ocr_markdown: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class MarkBreakdownOut(BaseModel):
    code: str
    awarded: float
    max_mark: float
    reason: str


class QuestionResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_number: str
    sub_part: str | None
    extracted_answer: str | None
    mark_awarded: float | None
    max_mark: float
    grader_type: GraderType
    mark_scheme_version: str | None
    confidence: float | None
    ocr_confidence: float | None
    reasoning: str | None
    # One entry per mark point, in scheme order; None unless a procedure marked the question
    mark_breakdown: list[MarkBreakdownOut] | None
    # True when the awards resume after a zero (LLM only); None without a breakdown
    invalid_mark_pattern: bool | None
    created_at: datetime


class SchemeOut(BaseModel):
    scheme_version: str
    name: str
    subject: str | None
    description: str | None
    question_count: int
    origin: Literal["repo", "uploaded"]
    # Set for uploaded schemes only
    owner_username: str | None = None
    # Uploaded schemes only: whether an admin has let it into the public corpus. It does not
    # affect grading; None for repo files, which are the corpus.
    review_status: SchemeReviewStatus | None = None


class SchemeQuestionSummary(BaseModel):
    """What a scheme question marks, without its answer."""

    number: str
    sub_part: str | None
    matcher: str
    max_mark: float
    # Procedure questions only
    procedure: str | None = None
    mark_codes: list[str] | None = None


class PendingSchemeOut(BaseModel):
    scheme_version: str
    name: str
    version: str
    subject: str | None
    description: str | None
    source: str
    contributor_username: str
    # Whether the contributor agreed to be named when the scheme is exported
    attribution_opt_in: bool
    question_count: int
    questions: list[SchemeQuestionSummary]
    # Set when the stored YAML no longer parses under the current rules; questions is then empty
    parse_error: str | None
    yaml_content: str
    created_at: datetime


ReviewNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class SchemeReviewRequest(BaseModel):
    review_status: Literal[SchemeReviewStatus.ACCEPTED, SchemeReviewStatus.DECLINED]
    note: ReviewNote | None = None


class SchemeReviewOut(BaseModel):
    scheme_version: str
    review_status: SchemeReviewStatus
    review_note: str | None
    reviewed_at: datetime
    exported_at: datetime | None
    # What BIG pays for a well-designed accepted scheme (SCHEME_REWARD_SATS); nothing is recorded here
    reward_sats: int


class SchemeTestRequest(BaseModel):
    session_id: uuid.UUID
    unnumbered_mode: bool = False


class SchemeGradeRequest(BaseModel):
    scheme_version: str
    unnumbered_mode: bool = False


class LLMGradeRequest(BaseModel):
    # Aligns the model's marks to this scheme's structure; it is never shown the scheme's answers
    scheme_version: str | None = None


class SchemeGradeResponse(BaseModel):
    grading_run_id: uuid.UUID
    results: list[QuestionResultOut]


class QuestionComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_number: str
    sub_part: str | None
    extracted_answer: str | None
    llm_mark: float | None
    scheme_mark: float | None
    max_mark: float | None
    llm_progress: int | None
    scheme_progress: int | None
    progress_max: int | None
    progress_note: str | None
    invalid_mark_pattern: bool
    agree: bool | None
    human_verdict: bool | None


class RunComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    llm_run_id: uuid.UUID | None
    scheme_run_id: uuid.UUID | None
    scheme_version: str | None
    questions: list[QuestionComparisonOut]
    agreement_rate: float | None
    excluded_invalid_pattern: int
    llm_total: float | None
    scheme_total: float | None
    max_total: float | None


class GradingRunOut(BaseModel):
    grading_run_id: uuid.UUID
    grader_type: GraderType
    mark_scheme_version: str | None
    created_at: datetime


class VerdictRequest(BaseModel):
    # Required but nullable: null clears a previous verdict
    is_correct: bool | None


class GraderAccuracyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grader_type: GraderType
    mark_scheme_version: str | None
    judged_questions: int
    correct_decisions: int
    accuracy: float | None
    invalid_pattern_questions: int


class AccuracyPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    grader_type: GraderType
    mark_scheme_version: str | None
    judged_questions: int
    correct_decisions: int
    accuracy: float | None
    cumulative_judged: int
    cumulative_correct: int
    cumulative_accuracy: float | None


class GraderVerdictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grader_type: GraderType
    mark_scheme_version: str | None
    mark_awarded: float | None
    max_mark: float
    agreed: bool | None
    invalid_mark_pattern: bool


class JudgedQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    owner_id: uuid.UUID
    owner_username: str
    original_filename: str
    subject: str | None
    question_number: str
    sub_part: str | None
    extracted_answer: str | None
    verdict: bool
    verdict_set_at: datetime | None
    graders: list[GraderVerdictOut]


class VerdictHistoryOut(BaseModel):
    items: list[JudgedQuestionOut]
    total: int
    limit: int
    offset: int
