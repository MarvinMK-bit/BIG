import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.grading_session import GradingSession
    from app.models.user import User


class GraderType(str, enum.Enum):
    LLM = "llm"
    MARK_SCHEME = "mark_scheme"


class QuestionResult(Base):
    __tablename__ = "question_results"
    __table_args__ = (
        Index("ix_question_results_grading_run_id_question_number", "grading_run_id", "question_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    grading_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grading_sessions.id"), index=True, nullable=False
    )

    question_number: Mapped[str] = mapped_column(String, nullable=False)
    sub_part: Mapped[str | None] = mapped_column(String, nullable=True)

    extracted_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    mark_awarded: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_mark: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    grader_type: Mapped[GraderType] = mapped_column(Enum(GraderType, name="grader_type"), nullable=False)
    mark_scheme_version: Mapped[str | None] = mapped_column(String, nullable=True)

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct_per_human: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="question_results")
    session: Mapped["GradingSession"] = relationship("GradingSession", back_populates="question_results")
