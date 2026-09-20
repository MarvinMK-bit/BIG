import sys
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_result import QuestionResult


def question_sort_key(number: str, sub_part: str | None) -> tuple[int, str, str]:
    """Sort "2" before "10" and a bare question before its sub-parts; non-numeric labels go last."""
    numeric = int(number) if number.isdigit() else sys.maxsize
    return numeric, number, (sub_part or "").strip("()").casefold()


class QuestionResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_run(self, grading_run_id: UUID, owner_id: UUID) -> list[QuestionResult]:
        result = await self.session.execute(
            select(QuestionResult).where(
                QuestionResult.grading_run_id == grading_run_id,
                QuestionResult.owner_id == owner_id,
            )
        )
        rows = list(result.scalars().all())
        rows.sort(key=lambda r: question_sort_key(r.question_number, r.sub_part))
        return rows

    async def list_for_session(self, session_id: UUID, owner_id: UUID) -> list[QuestionResult]:
        result = await self.session.execute(
            select(QuestionResult)
            .where(QuestionResult.session_id == session_id, QuestionResult.owner_id == owner_id)
            .order_by(QuestionResult.created_at, QuestionResult.question_number, QuestionResult.sub_part)
        )
        return list(result.scalars().all())

    async def list_runs_for_session(
        self, session_id: UUID, owner_id: UUID
    ) -> list[tuple[UUID, str, str | None, datetime]]:
        first_created = func.min(QuestionResult.created_at).label("first_created")
        result = await self.session.execute(
            select(
                QuestionResult.grading_run_id,
                QuestionResult.grader_type,
                QuestionResult.mark_scheme_version,
                first_created,
            )
            .where(QuestionResult.session_id == session_id, QuestionResult.owner_id == owner_id)
            .group_by(
                QuestionResult.grading_run_id,
                QuestionResult.grader_type,
                QuestionResult.mark_scheme_version,
            )
            .order_by(first_created.desc(), QuestionResult.grading_run_id)
        )
        return [
            (row.grading_run_id, row.grader_type.value, row.mark_scheme_version, row.first_created)
            for row in result.all()
        ]

    async def set_human_verdict(
        self, result_id: UUID, owner_id: UUID, is_correct: bool | None
    ) -> QuestionResult | None:
        """Record a human verdict on the student's answer to a question.

        The verdict is a property of the student's answer, not of any one grader's
        judgement of it, so it is mirrored onto every result for the same session,
        question number and sub-part, across all grading runs and both grader types.
        Returns the requested result, or None if it does not exist or is not owned
        by owner_id. Passing None clears the verdict.
        """
        result = await self.session.execute(
            select(QuestionResult).where(
                QuestionResult.id == result_id, QuestionResult.owner_id == owner_id
            )
        )
        question_result = result.scalar_one_or_none()
        if question_result is None:
            return None

        sub_part_match = (
            QuestionResult.sub_part.is_(None)
            if question_result.sub_part is None
            else QuestionResult.sub_part == question_result.sub_part
        )
        await self.session.execute(
            update(QuestionResult)
            .where(
                QuestionResult.owner_id == owner_id,
                QuestionResult.session_id == question_result.session_id,
                QuestionResult.question_number == question_result.question_number,
                sub_part_match,
            )
            .values(is_correct_per_human=is_correct)
        )
        await self.session.flush()
        return question_result
