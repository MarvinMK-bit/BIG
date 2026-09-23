import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.grading_session import GradingStatus
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


class SchemeGradeRequest(BaseModel):
    scheme_version: str
    unnumbered_mode: bool = False


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
