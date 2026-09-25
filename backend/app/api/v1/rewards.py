from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.repositories.reward_repo import (
    RewardError,
    RewardNotFoundError,
    RewardRepository,
    RewardStateError,
)
from app.repositories.scheme_repo import MarkSchemeRepository
from app.repositories.user_repo import UserRepository
from app.schemas.reward import (
    CancelIn,
    ManualAwardIn,
    MarkPaidIn,
    MyRewardsOut,
    OwedGroupOut,
    OwedRewardOut,
    PayoutAttemptOut,
    PayoutOut,
    PayoutStatusOut,
    RewardOut,
)
from app.services.auth_service import get_current_admin, get_current_user
from app.services.grading.scheme_store import load_repo_schemes
from app.services.payouts import blink
from app.services.payouts.service import (
    PayoutError,
    PayoutNotFound,
    PayoutUnavailable,
    list_attempts,
    pay_reward,
)

# The ledger, plus one deliberate way to pay: POST /{id}/pay sends a single reward over Lightning.
# There is intentionally no endpoint that pays several rewards at once.
router = APIRouter(prefix="/rewards", tags=["rewards"])


def _ledger_error(exc: RewardError) -> HTTPException:
    if isinstance(exc, RewardNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, RewardStateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/me", response_model=MyRewardsOut)
async def my_rewards(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MyRewardsOut:
    repo = RewardRepository(session)
    rewards = await repo.list_for_recipient(user.id)
    return MyRewardsOut(
        total_owed_sats=await repo.balance_for_recipient(user.id),
        rewards=[RewardOut.from_model(r) for r in rewards],
    )


@router.post("", response_model=RewardOut, status_code=status.HTTP_201_CREATED)
async def award(
    payload: ManualAwardIn,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> RewardOut:
    """Award sats for a scheme or an improvement to one. Breadth is a judgement call, so an admin decides."""
    recipient = await UserRepository(session).get_by_username(payload.recipient_username)
    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {payload.recipient_username!r} not found"
        )

    version = payload.mark_scheme_version
    if version not in load_repo_schemes() and await MarkSchemeRepository(session).get_by_version(version) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mark scheme {version!r} not found")

    try:
        reward = await RewardRepository(session).create(
            recipient_id=recipient.id,
            amount_sats=payload.amount_sats or get_settings().SCHEME_REWARD_SATS,
            reason=payload.reason,
            note=payload.note,
            mark_scheme_version=version,
            awarded_by_id=admin.id,
        )
    except RewardError as exc:
        raise _ledger_error(exc)
    await session.commit()
    return RewardOut.from_model(reward)


@router.get("/owed", response_model=list[OwedGroupOut])
async def owed(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> list[OwedGroupOut]:
    """Everything owed, one group per recipient, largest balance first."""
    groups: dict[UUID, OwedGroupOut] = {}
    for reward in await RewardRepository(session).list_owed():
        group = groups.get(reward.recipient_id)
        if group is None:
            group = groups[reward.recipient_id] = OwedGroupOut(
                recipient_id=reward.recipient_id,
                recipient_username=reward.recipient.username,
                blink_address=reward.recipient.blink_address,
                total_owed_sats=0,
                rewards=[],
            )
        group.total_owed_sats += reward.amount_sats
        group.rewards.append(
            OwedRewardOut(
                **RewardOut.from_model(reward).model_dump(),
                attempts=[PayoutAttemptOut.model_validate(a) for a in reward.payout_attempts],
            )
        )
    return sorted(groups.values(), key=lambda g: (-g.total_owed_sats, g.recipient_username))


@router.patch("/{reward_id}/paid", response_model=RewardOut)
async def mark_paid(
    reward_id: UUID,
    payload: MarkPaidIn,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> RewardOut:
    """Record a payment the admin already made outside BIG."""
    try:
        reward = await RewardRepository(session).mark_paid(reward_id, payload.payment_ref)
    except RewardError as exc:
        raise _ledger_error(exc)
    await session.commit()
    return RewardOut.from_model(reward)


@router.patch("/{reward_id}/cancel", response_model=RewardOut)
async def cancel(
    reward_id: UUID,
    payload: CancelIn,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> RewardOut:
    try:
        reward = await RewardRepository(session).cancel(reward_id, payload.note)
    except RewardError as exc:
        raise _ledger_error(exc)
    await session.commit()
    return RewardOut.from_model(reward)


@router.get("/payouts", response_model=PayoutStatusOut)
async def payout_status(admin: User = Depends(get_current_admin)) -> PayoutStatusOut:
    """Whether Pay would send, and to which network. Never includes the key or wallet id."""
    settings = get_settings()
    return PayoutStatusOut(
        enabled=settings.PAYOUTS_ENABLED,
        configured=bool(
            settings.BLINK_API_KEY and settings.BLINK_API_KEY.get_secret_value() and settings.BLINK_WALLET_ID
        ),
        network=blink.network_of(settings.BLINK_API_URL),
        api_host=urlparse(settings.BLINK_API_URL).hostname or settings.BLINK_API_URL,
        problem=blink.config_problem(settings),
    )


@router.post("/{reward_id}/pay", response_model=PayoutOut)
async def pay(
    reward_id: UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> PayoutOut:
    """Send one owed reward over Lightning. A failed payment is still a 200: the attempt is recorded
    and returned, and its status says what happened."""
    try:
        outcome = await pay_reward(session, reward_id)
    except PayoutUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except PayoutNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PayoutError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return PayoutOut(
        attempt=PayoutAttemptOut.model_validate(outcome.attempt),
        reward=RewardOut.from_model(outcome.reward),
    )


@router.get("/{reward_id}/attempts", response_model=list[PayoutAttemptOut])
async def attempts(
    reward_id: UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> list[PayoutAttemptOut]:
    if await RewardRepository(session).get_by_id(reward_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reward not found")
    return [PayoutAttemptOut.model_validate(a) for a in await list_attempts(session, reward_id)]
