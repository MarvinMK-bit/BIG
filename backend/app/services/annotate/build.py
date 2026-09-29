"""A grading run's results, as the marks to draw on its script."""

from datetime import UTC, datetime

from app.models.question_result import QuestionResult
from app.services.annotate.renderer import MarkAnnotation, QuestionAnnotation, ScriptAnnotations
from app.services.grading.deterministic import QuestionKey, question_key
from app.services.grading.parser import (
    ParsedAnswer,
    has_question_markers,
    is_answer_line,
    parse_answers,
    parse_lines_as_questions,
)
from app.services.grading.schemes import ANSWER_CODE


def _answers_by_key(markdown: str) -> dict[QuestionKey, ParsedAnswer]:
    # Parsed as the scheme grader parses it; an unnumbered script was graded line by line
    answers = parse_answers(markdown) if has_question_markers(markdown) else parse_lines_as_questions(markdown)
    by_key: dict[QuestionKey, ParsedAnswer] = {}
    for parsed in answers:
        # The first occurrence wins, as it does in grading
        by_key.setdefault(question_key(parsed.number, parsed.sub_part), parsed)
    return by_key


def _answer_line(parsed: ParsedAnswer | None, markdown_lines: list[str]) -> int | None:
    """The line the question's answer is on: its "Answer:" line, else its last line of working,
    else its marker."""
    if parsed is None:
        return None
    for index in parsed.working_line_indices:
        if is_answer_line(markdown_lines[index]):
            return index
    if parsed.working_line_indices:
        return parsed.working_line_indices[-1]
    return parsed.source_line_index


def _label(result: QuestionResult) -> str:
    if result.sub_part is None:
        return result.question_number
    return f"{result.question_number}({result.sub_part.strip('()')})"


def annotations_for_run(results: list[QuestionResult], ocr_markdown: str) -> ScriptAnnotations:
    """One question annotation per result, in the order given.

    A procedure question's marks are its mark points, each at the line its breakdown names.
    Any other question, and LLM mark points that name no line, sit at the question's answer."""
    by_key = _answers_by_key(ocr_markdown)
    markdown_lines = ocr_markdown.splitlines()
    questions: list[QuestionAnnotation] = []
    for result in results:
        parsed = by_key.get(question_key(result.question_number, result.sub_part))
        anchor = _answer_line(parsed, markdown_lines)
        awarded = float(result.mark_awarded or 0)
        max_mark = float(result.max_mark)
        if result.mark_breakdown:
            marks = [
                MarkAnnotation(
                    code=item["code"],
                    awarded=item["awarded"],
                    max_mark=item["max_mark"],
                    line_index=item.get("line_index"),
                )
                for item in result.mark_breakdown
            ]
        else:
            # An answer-only question: one A for the whole of it
            marks = [MarkAnnotation(code=ANSWER_CODE, awarded=awarded, max_mark=max_mark, line_index=anchor)]
        questions.append(
            QuestionAnnotation(
                label=_label(result), mark_awarded=awarded, max_mark=max_mark, marks=marks, line_index=anchor
            )
        )

    created = [result.created_at for result in results if result.created_at is not None]
    marked_on = (min(created) if created else datetime.now(UTC)).date()
    scheme_version = next((r.mark_scheme_version for r in results if r.mark_scheme_version), None)
    return ScriptAnnotations(
        questions=questions, ocr_markdown=ocr_markdown, marked_on=marked_on, scheme_version=scheme_version
    )
