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

    Each judged question is counted once per grader: for every (session, grader type,
    scheme version) only the most recent grading run is used, and earlier runs of the
    same grader on the same session are ignored. Otherwise re-running a grader would
    inflate the sample size, since every run stores its own row per question. This
    matters most for the deterministic mark scheme grader, which is cheap to re-run and
    gives the same answer each time, so repeated runs would count the same decision
    again and again and make the accuracy look better-founded than it is. The latest
    run is the one with the newest created_at (ties broken by grading_run_id so the
    choice is deterministic).
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

    # Rank each run within its (session, grader type, scheme version) group, newest first.
    # A run's timestamp is that of its earliest result (all of a run's rows share it in practice).
    run_group = (
        QuestionResult.session_id,
        QuestionResult.grader_type,
        QuestionResult.mark_scheme_version,
    )
    ranked_runs = select(
        QuestionResult.grading_run_id.label("grading_run_id"),
        func.row_number()
        .over(
            partition_by=run_group,
            order_by=(func.min(QuestionResult.created_at).desc(), QuestionResult.grading_run_id.desc()),
        )
        .label("recency"),
    ).group_by(*run_group, QuestionResult.grading_run_id)
    if owner_id is not None:
        ranked_runs = ranked_runs.where(QuestionResult.owner_id == owner_id)
    ranked = ranked_runs.subquery("ranked_runs")

    query = (
        select(
            QuestionResult.grader_type,
            QuestionResult.mark_scheme_version,
            func.count(QuestionResult.id).label("judged"),
            func.sum(correct).label("correct"),
        )
        .join(ranked, (ranked.c.grading_run_id == QuestionResult.grading_run_id) & (ranked.c.recency == 1))
        # Judged-ness is decided after picking the latest run, not before: a latest run with no
        # verdicts contributes nothing rather than falling back to an older, judged run.
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
