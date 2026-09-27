import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.question_paper import PaperStatus


class QuestionPaperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    subject: str | None
    original_filename: str
    mime_type: str
    file_size_bytes: int
    status: PaperStatus
    # "docx-text" when the text was read from a Word document rather than OCR'd
    ocr_engine: str | None
    ocr_markdown: str | None
    ocr_confidence: float | None
    error_message: str | None
    created_at: datetime
    extracted_at: datetime | None
