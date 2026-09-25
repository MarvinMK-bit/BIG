import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_session import GradingSession
from app.models.question_result import GraderType, QuestionResult
from app.models.user import User
from app.services.grading.accuracy import grader_was_correct, latest_judged_results


def question_sort_key(number: str, sub_part: str | None) -> tuple[int, str, str]:
    """Sort "2" before "10" and a bare question before its sub-parts; non-numeric labels go last."""
    numeric = int(number) if number.isdigit() else sys.maxsize
    return numeric, number, (sub_part or "").strip("()").casefold()


@dataclass
class GraderVerdict:
    grader_type: str
    mark_scheme_version: str | None
    mark_awarded: Decimal | None
    max_mark: Decimal
    agreed: bool


@dataclass
class JudgedQuestion:
    session_id: UUID
    owner_id: UUID
    owner_username: str
    original_filename: str
    subject: str | None
    question_number: str
    sub_part: str | None
    extracted_answer: str | None
    verdict: bool
    verdict_set_at: datetime | None
    graders: list[GraderVerdict]


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
            .values(
                is_correct_per_human=is_correct,
                verdict_set_at=None if is_correct is None else func.now(),
            )
        )
        await self.session.flush()
        return question_result

    async def list_judged(
        self,
        owner_id: UUID | None,
        *,
        limit: int = 100,
        offset: int = 0,
        subject: str | None = None,
    ) -> tuple[list[JudgedQuestion], int]:
        """One entry per judged question, newest verdict first, and the total number of them.

        A question is a (session, question number, sub-part); its graders are the latest run
        of each grader on that session, the same results measure_accuracy counts. Verdicts set
        before verdict_set_at existed have no timestamp and sort after the rest, by grading
        time. owner_id=None covers every owner and must only be used for admin views.
        """
        key = (QuestionResult.session_id, QuestionResult.question_number, QuestionResult.sub_part)
        questions = latest_judged_results(
            *key,
            func.max(QuestionResult.verdict_set_at).label("verdict_set_at"),
            func.max(QuestionResult.created_at).label("graded_at"),
            owner_id=owner_id,
            subject=subject,
        ).group_by(*key)

        total = await self.session.scalar(select(func.count()).select_from(questions.subquery()))
        page = (
            await self.session.execute(
                questions.order_by(
                    func.max(QuestionResult.verdict_set_at).desc().nulls_last(),
                    func.max(QuestionResult.created_at).desc(),
                    *key,
                )
                .limit(limit)
                .offset(offset)
            )
        ).all()
        if not page:
            return [], total or 0

        # The page's keys are already filtered by subject, so rows only need matching to them
        rows = (
            await self.session.execute(
                latest_judged_results(
                    QuestionResult,
                    grader_was_correct().label("agreed"),
                    GradingSession.original_filename,
                    GradingSession.subject,
                    User.username,
                    owner_id=owner_id,
                )
                .join(GradingSession, GradingSession.id == QuestionResult.session_id)
                .join(User, User.id == QuestionResult.owner_id)
                .where(QuestionResult.session_id.in_({row.session_id for row in page}))
            )
        ).all()

        by_key: dict[tuple[UUID, str, str | None], list[Any]] = {}
        for row in rows:
            result = row.QuestionResult
            by_key.setdefault((result.session_id, result.question_number, result.sub_part), []).append(row)

        judged: list[JudgedQuestion] = []
        for question in page:
            graded = by_key.get((question.session_id, question.question_number, question.sub_part), [])
            if not graded:
                continue
            graded.sort(
                key=lambda row: (
                    row.QuestionResult.grader_type != GraderType.LLM,
                    row.QuestionResult.mark_scheme_version or "",
                )
            )
            first = graded[0]
            # The scheme grader stores the answer text verbatim; fall back to the LLM's extraction
            answers = sorted(
                (row.QuestionResult for row in graded if row.QuestionResult.extracted_answer),
                key=lambda r: r.grader_type != GraderType.MARK_SCHEME,
            )
            judged.append(
                JudgedQuestion(
                    session_id=question.session_id,
                    owner_id=first.QuestionResult.owner_id,
                    owner_username=first.username,
                    original_filename=first.original_filename,
                    subject=first.subject,
                    question_number=question.question_number,
                    sub_part=question.sub_part,
                    extracted_answer=answers[0].extracted_answer if answers else None,
                    verdict=bool(first.QuestionResult.is_correct_per_human),
                    verdict_set_at=question.verdict_set_at,
                    graders=[
                        GraderVerdict(
                            grader_type=row.QuestionResult.grader_type.value,
                            mark_scheme_version=row.QuestionResult.mark_scheme_version,
                            mark_awarded=row.QuestionResult.mark_awarded,
                            max_mark=row.QuestionResult.max_mark,
                            agreed=bool(row.agreed),
                        )
                        for row in graded
                    ],
                )
            )
        return judged, total or 0
