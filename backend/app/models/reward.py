import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback
    from app.models.user import User


class RewardReason(str, enum.Enum):
    FEEDBACK = "feedback"
    MARK_SCHEME = "mark_scheme"
    SCHEME_IMPROVEMENT = "scheme_improvement"


class RewardStatus(str, enum.Enum):
    OWED = "owed"
    PAID = "paid"
    CANCELLED = "cancelled"


class Reward(Base):
    """A ledger line: sats owed to someone. Recording one moves no money."""

    __tablename__ = "rewards"
    __table_args__ = (CheckConstraint("amount_sats > 0", name="ck_rewards_amount_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    amount_sats: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[RewardReason] = mapped_column(Enum(RewardReason, name="reward_reason"), nullable=False)
    # Why it was awarded
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Unique so approving one item can never award twice
    feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id"), unique=True, nullable=True
    )
    mark_scheme_version: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[RewardStatus] = mapped_column(
        Enum(RewardStatus, name="reward_status"), nullable=False, default=RewardStatus.OWED
    )
    awarded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The external payment's id, entered by the admin who paid it
    payment_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])
    awarded_by: Mapped["User"] = relationship("User", foreign_keys=[awarded_by_id])
    feedback: Mapped["Feedback | None"] = relationship("Feedback")
