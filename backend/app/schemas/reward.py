import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

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


class PayoutAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reward_id: uuid.UUID
    amount_sats: int
    lightning_address: str
    status: str
    blink_status: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class OwedRewardOut(RewardOut):
    attempts: list[PayoutAttemptOut]


class OwedGroupOut(BaseModel):
    recipient_id: uuid.UUID
    recipient_username: str
    # The recipient's Lightning address; payouts go here, and without one they can't be paid
    blink_address: str | None
    total_owed_sats: int
    rewards: list[OwedRewardOut]


class PayoutOut(BaseModel):
    attempt: PayoutAttemptOut
    reward: RewardOut


class PayoutStatusOut(BaseModel):
    """What the payouts banner shows. Deliberately excludes the API key and wallet id."""

    enabled: bool
    # Key and wallet id both set
    configured: bool
    network: Literal["staging", "mainnet", "other"]
    api_host: str
    # Why a Pay button would be refused right now, if it would
    problem: str | None


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
