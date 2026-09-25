import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models.reward import Reward, RewardReason, RewardStatus

MANUAL_REASONS = frozenset({RewardReason.MARK_SCHEME, RewardReason.SCHEME_IMPROVEMENT})

PaymentRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class RewardFeedbackOut(BaseModel):
    """The feedback a reward was for, with enough to link to it."""

    id: uuid.UUID
    public_ref: str
    mark_scheme_version: str | None
    question_result_id: uuid.UUID | None
    session_id: uuid.UUID | None
    question_number: str | None
    sub_part: str | None


class RewardOut(BaseModel):
    id: uuid.UUID
    recipient_username: str
    amount_sats: int
    reason: RewardReason
    note: str | None
    status: RewardStatus
    mark_scheme_version: str | None
    feedback: RewardFeedbackOut | None
    created_at: datetime
    # Set when an admin records a payment made outside BIG
    paid_at: datetime | None
    payment_ref: str | None

    @classmethod
    def from_model(cls, reward: Reward) -> "RewardOut":
        feedback = reward.feedback
        result = feedback.question_result if feedback else None
        return cls(
            id=reward.id,
            recipient_username=reward.recipient.username,
            amount_sats=reward.amount_sats,
            reason=reward.reason,
            note=reward.note,
            status=reward.status,
            mark_scheme_version=reward.mark_scheme_version,
            feedback=(
                RewardFeedbackOut(
                    id=feedback.id,
                    public_ref=feedback.public_ref,
                    mark_scheme_version=feedback.mark_scheme_version,
                    question_result_id=feedback.question_result_id,
                    session_id=result.session_id if result else None,
                    question_number=result.question_number if result else None,
                    sub_part=result.sub_part if result else None,
                )
                if feedback
                else None
            ),
            created_at=reward.created_at,
            paid_at=reward.paid_at,
            payment_ref=reward.payment_ref,
        )


class MyRewardsOut(BaseModel):
    total_owed_sats: int
    rewards: list[RewardOut]


class OwedGroupOut(BaseModel):
    recipient_id: uuid.UUID
    recipient_username: str
    # Where the admin can send the payment by hand, if the recipient has given one
    blink_address: str | None
    total_owed_sats: int
    rewards: list[RewardOut]


class ManualAwardIn(BaseModel):
    recipient_username: str
    reason: RewardReason
    mark_scheme_version: str
    # Defaults to SCHEME_REWARD_SATS
    amount_sats: int | None = Field(default=None, gt=0)
    note: Note

    @field_validator("reason")
    @classmethod
    def _manual_reason(cls, value: RewardReason) -> RewardReason:
        if value not in MANUAL_REASONS:
            raise ValueError("reason must be mark_scheme or scheme_improvement; feedback is rewarded on approval")
        return value


class MarkPaidIn(BaseModel):
    payment_ref: PaymentRef


class CancelIn(BaseModel):
    note: Note
