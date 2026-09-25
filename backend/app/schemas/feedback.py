import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from app.models.feedback import Feedback, FeedbackStatus, FeedbackTarget
from app.repositories.feedback_repo import REVIEW_STATUSES
from app.schemas.reward import RewardOut

FeedbackBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
AuthorContext = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class FeedbackCreate(BaseModel):
    target_type: FeedbackTarget
    question_result_id: uuid.UUID | None = None
    mark_scheme_version: str | None = None
    parent_id: uuid.UUID | None = None
    body: FeedbackBody
    author_context: AuthorContext | None = None


class FeedbackEdit(BaseModel):
    body: FeedbackBody


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus

    @field_validator("status")
    @classmethod
    def _review_status(cls, value: FeedbackStatus) -> FeedbackStatus:
        if value not in REVIEW_STATUSES:
            raise ValueError("status must be approved, rejected or muted")
        return value


class FeedbackOut(BaseModel):
    id: uuid.UUID
    public_ref: str
    author_username: str
    author_context: str | None
    target_type: FeedbackTarget
    question_result_id: uuid.UUID | None
    # Where a question-result target lives, so it can be linked to
    session_id: uuid.UUID | None
    question_number: str | None
    sub_part: str | None
    mark_scheme_version: str | None
    parent_id: uuid.UUID | None
    # "In reply to 0001a"; the parent's body is left out, as the viewer may not be allowed to see it
    parent_public_ref: str | None
    body: str
    status: FeedbackStatus
    created_at: datetime
    edited_at: datetime | None
    reviewed_at: datetime | None

    @classmethod
    def from_model(cls, feedback: Feedback) -> "FeedbackOut":
        result = feedback.question_result
        return cls(
            id=feedback.id,
            public_ref=feedback.public_ref,
            author_username=feedback.author.username,
            author_context=feedback.author_context,
            target_type=feedback.target_type,
            question_result_id=feedback.question_result_id,
            session_id=result.session_id if result else None,
            question_number=result.question_number if result else None,
            sub_part=result.sub_part if result else None,
            mark_scheme_version=feedback.mark_scheme_version,
            parent_id=feedback.parent_id,
            parent_public_ref=feedback.parent.public_ref if feedback.parent else None,
            body=feedback.body,
            status=feedback.status,
            created_at=feedback.created_at,
            edited_at=feedback.edited_at,
            reviewed_at=feedback.reviewed_at,
        )


class FeedbackReviewOut(FeedbackOut):
    # The ledger entry for approved feedback, whether created by this review or an earlier one
    reward: RewardOut | None
