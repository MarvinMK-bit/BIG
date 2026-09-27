from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_session import GradingSession
from app.models.question_result import GraderType, MarkBreakdownItem, QuestionResult
from app.services.grading.matchers import MATCHERS
from app.services.grading.errors import NoQuestionMarkersError
from app.services.grading.procedures import get_procedure
from app.services.grading.progress import awards_of, is_valid_prefix
from app.services.grading.parser import (
    ParsedAnswer,
    has_question_markers,
    parse_answers,
    parse_lines_as_questions,
)
from app.services.grading.schemes import (
    PROCEDURE_MATCHER,
    MarkScheme,
    SchemeQuestion,
    format_award,
    mark_labels,
)

QuestionKey = tuple[str, str | None]


def question_key(number: str, sub_part: str | None) -> QuestionKey:
    """Normalised (number, sub_part), so "3", "(a)" and "3", "A" match."""
    if sub_part is None:
        return number.strip(), None
    return number.strip(), sub_part.strip().strip("()").casefold()


def _label(question: SchemeQuestion) -> str:
    if question.sub_part is None:
        return question.number
    return f"{question.number}({question.sub_part.strip('()')})"


def _expected_for(question: SchemeQuestion) -> str | Decimal:
    if question.matcher == "numeric":
        return Decimal(str(question.answer))
    return str(question.answer)


def _grade_procedure(
    question: SchemeQuestion, parsed: ParsedAnswer
) -> tuple[Decimal, str, list[MarkBreakdownItem]]:
    label = _label(question)
    if question.procedure is None:
        raise ValueError(f"Question {label} uses the procedure matcher but names no procedure")
    try:
        procedure = get_procedure(question.procedure)
    except ValueError as exc:
        raise ValueError(f"Question {label}: {exc}") from None

    working = [line.strip() for line in parsed.working.splitlines() if line.strip()]
    awards = procedure.grade(working, question.params, question.marks)
    if [award.mark_id for award in awards] != [mark.id for mark in question.marks]:
        raise ValueError(f"Question {label}: the {procedure.name} procedure did not award the scheme's marks")
    # Matched by position: M can appear more than once
    pairs = list(zip(question.marks, awards))
    pattern = awards_of((award.awarded, scheme_mark.max_mark) for scheme_mark, award in pairs)
    if not is_valid_prefix(pattern):
        # A bug in the procedure, not a marking outcome: every procedure stops at the first wrong step
        raise AssertionError(
            f"Question {label}: the {procedure.name} procedure awarded "
            f"{''.join(map(str, pattern))}, which resumes after a zero"
        )
    mark = sum((award.awarded for award in awards), Decimal(0))
    labels = mark_labels([award.mark_id for award in awards])
    outcomes = "\n".join(
        f"{format_award(award.mark_id, award.awarded)}{f' ({label})' if label else ''}: {award.reason}"
        for award, label in zip(awards, labels)
    )
    breakdown: list[MarkBreakdownItem] = [
        {
            "code": award.mark_id,
            "awarded": float(award.awarded),
            "max_mark": float(scheme_mark.max_mark),
            "reason": award.reason,
        }
        for scheme_mark, award in pairs
    ]
    return mark, f"Marked by the {procedure.name} procedure.\n{outcomes}", breakdown


def _unearned(question: SchemeQuestion, reason: str) -> list[MarkBreakdownItem]:
    return [
        {"code": mark.id, "awarded": 0.0, "max_mark": float(mark.max_mark), "reason": reason}
        for mark in question.marks
    ]


def _grade_question(
    question: SchemeQuestion, parsed: ParsedAnswer | None
) -> tuple[Decimal, str, list[MarkBreakdownItem] | None]:
    """The mark, the reasoning, and for procedure questions the outcome of each mark point."""
    label = _label(question)
    procedure = question.matcher == PROCEDURE_MATCHER
    if parsed is None:
        reason = f"No answer found for question {label}."
        return Decimal(0), reason, _unearned(question, reason) if procedure else None
    if procedure:
        if not parsed.working:
            reason = f"Question {label} has no working written."
            return Decimal(0), reason, _unearned(question, reason)
        return _grade_procedure(question, parsed)
    if not parsed.raw_answer:
        return Decimal(0), f"Question {label} has no answer written.", None

    matcher = MATCHERS.get(question.matcher)
    if matcher is None:
        raise ValueError(f"Question {label} has unknown matcher {question.matcher!r}")

    if matcher(_expected_for(question), parsed.raw_answer):
        return (
            question.max_mark,
            f"Correct: answered {parsed.raw_answer!r} ({question.matcher} match).",
            None,
        )
    return (
        Decimal(0),
        f"Incorrect: answered {parsed.raw_answer!r}, expected {question.answer} "
        f"({question.matcher} match).",
        None,
    )


async def grade_with_scheme(
    session: GradingSession,
    scheme: MarkScheme,
    db: AsyncSession,
    grading_run_id: UUID,
    unnumbered_mode: bool = False,
    is_test_run: bool = False,
) -> list[QuestionResult]:
    """Grade the session's OCR text against the scheme and store one result per scheme question.

    is_test_run marks the results as an admin's trial of a scheme under review, which keeps
    them out of accuracy figures; see QuestionResult.is_test_run.
    """
    if session.ocr_markdown is None:
        raise ValueError(f"Grading session {session.id} has no OCR text to grade")

    if has_question_markers(session.ocr_markdown):
        answers = parse_answers(session.ocr_markdown)
    elif unnumbered_mode:
        answers = parse_lines_as_questions(session.ocr_markdown)
    else:
        raise NoQuestionMarkersError()

    parsed_by_key: dict[QuestionKey, ParsedAnswer] = {}
    for parsed in answers:
        # If the student's paper repeats a question number, the first occurrence wins
        parsed_by_key.setdefault(question_key(parsed.number, parsed.sub_part), parsed)

    results: list[QuestionResult] = []
    for question in scheme.questions:
        parsed = parsed_by_key.get(question_key(question.number, question.sub_part))
        mark, reasoning, breakdown = _grade_question(question, parsed)
        results.append(
            QuestionResult(
                owner_id=session.owner_id,
                grading_run_id=grading_run_id,
                session_id=session.id,
                question_number=question.number,
                sub_part=question.sub_part,
                extracted_answer=parsed.raw_answer if parsed is not None else None,
                mark_awarded=mark,
                max_mark=question.max_mark,
                grader_type=GraderType.MARK_SCHEME,
                mark_scheme_version=scheme.scheme_version,
                confidence=1.0,
                ocr_confidence=session.ocr_confidence,
                reasoning=reasoning,
                mark_breakdown=breakdown,
                # _grade_procedure raises rather than return an invalid pattern
                invalid_mark_pattern=False if breakdown is not None else None,
                is_test_run=True if is_test_run else None,
            )
        )

    db.add_all(results)
    await db.flush()
    return results
