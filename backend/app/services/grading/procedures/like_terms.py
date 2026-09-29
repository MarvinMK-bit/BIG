"""Collecting like terms in a linear expression, marked line by line.

Marking model
-------------
The scheme carries no fixed expression, so it marks ANY linear expression in one unknown. The
student's first line is read as the expression: any single variable letter, terms that may be
negative, fractional, implicit ("x") or bracketed ("2(x + 1)"). A line with no equals sign is
the expression itself; a first line written "3x + 3x = 6x" gives the expression before the
first equals sign and the working after it.

There is no M. Collecting like terms is a one-step simplification: nothing lies between reading
the expression and stating the result, so there is no intermediate working to reward. A student
may still write working, e.g. "(3 + 3)x", and each such step must be correct, but it earns
nothing.

Every step after the expression, on line 1 after "=" or on the lines that follow, is checked
in order. Algebra is compared with sympy, never as strings: a step is correct when it equals the
expression for every value of the unknown.

Mark points use BIG's mark codes (docs/MARK-CODES.md), declared by code alone. Each is
earned on its own line, and reads "T - 1" when earned and "T - 0" when not:
  T  line 1: the expression identified, a linear expression in one unknown, its terms
     extracted.
  A  the simplified result: the first step that equals the expression and is fully collected,
     with every step before it verified. Fully collected means at most one term in the
     unknown and at most one constant, each a plain number times the unknown or a plain
     number, with no zero terms left in: "6x", or "6x + 2" where a constant remains. "3x + 3x"
     stated as "3x + 3x" is not an answer.
  D  a concluding statement on a line after the answer. Checked by pattern, not by a model:
     the line must contain the simplified result, fully collected, and one of
     CONCLUDING_WORDS, shared with the other procedures. Awarded only when A was earned.

Marking STOPS at the first incorrect step. Every mark from that point on is
zero, including marks that would otherwise follow from the student's own
working. This is deliberate, and stricter than UNEB follow-through marking,
which would credit later working done correctly from an earlier slip. A
correct final answer reached through incorrect working earns nothing. Lines
after the answer must each be a correct step or the conclusion.

Reading conventions: a label ending in ":" at the start of a line ("Simplify:") is ignored, as
is a leading "simplify", "answer" or concluding word; decimals are accepted when correctly
rounded to the places written; a line starting with "=" continues the working.
"""

import re
import string
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import sympy

from app.services.grading.procedures.base import MarkAward, Procedure, marks_of
from app.services.grading.procedures.common import (
    CLAUSE_SPLIT_RE,
    CONCLUDING_RE,
    CONCLUDING_WORDS,
    PLAIN_NUMBER_RE,
    PROSE_RE,
    REPLACEMENTS,
    STOP_NOTE,
    equal,
    parse_arithmetic,
    rounding_tolerance,
    terms_of,
)
from app.services.grading.procedures.registry import register
from app.services.grading.schemes import (
    ANSWER_CODE,
    CONCLUSION_CODE,
    FIRST_STEP_CODE,
    SchemeMark,
    check_mark_codes,
)

_LABEL_RE = re.compile(
    r"^\s*(?:(?:simplify|collect|answer|ans|result|therefore|hence|thus|so|the|is)\b\s*)+",
    re.IGNORECASE,
)
_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])")
_ALL_LETTERS = set(string.ascii_letters)
# A number that multiplies the unknown: "6", "0.5", "1/2", "(1/2)"
_COEFFICIENT = r"(?:\d+(?:\.\d+)?|\d+/\d+|\(\d+/\d+\))"


class _StepError(Exception):
    """The line is not a legitimate step; the message says why."""


@dataclass
class _Expression:
    variable: sympy.Symbol
    value: sympy.Expr
    terms: list[str]


def _normalise(line: str) -> str:
    text = line
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = text.rsplit(":", 1)[-1]
    text = _LABEL_RE.sub("", text)
    text = text.replace("*", " * ")
    return " ".join(text.split()).rstrip(".").strip()


def _read_expression(line: str) -> tuple[_Expression, list[str]]:
    """The expression on line 1, and any steps written after it on the same line."""
    segments = [segment.strip() for segment in _normalise(line).split("=")]
    text = segments[0]
    if not text:
        raise _StepError("has no expression before its equals sign")
    letters = {letter for letter in _LETTER_RE.findall(text)}
    if not letters:
        raise _StepError("has no unknown: it is not an algebraic expression")
    if len(letters) > 1:
        raise _StepError(
            f"uses {', '.join(sorted(letters))}: collecting like terms here takes one unknown"
        )
    expr = parse_arithmetic(text, _ALL_LETTERS)
    if expr is None:
        raise _StepError(f"'{text}' could not be read as mathematics")
    (letter,) = letters
    variable = sympy.Symbol(letter)
    value = sympy.expand(expr)
    try:
        degree = sympy.Poly(value, variable).degree() if value.free_symbols else 0
    except sympy.PolynomialError:
        raise _StepError(f"'{text}' is not a linear expression") from None
    if value.free_symbols - {variable} or degree > 1:
        raise _StepError(f"'{text}' is not a linear expression")
    return _Expression(variable=variable, value=value, terms=terms_of(text)), segments[1:]


