from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.feedback import Feedback, FeedbackStatus, FeedbackTarget, feedback_ref_seq

REVIEW_STATUSES = frozenset({FeedbackStatus.APPROVED, FeedbackStatus.REJECTED, FeedbackStatus.MUTED})


class FeedbackError(ValueError):
    """A request the feedback rules forbid; the message is safe to show to the user."""


class InvalidTargetError(FeedbackError):
    pass


class NestedReplyError(FeedbackError):
    pass


class NotEditableError(FeedbackError):
    pass


def check_target(
    target_type: FeedbackTarget, question_result_id: UUID | None, mark_scheme_version: str | None
) -> None:
    """Exactly one of question_result_id or mark_scheme_version, matching target_type."""
    if target_type == FeedbackTarget.QUESTION_RESULT:
        if question_result_id is None or mark_scheme_version is not None:
            raise InvalidTargetError(
                "Feedback on a question result must give question_result_id and no mark_scheme_version."
            )
    elif mark_scheme_version is None or question_result_id is not None:
        raise InvalidTargetError(
            "Feedback on a mark scheme must give mark_scheme_version and no question_result_id."
        )


def suffix_letters(index: int) -> str:
    """0 -> "a", 25 -> "z", 26 -> "aa": the letter part of a public_ref."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(ord("a") + rem) + letters
    return letters


def ref_number(public_ref: str) -> str:
    """The zero-padded number of a public_ref: "0012c" -> "0012"."""
    return public_ref.rstrip("abcdefghijklmnopqrstuvwxyz")


def _select() -> Select[tuple[Feedback]]:
    # Replies always come with their parent; the author and result say who wrote it and where
    return select(Feedback).options(
        selectinload(Feedback.parent),
        selectinload(Feedback.author),
        selectinload(Feedback.question_result),
    )


def _visible_to(viewer_id: UUID) -> ColumnElement[bool]:
    """Approved feedback, plus the viewer's own pending items."""
    return or_(
        Feedback.status == FeedbackStatus.APPROVED,
        and_(Feedback.author_id == viewer_id, Feedback.status == FeedbackStatus.PENDING),
    )


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        author_id: UUID,
        target_type: FeedbackTarget,
        question_result_id: UUID | None,
        mark_scheme_version: str | None,
        body: str,
        author_context: str | None = None,
        parent_id: UUID | None = None,
    ) -> Feedback:
        check_target(target_type, question_result_id, mark_scheme_version)

        if parent_id is None:
            number = await self.session.scalar(select(feedback_ref_seq.next_value()))
            public_ref = f"{number:04d}a"
        else:
            # Locking the parent serialises sibling replies, so two can't take the same letter
            parent = await self.get_by_id(parent_id, for_update=True)
            if parent is None:
                raise InvalidTargetError("The feedback being replied to does not exist.")
            if parent.parent_id is not None:
                raise NestedReplyError(
                    f"Feedback {parent.public_ref} is itself a reply; reply to "
                    f"{ref_number(parent.public_ref)}a instead."
                )
            if (parent.target_type, parent.question_result_id, parent.mark_scheme_version) != (
                target_type,
                question_result_id,
                mark_scheme_version,
            ):
                raise InvalidTargetError("A reply must have the same target as the feedback it replies to.")
            sibling_count = await self.session.scalar(
                select(func.count()).select_from(Feedback).where(Feedback.parent_id == parent.id)
            )
            public_ref = ref_number(parent.public_ref) + suffix_letters((sibling_count or 0) + 1)

        feedback = Feedback(
            public_ref=public_ref,
            author_id=author_id,
            target_type=target_type,
            question_result_id=question_result_id,
            mark_scheme_version=mark_scheme_version,
            parent_id=parent_id,
            body=body,
            author_context=author_context,
            status=FeedbackStatus.PENDING,
        )
        self.session.add(feedback)
        await self.session.flush()
        # Reload so the parent and author relationships are populated for the caller
        created = await self.get_by_id(feedback.id)
        assert created is not None
        return created

    async def get_by_id(self, feedback_id: UUID, *, for_update: bool = False) -> Feedback | None:
        query = _select().where(Feedback.id == feedback_id).execution_options(populate_existing=True)
        if for_update:
            query = query.with_for_update(of=Feedback)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_public_ref(self, public_ref: str) -> Feedback | None:
        result = await self.session.execute(_select().where(Feedback.public_ref == public_ref))
        return result.scalar_one_or_none()

    async def list_for_question_result(self, question_result_id: UUID, viewer_id: UUID) -> list[Feedback]:
        result = await self.session.execute(
            _select()
            .where(Feedback.question_result_id == question_result_id, _visible_to(viewer_id))
            .order_by(Feedback.created_at, Feedback.public_ref)
        )
        return list(result.scalars().all())

    async def list_for_scheme(self, mark_scheme_version: str, viewer_id: UUID) -> list[Feedback]:
        result = await self.session.execute(
            _select()
            .where(Feedback.mark_scheme_version == mark_scheme_version, _visible_to(viewer_id))
            .order_by(Feedback.created_at, Feedback.public_ref)
        )
        return list(result.scalars().all())

    async def list_pending(self) -> list[Feedback]:
        """Everything awaiting review, oldest first. For admins only."""
        result = await self.session.execute(
            _select()
            .where(Feedback.status == FeedbackStatus.PENDING)
            .order_by(Feedback.created_at, Feedback.public_ref)
        )
        return list(result.scalars().all())

    async def set_status(self, feedback: Feedback, status: FeedbackStatus, reviewer_id: UUID) -> Feedback:
        """Record an admin's review. Approval only marks the item; it pays nothing."""
        if status not in REVIEW_STATUSES:
            raise FeedbackError(f"Feedback can't be set back to {status.value}.")
        feedback.status = status
        feedback.reviewed_by_id = reviewer_id
        feedback.reviewed_at = datetime.now(UTC)
        await self.session.flush()
        return feedback

    async def update_body(self, feedback: Feedback, body: str) -> Feedback:
        """Ownership is the caller's check; this enforces that only pending feedback changes."""
        if feedback.status != FeedbackStatus.PENDING:
            raise NotEditableError(
                f"Feedback {feedback.public_ref} has been {feedback.status.value} and can no longer be edited."
            )
        feedback.body = body
        feedback.edited_at = datetime.now(UTC)
        await self.session.flush()
        return feedback
