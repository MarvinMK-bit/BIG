import uuid
from datetime import datetime

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


class SchemeGradeRequest(BaseModel):
    scheme_version: str


class SchemeGradeResponse(BaseModel):
    grading_run_id: uuid.UUID
    results: list[QuestionResultOut]
