"""Paying one reward over Lightning, with a record written before any money can move."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payout_attempt import BLOCKING_STATUSES, AttemptStatus, PayoutAttempt
from app.models.reward import Reward, RewardStatus
from app.repositories.reward_repo import RewardError, RewardRepository
from app.services.payouts import blink

logger = logging.getLogger(__name__)


class PayoutError(Exception):
    """A payout refused before anything was sent; the message is safe to show."""


class PayoutUnavailable(PayoutError):
    pass


class PayoutNotFound(PayoutError):
    pass


class PayoutRefused(PayoutError):
    pass


@dataclass
class PayoutOutcome:
    attempt: PayoutAttempt
    reward: Reward


async def list_attempts(db: AsyncSession, reward_id: UUID) -> list[PayoutAttempt]:
    result = await db.execute(
        select(PayoutAttempt)
        .where(PayoutAttempt.reward_id == reward_id)
        .order_by(PayoutAttempt.created_at)
    )
    return list(result.scalars().all())


async def pay_reward(db: AsyncSession, reward_id: UUID) -> PayoutOutcome:
    """Pay one owed reward to its recipient's Lightning address.

    The attempt is committed as "attempting" before Blink is called, so a crash mid-payment leaves
    evidence, and that attempt blocks any retry until an admin has checked what happened.
    """
    problem = blink.config_problem()
    if problem:
        raise PayoutUnavailable(problem)

    rewards = RewardRepository(db)
    # Locked until the attempt is committed, so two concurrent requests can't both get past the guard
    reward = await rewards.get_by_id(reward_id, for_update=True)
    if reward is None:
        raise PayoutNotFound("Reward not found.")
    if reward.status != RewardStatus.OWED:
        raise PayoutRefused(f"This reward is {reward.status.value}; only owed rewards can be paid.")
    address = reward.recipient.blink_address
    if not address:
        raise PayoutRefused(
            f"{reward.recipient.username} has not saved a Lightning address, so this reward can't be paid."
        )

    blocking = await db.scalar(
        select(PayoutAttempt)
        .where(
            PayoutAttempt.reward_id == reward.id,
            PayoutAttempt.status.in_([s.value for s in BLOCKING_STATUSES]),
        )
        .limit(1)
    )
    if blocking is not None:
        raise PayoutRefused(_blocked_message(blocking))

    attempt = PayoutAttempt(
        reward_id=reward.id,
        amount_sats=reward.amount_sats,
        lightning_address=address,
        status=AttemptStatus.ATTEMPTING.value,
    )
    db.add(attempt)
    try:
        await db.commit()
    except IntegrityError:
        # The partial unique index caught a concurrent attempt the lock somehow didn't
        await db.rollback()
        raise PayoutRefused("Another payment for this reward is already in progress.")
    logger.info("Payout attempt %s for reward %s: sending %d sats", attempt.id, reward.id, reward.amount_sats)

    try:
        result = await blink.send_to_lightning_address(
            address, reward.amount_sats, memo=reward.note
        )
    except RuntimeError as exc:
        # Configuration changed between the check above and now; nothing was sent
        result = blink.PaymentResult("failed", [str(exc)], {})
    except Exception as exc:
        # Unknown failure after the attempt was recorded: assume the sats may have gone
        logger.exception("Payout attempt %s: unexpected error", attempt.id)
        result = blink.PaymentResult(
            "pending", [f"Unexpected error ({type(exc).__name__}); the payment may have gone through."], {}
        )

    attempt.status = result.status
    attempt.blink_status = result.blink_status
    attempt.error_message = "; ".join(result.errors) or None
    attempt.completed_at = datetime.now(UTC)

    if result.paid:
        payment_ref = f"blink:{result.transaction_id}" if result.transaction_id else f"blink-attempt:{attempt.id}"
        try:
            reward = await rewards.mark_paid(reward.id, payment_ref)
        except RewardError as exc:
            # Paid, but the reward changed underneath (e.g. cancelled meanwhile): keep the evidence
            attempt.error_message = f"Paid, but the reward could not be marked paid: {exc}"
    await db.commit()
    logger.info("Payout attempt %s for reward %s: %s", attempt.id, reward.id, attempt.status)

    reloaded = await rewards.get_by_id(reward.id)
    assert reloaded is not None
    return PayoutOutcome(attempt=attempt, reward=reloaded)


def _blocked_message(attempt: PayoutAttempt) -> str:
    if attempt.status in (AttemptStatus.SUCCESS.value, AttemptStatus.ALREADY_PAID.value):
        return "This reward has already been paid over Lightning."
    if attempt.status == AttemptStatus.PENDING.value:
        return (
            "An earlier payment for this reward is pending and may still arrive. Check it in the "
            "Blink dashboard before doing anything else."
        )
    return (
        "An earlier payment for this reward was started and never finished. Check the Blink "
        "dashboard to see whether it went out before doing anything else."
    )
