from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_result import GraderType, QuestionResult
from app.repositories.result_repo import QuestionResultRepository, question_sort_key
from app.services.grading.progress import breakdown_awards, mark_progress
from app.services.grading.schemes import mark_labels

_QuestionKey = tuple[str, str | None]


class RunNotFoundError(ValueError):
    pass


@dataclass
class QuestionComparison:
    question_number: str
    sub_part: str | None
    extracted_answer: str | None
    llm_mark: Decimal | None
    scheme_mark: Decimal | None
    max_mark: Decimal | None
    # Coded questions: how many marks, T to D, each grader earned before its first zero
    llm_progress: int | None
    scheme_progress: int | None
    progress_max: int | None
    # Which grader got further, e.g. "Mark scheme reached A (3); LLM reached T (1)."
    progress_note: str | None
    # A grader returned marks that resume after a zero; the question is left out of agreement
    invalid_mark_pattern: bool
    agree: bool | None
    human_verdict: bool | None


@dataclass
class RunComparison:
    session_id: UUID
    llm_run_id: UUID | None
    scheme_run_id: UUID | None
    scheme_version: str | None
    questions: list[QuestionComparison]
    agreement_rate: float | None
    # Questions left out of agreement because a grader's mark pattern was invalid
    excluded_invalid_pattern: int
    llm_total: Decimal | None
    scheme_total: Decimal | None
    max_total: Decimal | None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _key(result: QuestionResult) -> _QuestionKey:
    # The LLM may return "(a)" where a scheme says "a"
    sub_part = result.sub_part.strip().strip("()").casefold() if result.sub_part else None
    return result.question_number.strip(), sub_part or None


def _index(results: list[QuestionResult]) -> dict[_QuestionKey, QuestionResult]:
    indexed: dict[_QuestionKey, QuestionResult] = {}
    for result in results:
        # If a run repeats a question, the first occurrence wins
        indexed.setdefault(_key(result), result)
    return indexed


def _total(values: list[Decimal | None]) -> Decimal | None:
    present = [value for value in values if value is not None]
    return sum(present, Decimal(0)) if present else None


def _progress(result: QuestionResult | None) -> int | None:
    if result is None or not result.mark_breakdown or result.invalid_mark_pattern:
        return None
    return mark_progress(breakdown_awards(result.mark_breakdown))


def _codes(result: QuestionResult | None) -> list[str] | None:
    return [item["code"] for item in result.mark_breakdown] if result and result.mark_breakdown else None


def _reached(grader: str, progress: int, codes: list[str]) -> str:
    """ "LLM reached T (1)", naming the last mark earned, or "LLM reached no mark (0)". """
    if progress == 0:
        return f"{grader} reached no mark (0)"
    label = mark_labels(codes)[progress - 1] or codes[progress - 1]
    return f"{grader} reached {label} ({progress})"


def _compare_question(
    llm: QuestionResult | None, scheme: QuestionResult | None
) -> QuestionComparison:
    # At least one side is always present
    primary = scheme or llm
    assert primary is not None

    llm_mark = _decimal(llm.mark_awarded) if llm else None
    scheme_mark = _decimal(scheme.mark_awarded) if scheme else None
    max_mark = _decimal(scheme.max_mark) if scheme else _decimal(llm.max_mark if llm else None)

    # Graders that marked the same codes are compared on how far each got before stopping;
    # otherwise, on the mark
    codes = _codes(scheme)
    by_progress = codes is not None and codes == _codes(llm)
    invalid = any(r is not None and bool(r.invalid_mark_pattern) for r in (llm, scheme))
    llm_progress, scheme_progress = _progress(llm), _progress(scheme)

    agree: bool | None
    note: str | None = None
    if invalid:
        agree = None
    elif by_progress and llm_progress is not None and scheme_progress is not None:
        assert codes is not None
        agree = llm_progress == scheme_progress
        if not agree:
            note = (
                f"{_reached('Mark scheme', scheme_progress, codes)}; "
                f"{_reached('LLM', llm_progress, codes)}."
            )
    elif llm_mark is None or scheme_mark is None:
        agree = None
    else:
        agree = llm_mark == scheme_mark

    verdicts = [
        r.is_correct_per_human for r in (scheme, llm) if r is not None and r.is_correct_per_human is not None
    ]

    return QuestionComparison(
        question_number=primary.question_number,
        sub_part=primary.sub_part,
        # The scheme run stores the answer text verbatim; fall back to the LLM's extraction
        extracted_answer=(scheme.extracted_answer if scheme else None)
        or (llm.extracted_answer if llm else None),
        llm_mark=llm_mark,
        scheme_mark=scheme_mark,
        max_mark=max_mark,
        llm_progress=llm_progress,
        scheme_progress=scheme_progress,
        progress_max=len(codes) if by_progress and codes else None,
        progress_note=note,
        invalid_mark_pattern=invalid,
        agree=agree,
        human_verdict=verdicts[0] if verdicts else None,
    )


async def compare_runs(
    session_id: UUID,
    owner_id: UUID,
    db: AsyncSession,
    llm_run_id: UUID | None = None,
    scheme_run_id: UUID | None = None,
) -> RunComparison:
    repo = QuestionResultRepository(db)
    runs = await repo.list_runs_for_session(session_id, owner_id)  # newest first

    def resolve(requested: UUID | None, grader_type: GraderType) -> tuple[UUID, str | None] | None:
        for run_id, run_type, scheme_version, _ in runs:
            if run_type != grader_type.value:
                continue
            if requested is None or requested == run_id:
                return run_id, scheme_version
        if requested is not None:
            raise RunNotFoundError(
                f"No {grader_type.value} run {requested} found for session {session_id}"
            )
        return None

    llm_run = resolve(llm_run_id, GraderType.LLM)
    scheme_run = resolve(scheme_run_id, GraderType.MARK_SCHEME)

    llm_results = _index(await repo.list_for_run(llm_run[0], owner_id)) if llm_run else {}
    scheme_results = _index(await repo.list_for_run(scheme_run[0], owner_id)) if scheme_run else {}

    keys = sorted(
        llm_results.keys() | scheme_results.keys(), key=lambda k: question_sort_key(k[0], k[1])
    )
    questions = [_compare_question(llm_results.get(k), scheme_results.get(k)) for k in keys]

    comparable = [q.agree for q in questions if q.agree is not None]

    return RunComparison(
        session_id=session_id,
        llm_run_id=llm_run[0] if llm_run else None,
        scheme_run_id=scheme_run[0] if scheme_run else None,
        scheme_version=scheme_run[1] if scheme_run else None,
        questions=questions,
        agreement_rate=sum(comparable) / len(comparable) if comparable else None,
        excluded_invalid_pattern=sum(q.invalid_mark_pattern for q in questions),
        llm_total=_total([q.llm_mark for q in questions]),
        scheme_total=_total([q.scheme_mark for q in questions]),
        max_total=_total([q.max_mark for q in questions]),
    )
