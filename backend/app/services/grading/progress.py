"""The prefix rule for coded marks. See "The prefix rule" in docs/MARK-CODES.md.

Marking stops at the first wrong step, so a question's awards in code order are a run of 1s
followed by a run of 0s: 1111, 1110, 1100, 1000 and 0000 are valid; 1101 and 1011 are not.
"""

from collections.abc import Iterable
from decimal import Decimal

from app.models.question_result import MarkBreakdownItem


def mark_progress(awards: list[int]) -> int | None:
    """How many marks were earned before the first zero, or None if the pattern is not a valid
    prefix, i.e. a mark is earned after one that was not."""
    progress = 0
    while progress < len(awards) and awards[progress]:
        progress += 1
    if any(awards[progress:]):
        return None
    return progress


def is_valid_prefix(awards: list[int]) -> bool:
    return mark_progress(awards) is not None


def awards_of(marks: Iterable[tuple[Decimal | float, Decimal | float]]) -> list[int]:
    """1 or 0 per mark from (awarded, max_mark) pairs: a mark is earned when it got its full value."""
    return [1 if awarded >= max_mark else 0 for awarded, max_mark in marks]


def breakdown_awards(breakdown: list[MarkBreakdownItem]) -> list[int]:
    return awards_of((item["awarded"], item["max_mark"]) for item in breakdown)
