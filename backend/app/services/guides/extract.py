from decimal import Decimal

from app.services.grading.parser import (
    ParsedAnswer,
    has_question_markers,
    parse_answers,
    parse_lines_as_questions,
)
from app.services.guides.rows import GuideRow, default_matcher

DEFAULT_MARKS = Decimal(1)


def _stated_answer(text: str) -> str:
    """The guide's answer: whatever follows the last "=", so "7 × 8 = 56" gives "56"."""
    _, _, after = text.rpartition("=")
    return after.strip()


def _expression_lines(markdown: str) -> list[ParsedAnswer]:
    """One question per line, numbered from 1.

    Markdown headings are dropped. If any line is an expression ("... = ..."), only those
    lines count, so titles and instructions on the guide don't become questions.
    """
    lines = [
        p for p in parse_lines_as_questions(markdown) if not p.raw_answer.lstrip().startswith("#")
    ]
    expressions = [p for p in lines if "=" in p.raw_answer]
    kept = expressions or lines
    return [
        ParsedAnswer(number=str(i), sub_part=None, raw_answer=p.raw_answer, working=p.working)
        for i, p in enumerate(kept, start=1)
    ]


def extract_questions_from_guide(markdown: str) -> list[GuideRow]:
    """Turn a guide's OCR text into review rows.

    Uses question markers where the guide has them, otherwise one question per expression
    line. Every row gets 1 mark and a matcher guessed from its answer; the admin fixes both
    in the DOCX review.
    """
    parsed = parse_answers(markdown) if has_question_markers(markdown) else _expression_lines(markdown)
    rows: list[GuideRow] = []
    for p in parsed:
        answer = _stated_answer(p.raw_answer)
        rows.append(
            GuideRow(
                question=p.number,
                sub_part=p.sub_part,
                answer=answer,
                marks=DEFAULT_MARKS,
                matcher=default_matcher(answer),
            )
        )
    return rows
