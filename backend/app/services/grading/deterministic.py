from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_session import GradingSession
from app.models.question_result import GraderType, QuestionResult
from app.services.grading.matchers import MATCHERS
from app.services.grading.errors import NoQuestionMarkersError
from app.services.grading.procedures import get_procedure
from app.services.grading.parser import (
    ParsedAnswer,
    has_question_markers,
    parse_answers,
    parse_lines_as_questions,
)
from app.services.grading.schemes import PROCEDURE_MATCHER, MarkScheme, SchemeQuestion

_QuestionKey = tuple[str, str | None]


def _key(number: str, sub_part: str | None) -> _QuestionKey:
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


def _grade_procedure(question: SchemeQuestion, parsed: ParsedAnswer) -> tuple[Decimal, str]:
    label = _label(question)
    if question.procedure is None:
        raise ValueError(f"Question {label} uses the procedure matcher but names no procedure")
    try:
        procedure = get_procedure(question.procedure)
    except ValueError as exc:
        raise ValueError(f"Question {label}: {exc}") from None

    working = [line.strip() for line in parsed.working.splitlines() if line.strip()]
    awards = procedure.grade(working, question.params, question.marks)
    max_by_id = {mark.id: mark.max_mark for mark in question.marks}
    mark = sum((award.awarded for award in awards), Decimal(0))
    outcomes = "\n".join(
        f"{award.mark_id} {award.awarded}/{max_by_id[award.mark_id]}: {award.reason}"
        for award in awards
    )
    return mark, f"Marked by the {procedure.name} procedure.\n{outcomes}"


def _grade_question(
    question: SchemeQuestion, parsed: ParsedAnswer | None
) -> tuple[Decimal, str]:
    label = _label(question)
    if parsed is None:
        return Decimal(0), f"No answer found for question {label}."
    if question.matcher == PROCEDURE_MATCHER:
        if not parsed.working:
            return Decimal(0), f"Question {label} has no working written."
        return _grade_procedure(question, parsed)
    if not parsed.raw_answer:
        return Decimal(0), f"Question {label} has no answer written."

    matcher = MATCHERS.get(question.matcher)
    if matcher is None:
        raise ValueError(f"Question {label} has unknown matcher {question.matcher!r}")

    if matcher(_expected_for(question), parsed.raw_answer):
        return question.max_mark, f"Correct: answered {parsed.raw_answer!r} ({question.matcher} match)."
    return (
        Decimal(0),
        f"Incorrect: answered {parsed.raw_answer!r}, expected {question.answer} "
        f"({question.matcher} match).",
    )


async def grade_with_scheme(
    session: GradingSession,
    scheme: MarkScheme,
    db: AsyncSession,
    grading_run_id: UUID,
    unnumbered_mode: bool = False,
) -> list[QuestionResult]:
    if session.ocr_markdown is None:
        raise ValueError(f"Grading session {session.id} has no OCR text to grade")

    if has_question_markers(session.ocr_markdown):
        answers = parse_answers(session.ocr_markdown)
    elif unnumbered_mode:
        answers = parse_lines_as_questions(session.ocr_markdown)
    else:
        raise NoQuestionMarkersError()

    parsed_by_key: dict[_QuestionKey, ParsedAnswer] = {}
    for parsed in answers:
        # If the student's paper repeats a question number, the first occurrence wins
        parsed_by_key.setdefault(_key(parsed.number, parsed.sub_part), parsed)

    results: list[QuestionResult] = []
    for question in scheme.questions:
        parsed = parsed_by_key.get(_key(question.number, question.sub_part))
        mark, reasoning = _grade_question(question, parsed)
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
            )
        )

    db.add_all(results)
    await db.flush()
    return results
