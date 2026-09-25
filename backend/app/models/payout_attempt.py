import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.reward import Reward


class AttemptStatus(str, enum.Enum):
    ATTEMPTING = "attempting"
    SUCCESS = "success"
    FAILED = "failed"
    # The outcome is unknown (Blink said PENDING, or the call timed out); the sats may yet arrive
    PENDING = "pending"
    ALREADY_PAID = "already_paid"


# Statuses that mean the sats have gone, or may have: a reward with one of these can't be paid again
BLOCKING_STATUSES = (
    AttemptStatus.ATTEMPTING,
    AttemptStatus.PENDING,
    AttemptStatus.SUCCESS,
    AttemptStatus.ALREADY_PAID,
)
_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in AttemptStatus)
_BLOCKING_VALUES = ", ".join(f"'{s.value}'" for s in BLOCKING_STATUSES)


class PayoutAttempt(Base):
    """One try at paying a reward over Lightning. Written before the network call, so a crash
    mid-payment still leaves a record."""

    __tablename__ = "payout_attempts"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_payout_attempts_status"),
        # Double-payment backstop: at most one attempt per reward that has, or may have, paid
        Index(
            "uq_payout_attempts_one_live_per_reward",
            "reward_id",
            unique=True,
            postgresql_where=text(f"status IN ({_BLOCKING_VALUES})"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reward_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rewards.id"), index=True, nullable=False
    )
    amount_sats: Mapped[int] = mapped_column(Integer, nullable=False)
    # The recipient's address at the time; they may change it later
    lightning_address: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False, default=AttemptStatus.ATTEMPTING.value)
    # Blink's own PaymentSendResult (SUCCESS, FAILURE, PENDING, ALREADY_PAID), when it answered
    blink_status: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reward: Mapped["Reward"] = relationship("Reward", back_populates="payout_attempts")
