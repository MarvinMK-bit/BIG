import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.grading_session import GradingStatus


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
