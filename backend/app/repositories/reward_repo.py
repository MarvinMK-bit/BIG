from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.feedback import Feedback
from app.models.reward import Reward, RewardReason, RewardStatus


class RewardError(ValueError):
    """A ledger change the rules forbid; the message is safe to show to the user."""


class DuplicateRewardError(RewardError):
    pass


class RewardStateError(RewardError):
    pass


class RewardNotFoundError(RewardError):
    pass


def _select() -> Select[tuple[Reward]]:
    # The recipient and the feedback it was for (with that feedback's question result) are
    # what every caller shows alongside the amount
    return select(Reward).options(
        selectinload(Reward.recipient),
        selectinload(Reward.feedback).selectinload(Feedback.question_result),
    )


class RewardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        recipient_id: UUID,
        amount_sats: int,
        reason: RewardReason,
        awarded_by_id: UUID,
        note: str | None = None,
        feedback_id: UUID | None = None,
        mark_scheme_version: str | None = None,
    ) -> Reward:
        """Record sats as owed. This moves no money."""
        if amount_sats <= 0:
            raise RewardError("A reward must be a positive number of sats.")
        if feedback_id is not None:
            # The unique constraint is the backstop; this gives a readable error first
            existing = await self.get_for_feedback(feedback_id)
            if existing is not None:
                raise DuplicateRewardError(
                    f"This feedback has already been rewarded ({existing.amount_sats} sats, "
                    f"{existing.status.value})."
                )

        reward = Reward(
            recipient_id=recipient_id,
            amount_sats=amount_sats,
            reason=reason,
            note=note,
            feedback_id=feedback_id,
            mark_scheme_version=mark_scheme_version,
            status=RewardStatus.OWED,
            awarded_by_id=awarded_by_id,
        )
        self.session.add(reward)
        await self.session.flush()
        # Reload so recipient and feedback are populated for the caller
        created = await self.get_by_id(reward.id)
        assert created is not None
        return created

    async def get_by_id(self, reward_id: UUID, *, for_update: bool = False) -> Reward | None:
        query = _select().where(Reward.id == reward_id).execution_options(populate_existing=True)
        if for_update:
            query = query.with_for_update(of=Reward)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_feedback(self, feedback_id: UUID) -> Reward | None:
        result = await self.session.execute(_select().where(Reward.feedback_id == feedback_id))
        return result.scalar_one_or_none()

    async def list_for_recipient(self, recipient_id: UUID) -> list[Reward]:
        """Every reward for the recipient, whatever its status, newest first."""
        result = await self.session.execute(
            _select().where(Reward.recipient_id == recipient_id).order_by(Reward.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_owed(self) -> list[Reward]:
        """Everything still owed, oldest first. For admins only."""
        result = await self.session.execute(
            _select().where(Reward.status == RewardStatus.OWED).order_by(Reward.created_at)
        )
        return list(result.scalars().all())

    async def balance_for_recipient(self, recipient_id: UUID) -> int:
        """Total sats still OWED; paid and cancelled rewards don't count."""
        total = await self.session.scalar(
            select(func.coalesce(func.sum(Reward.amount_sats), 0)).where(
                Reward.recipient_id == recipient_id, Reward.status == RewardStatus.OWED
            )
        )
        return int(total or 0)

    async def mark_paid(self, reward_id: UUID, payment_ref: str) -> Reward:
        """Record that an admin paid this outside BIG; payment_ref identifies that payment."""
        reward = await self._owed_for_update(reward_id, "marked paid")
        reward.status = RewardStatus.PAID
        reward.paid_at = datetime.now(UTC)
        reward.payment_ref = payment_ref
        await self.session.flush()
        return reward

    async def cancel(self, reward_id: UUID, note: str) -> Reward:
        """Withdraw an owed reward. The reason is appended so the original note survives."""
        reward = await self._owed_for_update(reward_id, "cancelled")
        reward.status = RewardStatus.CANCELLED
        reward.note = f"{reward.note}\nCancelled: {note}" if reward.note else f"Cancelled: {note}"
        await self.session.flush()
        return reward

    async def _owed_for_update(self, reward_id: UUID, action: str) -> Reward:
        # Locked so a concurrent paid/cancel can't both succeed
        reward = await self.get_by_id(reward_id, for_update=True)
        if reward is None:
            raise RewardNotFoundError("Reward not found.")
        if reward.status != RewardStatus.OWED:
            raise RewardStateError(
                f"This reward is already {reward.status.value}; only owed rewards can be {action}."
            )
        return reward
