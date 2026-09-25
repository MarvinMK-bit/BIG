from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Date, Select, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_session import GradingSession
from app.models.question_result import QuestionResult

Bucket = Literal["day", "week", "month"]
BUCKETS: tuple[Bucket, ...] = ("day", "week", "month")


@dataclass
class GraderAccuracy:
    grader_type: str
    mark_scheme_version: str | None
    judged_questions: int
    correct_decisions: int
    accuracy: float | None


@dataclass
class AccuracyPoint:
    period_start: date
    grader_type: str
    mark_scheme_version: str | None
    judged_questions: int
    correct_decisions: int
    accuracy: float | None
    cumulative_judged: int
    cumulative_correct: int
    cumulative_accuracy: float | None


def grader_was_correct() -> Any:
    """1 when the grader's decision matches the human verdict, else 0.

    Correct means the human said the answer was right and the grader awarded full
    marks, or the human said it was wrong and the grader awarded less than full marks.
    """
    return case(
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


def latest_judged_results(
    *columns: Any, owner_id: UUID | None = None, subject: str | None = None
) -> Select[Any]:
    """Select columns from judged results of each grader's latest run on each session.

    Each judged question is counted once per grader: for every (session, grader type,
    scheme version) only the most recent grading run is used, and earlier runs of the
    same grader on the same session are ignored. Otherwise re-running a grader would
    inflate the sample size, since every run stores its own row per question. This
    matters most for the deterministic mark scheme grader, which is cheap to re-run and
    gives the same answer each time, so repeated runs would count the same decision
    again and again and make the accuracy look better-founded than it is. The latest
    run is the one with the newest created_at (ties broken by grading_run_id so the
    choice is deterministic).

    owner_id=None covers every owner and must only be used for admin views.
    """
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
        select(*columns)
        .select_from(QuestionResult)
        .join(ranked, (ranked.c.grading_run_id == QuestionResult.grading_run_id) & (ranked.c.recency == 1))
        # Judged-ness is decided after picking the latest run, not before: a latest run with no
        # verdicts contributes nothing rather than falling back to an older, judged run.
        .where(QuestionResult.is_correct_per_human.is_not(None))
    )
    if owner_id is not None:
        query = query.where(QuestionResult.owner_id == owner_id)
    if subject is not None:
        query = query.join(GradingSession, GradingSession.id == QuestionResult.session_id).where(
            GradingSession.subject == subject
        )
    return query


async def measure_accuracy(
    db: AsyncSession,
    owner_id: UUID | None = None,
    subject: str | None = None,
) -> list[GraderAccuracy]:
    """Measure each grader against human verdicts, per grader type and scheme version.

    See grader_was_correct for the rule and latest_judged_results for which results
    count. owner_id=None measures across every owner and must only be used for admin views.
    """
    query = (
        latest_judged_results(
            QuestionResult.grader_type,
            QuestionResult.mark_scheme_version,
            func.count(QuestionResult.id).label("judged"),
            func.sum(grader_was_correct()).label("correct"),
            owner_id=owner_id,
            subject=subject,
        )
        .group_by(QuestionResult.grader_type, QuestionResult.mark_scheme_version)
        .order_by(QuestionResult.grader_type, QuestionResult.mark_scheme_version)
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


async def measure_accuracy_over_time(
    db: AsyncSession,
    owner_id: UUID | None = None,
    subject: str | None = None,
    bucket: Bucket = "week",
) -> list[AccuracyPoint]:
    """measure_accuracy per time bucket, with running totals, oldest bucket first per grader.

    Results are bucketed by their created_at, truncated in UTC to the start of the day,
    ISO week (Monday) or month. Only buckets with judged results appear. The cumulative
    fields sum every bucket up to and including this one for the same grader and scheme
    version, so the series shows the trend rather than per-period noise.
    """
    if bucket not in BUCKETS:
        raise ValueError(f"bucket must be one of {', '.join(BUCKETS)}, got {bucket!r}")

    period = cast(
        func.date_trunc(bucket, func.timezone("UTC", QuestionResult.created_at)), Date
    ).label("period_start")
    judged = latest_judged_results(
        QuestionResult.grader_type,
        QuestionResult.mark_scheme_version,
        period,
        grader_was_correct().label("correct"),
        owner_id=owner_id,
        subject=subject,
    ).subquery("judged")

    # Grouping on the subquery's column avoids repeating date_trunc with a second bound parameter
    grader = (judged.c.grader_type, judged.c.mark_scheme_version)
    per_period = (
        select(
            *grader,
            judged.c.period_start,
            func.count().label("judged"),
            func.sum(judged.c.correct).label("correct"),
        )
        .group_by(*grader, judged.c.period_start)
        .subquery("per_period")
    )

    series = (per_period.c.grader_type, per_period.c.mark_scheme_version)
    running = {"partition_by": series, "order_by": per_period.c.period_start}
    query = select(
        per_period,
        func.sum(per_period.c.judged).over(**running).label("cumulative_judged"),
        func.sum(per_period.c.correct).over(**running).label("cumulative_correct"),
    ).order_by(*series, per_period.c.period_start)

    points: list[AccuracyPoint] = []
    for row in (await db.execute(query)).all():
        judged_count, correct = int(row.judged), int(row.correct or 0)
        cumulative_judged, cumulative_correct = int(row.cumulative_judged), int(row.cumulative_correct or 0)
        points.append(
            AccuracyPoint(
                period_start=row.period_start,
                grader_type=row.grader_type.value,
                mark_scheme_version=row.mark_scheme_version,
                judged_questions=judged_count,
                correct_decisions=correct,
                accuracy=correct / judged_count if judged_count else None,
                cumulative_judged=cumulative_judged,
                cumulative_correct=cumulative_correct,
                cumulative_accuracy=(
                    cumulative_correct / cumulative_judged if cumulative_judged else None
                ),
            )
        )
    return points
