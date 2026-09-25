from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.services.grading.schemes import SchemeMark


@dataclass
class MarkAward:
    mark_id: str
    awarded: Decimal
    reason: str


class Procedure(ABC):
    """Contract for procedures that mark a question's working step by step.

    Given the student's working lines for one question, in order, a procedure
    returns one MarkAward per scheme mark point, each with a reason naming the
    line that earned or lost it.
    """

    name: str

    @abstractmethod
    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        ...
