from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.services.grading.schemes import MARK_CODE_MEANINGS, MAX_STEP_MARKS, SchemeMark


@dataclass
class MarkAward:
    # The mark's code, e.g. "M"; what it earned is `awarded`, never part of the code
    mark_id: str
    awarded: Decimal
    reason: str


class Procedure(ABC):
    """Contract for procedures that mark a question's working step by step.

    Given the student's working lines for one question, in order, a procedure
    returns one MarkAward per scheme mark point, in the scheme's order, each with
    a reason naming the line that earned or lost it. Mark ids are BIG's mark codes
    (T, M, A, D), and M may repeat, so awards match marks by position.

    A question may declare no marks. grade() is then passed an empty list and awards
    its default_marks() instead, and the question is worth as many marks as it returns.
    """

    name: str
    # How many M marks a scheme may declare for this procedure, fewest and most
    step_marks: tuple[int, int] = (1, MAX_STEP_MARKS)

    @abstractmethod
    def default_marks(self) -> list[SchemeMark]:
        """The marks grade() awards when it is passed none, one mark each."""
        ...

    @abstractmethod
    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        ...


def marks_of(*codes: str) -> list[SchemeMark]:
    """Marks worth one each, for a procedure's default_marks, described in words that give away
    nothing about any particular question."""
    return [SchemeMark(id=code, description=MARK_CODE_MEANINGS[code]) for code in codes]
