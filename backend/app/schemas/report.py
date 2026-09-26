import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.performance_report import PerformanceReport

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MethodNotes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]


class ReportCreate(BaseModel):
    # No is_author_self_report: the server works that out from who owns the scheme
    mark_scheme_version: ShortText
    disputes_id: uuid.UUID | None = None
    scripts_tested: int = Field(gt=0)
    questions_judged: int = Field(gt=0)
    correct_decisions: int = Field(ge=0)
    paper_type: ShortText
    level: ShortText | None = None
    tester_context: ShortText | None = None
    method_notes: MethodNotes | None = None

    @model_validator(mode="after")
    def _correct_within_judged(self) -> "ReportCreate":
        if self.correct_decisions > self.questions_judged:
            raise ValueError("correct_decisions can't exceed questions_judged")
        return self


class ReportOut(BaseModel):
    id: uuid.UUID
    public_ref: str
    author_username: str
    mark_scheme_version: str
    disputes_id: uuid.UUID | None
    disputes_public_ref: str | None
    scripts_tested: int
    questions_judged: int
    correct_decisions: int
    # correct_decisions / questions_judged, from 0 to 1
    accuracy: float
    paper_type: str
    level: str | None
    tester_context: str | None
    method_notes: str | None
    is_author_self_report: bool
    created_at: datetime

    @classmethod
    def from_model(cls, report: PerformanceReport) -> "ReportOut":
        return cls(
            id=report.id,
            public_ref=report.public_ref,
            author_username=report.author.username,
            mark_scheme_version=report.mark_scheme_version,
            disputes_id=report.disputes_id,
            disputes_public_ref=report.disputes.public_ref if report.disputes else None,
            scripts_tested=report.scripts_tested,
            questions_judged=report.questions_judged,
            correct_decisions=report.correct_decisions,
            accuracy=report.accuracy,
            paper_type=report.paper_type,
            level=report.level,
            tester_context=report.tester_context,
            method_notes=report.method_notes,
            is_author_self_report=report.is_author_self_report,
            created_at=report.created_at,
        )


class ReportWithDisputesOut(ReportOut):
    # Newest first; always empty on a report that is itself a dispute
    disputed_by: list[ReportOut]