def _check_step(text: str, expression: _Expression) -> None:
    """Raises _StepError unless the step equals the expression for every value of the unknown."""
    if not text:
        raise _StepError("has nothing on one side of an equals sign")
    expr = parse_arithmetic(text, {expression.variable.name})
    if expr is None or expr.free_symbols - {expression.variable}:
        raise _StepError(f"'{text}' could not be read as mathematics")
    difference = sympy.expand(expr - expression.value)
    within = rounding_tolerance(text)
    try:
        polynomial = sympy.Poly(difference, expression.variable)
    except sympy.PolynomialError:
        raise _StepError(f"'{text}' does not equal the expression on line 1") from None
    if not all(equal(coefficient, 0, within) for coefficient in polynomial.all_coeffs()):
        raise _StepError(f"'{text}' does not equal the expression on line 1")


def _collection_problem(text: str, expression: _Expression) -> str | None:
    """Why a correct step isn't fully collected, or None when it is."""
    unknown = re.escape(expression.variable.name)
    unknown_term = re.compile(
        rf"^{_COEFFICIENT}?\*?{unknown}$|^{unknown}/\d+$|^\d+{unknown}/\d+$"
    )
    in_unknown = 0
    constants = 0
    for term in terms_of(text):
        bare = term.lstrip("+-")
        if PLAIN_NUMBER_RE.match(bare):
            constants += 1
        elif unknown_term.match(bare):
            in_unknown += 1
        else:
            return f"leaves '{term}' uncollected"
        value = parse_arithmetic(bare, {expression.variable.name})
        if value is not None and value.is_zero and len(terms_of(text)) > 1:
            return f"keeps the zero term '{term}'"
    if in_unknown > 1:
        return f"has {in_unknown} terms in {expression.variable} still to collect"
    if constants > 1:
        return f"has {constants} constants still to collect"
    return None


_NO_CONCLUDING_WORD = "has no concluding word"


def _conclusion_problem(line: str, expression: _Expression) -> str | None:
    """Why the line isn't a concluding statement, or None when it is: it must hold a concluding
    word and the simplified result, fully collected."""
    if not CONCLUDING_RE.search(line.replace("∴", " therefore ")):
        return _NO_CONCLUDING_WORD
    # Prose is dropped; what's left is read clause by clause
    text = PROSE_RE.sub(";", _normalise(line))
    for clause in CLAUSE_SPLIT_RE.split(text):
        for segment in clause.split("="):
            segment = segment.strip()
            try:
                _check_step(segment, expression)
            except _StepError:
                continue
            if _collection_problem(segment, expression) is None:
                return None
    return "does not give the simplified result"


# A mark's (earned, reason, the 1-based number of the line its reason names, if any)
_Outcome = tuple[bool, str, int | None]


