from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.services.grading.schemes import SchemeMark


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
    """

    name: str

    @abstractmethod
    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        ...
