import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.marking_guide import GuideStatus


class MarkingGuideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    subject: str | None
    title: str | None
    status: GuideStatus
    ocr_engine: str | None
    ocr_markdown: str | None
    ocr_confidence: float | None
    error_message: str | None
    created_at: datetime
    extracted_at: datetime | None


class GuideYamlOut(BaseModel):
    yaml: str
