from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_session import GradingSession
from app.models.question_result import QuestionResult


@dataclass
class GraderAccuracy:
    grader_type: str
    mark_scheme_version: str | None
    judged_questions: int
    correct_decisions: int
    accuracy: float | None


async def measure_accuracy(
    db: AsyncSession,
    owner_id: UUID | None = None,
    subject: str | None = None,
) -> list[GraderAccuracy]:
    """Measure each grader against human verdicts, per grader type and scheme version.

    A grader's decision is correct when the human said the answer was right and it
    awarded full marks, or the human said it was wrong and it awarded less than full
    marks. Results without a human verdict are excluded. owner_id=None measures
    across every owner and must only be used for admin views.
    """
    correct = case(
        (
            (QuestionResult.is_correct_per_human.is_(True))
            & (QuestionResult.mark_awarded == QuestionResult.max_mark),
            1,
        ),
        (
            (QuestionResult.is_correct_per_human.is_(False))
            & (QuestionResult.mark_awarded < QuestionResult.max_mark),
            1,
        ),
        else_=0,
    )

    query = (
        select(
            QuestionResult.grader_type,
            QuestionResult.mark_scheme_version,
            func.count(QuestionResult.id).label("judged"),
            func.sum(correct).label("correct"),
        )
        .where(QuestionResult.is_correct_per_human.is_not(None))
        .group_by(QuestionResult.grader_type, QuestionResult.mark_scheme_version)
        .order_by(QuestionResult.grader_type, QuestionResult.mark_scheme_version)
    )
    if owner_id is not None:
        query = query.where(QuestionResult.owner_id == owner_id)
    if subject is not None:
        query = query.join(GradingSession, GradingSession.id == QuestionResult.session_id).where(
            GradingSession.subject == subject
        )

    rows = (await db.execute(query)).all()
    return [
        GraderAccuracy(
            grader_type=row.grader_type.value,
            mark_scheme_version=row.mark_scheme_version,
            judged_questions=row.judged,
            correct_decisions=int(row.correct or 0),
            accuracy=int(row.correct or 0) / row.judged if row.judged else None,
        )
        for row in rows
    ]
