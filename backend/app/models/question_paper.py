import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class PaperStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    FAILED = "failed"


class QuestionPaper(Base):
    """The questions that were set, so the LLM grader can mark against what was actually asked.

    A question paper states what was asked. It is never graded and holds no student work: the
    students' answers live in grading sessions, each of which may point at one paper. One paper
    serves many sessions, since a class is graded against a single upload.

    ocr_markdown holds the paper's text however it was obtained: OCR for images and PDFs, and
    the document's own text for DOCX, where ocr_engine records that no OCR was involved.
    """

    __tablename__ = "question_papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)

    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[PaperStatus] = mapped_column(
        Enum(PaperStatus, name="paper_status"), nullable=False, default=PaperStatus.PENDING
    )

    ocr_engine: Mapped[str | None] = mapped_column(String, nullable=True)
    ocr_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="question_papers")
