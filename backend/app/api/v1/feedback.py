from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.feedback import Feedback, FeedbackStatus, FeedbackTarget
from app.models.question_result import QuestionResult
from app.models.reward import RewardReason
from app.models.user import User
from app.repositories.feedback_repo import (
    FeedbackError,
    FeedbackRepository,
    NotEditableError,
    check_target,
)
from app.repositories.reward_repo import RewardRepository
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackEdit,
    FeedbackOut,
    FeedbackReviewOut,
    FeedbackStatusUpdate,
)
from app.schemas.reward import RewardOut
from app.services.auth_service import get_current_admin, get_current_user
from app.services.grading.scheme_store import get_visible_record, load_repo_schemes

router = APIRouter(prefix="/feedback", tags=["feedback"])


async def _require_visible_result(session: AsyncSession, result_id: UUID, user: User) -> None:
    """Question results are visible to their owner and to admins; anything else is a 404."""
    result = await session.get(QuestionResult, result_id)
    if result is None or not (result.owner_id == user.id or user.is_admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question result not found")


async def _require_visible_scheme(session: AsyncSession, scheme_version: str, user: User) -> None:
    if scheme_version in load_repo_schemes():
        return
    if await get_visible_record(session, scheme_version, user.id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Mark scheme {scheme_version!r} not found"
        )


def _can_see(feedback: Feedback, user: User) -> bool:
    return (
        feedback.status == FeedbackStatus.APPROVED
        or (feedback.status == FeedbackStatus.PENDING and feedback.author_id == user.id)
        or user.is_admin
    )


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FeedbackOut:
    try:
        check_target(payload.target_type, payload.question_result_id, payload.mark_scheme_version)
    except FeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if payload.target_type == FeedbackTarget.QUESTION_RESULT:
        assert payload.question_result_id is not None
        await _require_visible_result(session, payload.question_result_id, user)
    else:
        assert payload.mark_scheme_version is not None
        await _require_visible_scheme(session, payload.mark_scheme_version, user)

    repo = FeedbackRepository(session)
    if payload.parent_id is not None:
        parent = await repo.get_by_id(payload.parent_id)
        if parent is None or not _can_see(parent, user):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="The feedback being replied to was not found"
            )

    try:
        feedback = await repo.create(
            author_id=user.id,
            target_type=payload.target_type,
            question_result_id=payload.question_result_id,
            mark_scheme_version=payload.mark_scheme_version,
            parent_id=payload.parent_id,
            body=payload.body,
            author_context=payload.author_context,
        )
    except FeedbackError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await session.commit()
    return FeedbackOut.from_model(feedback)


@router.get("/result/{result_id}", response_model=list[FeedbackOut])
async def list_result_feedback(
    result_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[FeedbackOut]:
    """Approved feedback on the result, plus the caller's own pending items."""
    await _require_visible_result(session, result_id, user)
    items = await FeedbackRepository(session).list_for_question_result(result_id, user.id)
    return [FeedbackOut.from_model(f) for f in items]


@router.get("/scheme/{scheme_version}", response_model=list[FeedbackOut])
async def list_scheme_feedback(
    scheme_version: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[FeedbackOut]:
    """Approved feedback on the scheme, plus the caller's own pending items."""
    await _require_visible_scheme(session, scheme_version, user)
    items = await FeedbackRepository(session).list_for_scheme(scheme_version, user.id)
    return [FeedbackOut.from_model(f) for f in items]


@router.get("/pending", response_model=list[FeedbackOut])
async def list_pending_feedback(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> list[FeedbackOut]:
    items = await FeedbackRepository(session).list_pending()
    return [FeedbackOut.from_model(f) for f in items]


@router.patch("/{feedback_id}", response_model=FeedbackOut)
async def edit_feedback(
    feedback_id: UUID,
    payload: FeedbackEdit,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FeedbackOut:
    repo = FeedbackRepository(session)
    # Locked so an admin's review can't land between the status check and the edit
    feedback = await repo.get_by_id(feedback_id, for_update=True)
    if feedback is None or not _can_see(feedback, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    if feedback.author_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can edit this feedback"
        )

    try:
        await repo.update_body(feedback, payload.body)
    except NotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return FeedbackOut.from_model(feedback)


@router.patch("/{feedback_id}/status", response_model=FeedbackReviewOut)
async def set_feedback_status(
    feedback_id: UUID,
    payload: FeedbackStatusUpdate,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> FeedbackReviewOut:
    repo = FeedbackRepository(session)
    # The row lock also serialises concurrent approvals, so only one of them can award
    feedback = await repo.get_by_id(feedback_id, for_update=True)
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")

    await repo.set_status(feedback, payload.status, admin.id)

    # Approval records sats as owed, in the same transaction; it pays nothing.
    # Re-approving keeps the existing reward rather than awarding again.
    rewards = RewardRepository(session)
    reward = await rewards.get_for_feedback(feedback.id)
    if payload.status == FeedbackStatus.APPROVED and reward is None:
        reward = await rewards.create(
            recipient_id=feedback.author_id,
            amount_sats=get_settings().FEEDBACK_REWARD_SATS,
            reason=RewardReason.FEEDBACK,
            note=f"Approved feedback {feedback.public_ref}",
            feedback_id=feedback.id,
            awarded_by_id=admin.id,
        )
    await session.commit()
    return FeedbackReviewOut(
        **FeedbackOut.from_model(feedback).model_dump(),
        reward=RewardOut.from_model(reward) if reward else None,
    )