@register
class LikeTermsProcedure(Procedure):
    """Marks the collection of like terms in any linear expression; see the module docstring."""

    name = "like_terms"
    # A one-step simplification: nothing to reward between the expression and its result
    step_marks = (0, 0)

    def default_marks(self) -> list[SchemeMark]:
        return marks_of(FIRST_STEP_CODE, ANSWER_CODE, CONCLUSION_CODE)

    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        if params:
            raise ValueError(f"like_terms procedure has no parameter(s) {', '.join(sorted(params))}")
        # None declared: the procedure's own
        marks = marks or self.default_marks()
        codes = [mark.id for mark in marks]
        check_mark_codes(codes, "like_terms procedure scheme", self.step_marks)
        lines = [line.strip() for line in working if line.strip()]
        outcomes = self._mark(lines, codes)
        return [
            MarkAward(
                mark_id=mark.id,
                awarded=mark.max_mark if earned else Decimal(0),
                reason=reason,
                line_index=None if line is None else line - 1,
            )
            for mark, (earned, reason, line) in zip(marks, outcomes)
        ]

    @staticmethod
    def _mark(lines: list[str], codes: list[str]) -> list[_Outcome]:
        """Each mark's (earned, reason, line), in the scheme's order."""
        outcomes: list[_Outcome | None] = [None] * len(codes)

        def unfilled(code: str | None = None) -> list[int]:
            return [
                i for i, c in enumerate(codes) if outcomes[i] is None and (code is None or c == code)
            ]

        def fill(code: str | None, outcome: _Outcome) -> None:
            for i in unfilled(code):
                outcomes[i] = outcome

        def result() -> list[_Outcome]:
            assert all(outcome is not None for outcome in outcomes)
            return [outcome for outcome in outcomes if outcome is not None]

        if not lines:
            fill(None, (False, "Not awarded: no working written.", None))
            return result()

        def at(number: int) -> str:
            return f"Line {number} '{lines[number - 1]}'"

        def quoted(number: int, step: str) -> str:
            """The step quoted, unless it is the whole line, which reasons quote already."""
            whole = _normalise(lines[number - 1]).removeprefix("=").strip()
            return "" if step == whole else f"'{step}' "

        def stopped(number: int, why: str) -> list[_Outcome]:
            # Errors quote the text they are about; don't quote a whole line twice
            why = why.removeprefix(f"'{_normalise(lines[number - 1]).removeprefix('=').strip()}' ")
            answer_lost = bool(unfilled(ANSWER_CODE))
            # The first mark still open is the one this line would have earned
            outcomes[unfilled()[0]] = (False, f"{at(number)} {why}. {STOP_NOTE}", number)
            later = f"Not awarded: marking stopped at line {number} '{lines[number - 1]}' ({why})."
            fill(None, (False, f"{later} {STOP_NOTE}", number))
            # Line 1 failing leaves no expression to check an answer against
            if answer_lost and number > 1 and later_answer_is_correct(number):
                for i in [i for i, c in enumerate(codes) if c == ANSWER_CODE]:
                    earned, reason, line = outcomes[i] or (False, "", number)
                    outcomes[i] = (
                        earned,
                        f"{reason} A later line states the simplified result, but a correct "
                        "answer reached through incorrect working earns nothing.",
                        line,
                    )
            return result()

        def steps_of(number: int) -> list[str]:
            """The steps written on a line after line 1: each side of each equals sign."""
            text = _normalise(lines[number - 1]).removeprefix("=").strip()
            return [segment.strip() for segment in text.split("=")]

        def later_answer_is_correct(number: int) -> bool:
            for later in range(number + 1, len(lines) + 1):
                for step in steps_of(later):
                    try:
                        _check_step(step, expression)
                    except _StepError:
                        continue
                    if _collection_problem(step, expression) is None:
                        return True
            return False

        try:
            expression, first_steps = _read_expression(lines[0])
        except _StepError as error:
            return stopped(1, str(error))
        fill(
            FIRST_STEP_CODE,
            (
                True,
                f"{at(1)}: expression in {expression.variable} identified, "
                f"terms {', '.join(expression.terms)}.",
                1,
            ),
        )

        # Steps in order, each with its line, until the first that is fully collected
        answer: tuple[int, str] | None = None
        last_problem = "does not state the result"
        for number in range(1, len(lines) + 1):
            steps = first_steps if number == 1 else steps_of(number)
            for step in steps:
                try:
                    _check_step(step, expression)
                except _StepError as error:
                    return stopped(number, str(error))
                if answer is None:
                    problem = _collection_problem(step, expression)
                    if problem is None:
                        answer = (number, step)
                    else:
                        last_problem = f"{quoted(number, step)}{problem}"
            if answer is not None:
                break

        if answer is None:
            fill(
                ANSWER_CODE,
                (
                    False,
                    f"Not awarded: every step is correct, but no step states the result fully "
                    f"collected: {at(len(lines))} {last_problem}.",
                    len(lines),
                ),
            )
            fill(
                CONCLUSION_CODE,
                (
                    False,
                    "Not awarded: a concluding statement counts only once the simplified result "
                    "is stated.",
                    None,
                ),
            )
            return result()

        answer_line, stated = answer
        fill(
            ANSWER_CODE,
            (True, f"{at(answer_line)}: {stated} stated, fully collected, every step verified.", answer_line),
        )

        if not unfilled(CONCLUSION_CODE):
            return result()
        # After the answer, each line is either the conclusion or another correct step
        for number in range(answer_line + 1, len(lines) + 1):
            problem = _conclusion_problem(lines[number - 1], expression)
            if problem is None:
                fill(
                    CONCLUSION_CODE,
                    (True, f"{at(number)}: concluding statement giving the simplified result.", number),
                )
                return result()
            if problem != _NO_CONCLUDING_WORD:
                return stopped(number, problem)
            for step in steps_of(number):
                try:
                    _check_step(step, expression)
                except _StepError as error:
                    return stopped(number, str(error))
        words = ", ".join(f"'{word}'" for word in CONCLUDING_WORDS)
        fill(
            CONCLUSION_CODE,
            (
                False,
                f"Not awarded: no concluding statement after the answer on line {answer_line}. "
                f"It must give the simplified result with a concluding word ({words}).",
                answer_line,
            ),
        )
        return result()
