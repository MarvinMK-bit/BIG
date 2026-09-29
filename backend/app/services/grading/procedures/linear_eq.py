"""Linear equations in one unknown, marked line by line.

Marking model
-------------
The scheme carries no fixed equation, so it marks ANY linear equation in one unknown, e.g.
"2x + 3 = 11". The student's first line is read as the equation: a single equals sign, any
single variable letter, on either or both sides, with terms that may be negative, fractional,
implicit ("x") or bracketed ("2(x + 1) = 10"). It must have exactly one solution, so an
identity ("2x = 2x") or a contradiction ("x + 1 = x") is not an equation to solve.

Every line after the first is checked, in order, as a legitimate step. Algebra is compared
with sympy, never as strings. A line is a chain of sides joined by equals signs, and each
neighbouring pair must be true: two sides without the unknown must be equal arithmetic
("11 - 3 = 8"), and two sides with it must form an equation with the same solution as line 1
("2x = 8", "x = 8/2"). A line stating only arithmetic, or the equation of line 1 again, is
correct but is not a step; nor is working out the arithmetic on one side alone, since both
sides then read the same as line 1's ("3x = 2 + 1" to "3x = 3").

Mark points use BIG's mark codes (docs/MARK-CODES.md), declared by code alone. Each is
earned on its own line, and reads "T - 1" when earned and "T - 0" when not:
  T  line 1: the equation identified, a linear equation in one unknown, its coefficients
     extracted by collecting it to the form ax = c.
  M  a correct rearrangement step: a line holding an equation with the same solution as line
     1, other than line 1's own equation and before the answer, e.g. "2x = 8". A scheme may
     declare up to four; each is earned by the next rearrangement line. Rearrangement lines
     beyond the scheme's M marks must still be correct, but earn nothing. A linear equation
     needs STEPS_NEEDED step, so an M beyond the first that no line earned is awarded with a
     correct answer, and its reason says the scheme declares more steps than this question
     type needs. The answer stated with no rearrangement before it loses the first M, and by
     the prefix rule every mark after it (docs/MARK-CODES.md).
  A  the value stated: the first line reading "x = value" whose value is a plain number,
     equal to the solution, with every line before it verified. A fraction must be in its
     lowest terms, "4" not "8/2"; decimals are accepted when correctly rounded to the places
     written.
  D  a concluding statement on a line after the answer, e.g. "therefore x = 4". Checked by
     pattern, not by a model: the line must contain the solution's value and one of
     CONCLUDING_WORDS, shared with the other procedures. Awarded only when A was earned.

Marking STOPS at the first incorrect step. Every mark from that point on is
zero, including marks that would otherwise follow from the student's own
working. This is deliberate, and stricter than UNEB follow-through marking,
which would credit later working done correctly from an earlier slip. A
correct final answer reached through incorrect working earns nothing. Lines
after the answer must each be a correct step or the conclusion.

Reading conventions: a label ending in ":" at the start of a line ("Solve:") is ignored, as is
a leading "solve", "answer" or concluding word; a line starting with "=" continues the last
side of the line before it.
"""

import math
import re
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
    show,
)
from app.services.grading.procedures.registry import register
from app.services.grading.schemes import (
    ANSWER_CODE,
    CONCLUSION_CODE,
    FIRST_STEP_CODE,
    STEP_CODE,
    SchemeMark,
    check_mark_codes,
)

# The one rearrangement between the equation and its value
STEPS_NEEDED = 1

_LABEL_RE = re.compile(
    r"^\s*(?:(?:solve|solution|answer|ans|therefore|hence|thus|so|the|value|is)\b\s*)+",
    re.IGNORECASE,
)
_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])")


class _StepError(Exception):
    """The line is not a legitimate step; the message says why."""


@dataclass
class _Equation:
    variable: sympy.Symbol
    # Line 1 collected to a·x = c
    a: sympy.Expr
    c: sympy.Expr
    # Line 1's two sides, expanded, so a repeat of the equation is recognised
    sides: tuple[sympy.Expr, sympy.Expr]

    @property
    def solution(self) -> sympy.Expr:
        return self.c / self.a


@dataclass
class _Line:
    # The line's text after normalising, with a leading "=" continued from the line before
    text: str
    # True when it holds an equation with line 1's solution that is not line 1's own equation
    rearranges: bool
    # The value written after "x =" when the line states the unknown's value, else None
    stated: str | None


def _normalise(line: str) -> str:
    text = line
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = text.rsplit(":", 1)[-1]
    text = _LABEL_RE.sub("", text)
    text = text.replace("*", " * ")
    return " ".join(text.split()).rstrip(".").strip()


def _read_equation(line: str) -> _Equation:
    text = _normalise(line)
    written = [side.strip() for side in text.split("=")]
    if len(written) != 2 or not all(written):
        raise _StepError("is not a single equation, with one expression either side of an equals sign")
    letters = set(_LETTER_RE.findall(text))
    if not letters:
        raise _StepError("has no unknown: it is not an equation to solve")
    if len(letters) > 1:
        raise _StepError(f"uses {', '.join(sorted(letters))}: a linear equation here takes one unknown")
    (letter,) = letters
    variable = sympy.Symbol(letter)
    read = [parse_arithmetic(side, {letter}) for side in written]
    lhs, rhs = read
    if lhs is None or rhs is None:
        raise _StepError(f"'{text}' could not be read as mathematics")
    difference = sympy.expand(lhs - rhs)
    try:
        polynomial = sympy.Poly(difference, variable)
    except sympy.PolynomialError:
        raise _StepError(f"'{text}' is not a linear equation") from None
    if polynomial.degree() > 1:
        raise _StepError(f"'{text}' is not a linear equation: it has degree {polynomial.degree()}")
    if polynomial.degree() < 1:
        if polynomial.is_zero:
            raise _StepError(f"'{text}' is true for every value of {letter}: it is not an equation to solve")
        raise _StepError(f"'{text}' has no solution: it is false for every value of {letter}")
    a, b = polynomial.all_coeffs()
    return _Equation(
        variable=variable, a=a, c=-b, sides=(sympy.expand(lhs), sympy.expand(rhs))
    )


def _times(coefficient: sympy.Expr, variable: sympy.Symbol) -> str:
    """"2x", "x", "-x", "(1/2)x": the coefficient as a student writes it."""
    if coefficient == 1:
        return variable.name
    if coefficient == -1:
        return f"-{variable.name}"
    shown = show(coefficient)
    return f"({shown}){variable.name}" if "/" in shown else f"{shown}{variable.name}"


def _is_simplified(text: str) -> bool:
    """A plain number, with any fraction in its lowest terms: "4", "-1/2", "0.5", not "8/2"."""
    compact = text.replace(" ", "")
    if not PLAIN_NUMBER_RE.match(compact):
        return False
    fraction = re.fullmatch(r"\(?[+-]?(\d+)/(\d+)\)?", compact)
    if fraction is None:
        return True
    numerator, denominator = int(fraction[1]), int(fraction[2])
    return denominator > 1 and math.gcd(numerator, denominator) == 1


def _read_line(line: str, equation: _Equation, previous_tail: str) -> _Line:
    """The line checked as a step: raises _StepError at the first pair of sides that is false."""
    text = _normalise(line)
    if text.startswith("=") and previous_tail:
        text = f"{previous_tail} {text}"
    variable = equation.variable
    segments = [segment.strip() for segment in text.split("=")]
    if len(segments) == 1:
        if variable.name in _LETTER_RE.findall(text):
            raise _StepError(f"'{text}' is an expression on its own, not a step")
        raise _StepError(
            f"'{text}' is a value on its own: state it as {variable} = .. or as part of an equation"
        )
    if not all(segments):
        raise _StepError(f"'{text}' has nothing on one side of an equals sign")

    exprs: list[sympy.Expr] = []
    for segment in segments:
        expr = parse_arithmetic(segment, {variable.name})
        if expr is None:
            raise _StepError(f"'{segment}' could not be read as mathematics in {variable}")
        exprs.append(expr)

    tolerance = rounding_tolerance(text)
    rearranges = False
    for i in range(1, len(exprs)):
        where = f"'{segments[i - 1]} = {segments[i]}'"
        difference = sympy.expand(exprs[i - 1] - exprs[i])
        if variable not in difference.free_symbols:
            # Arithmetic, or the same expression rewritten
            if not equal(difference, sympy.Integer(0), tolerance):
                raise _StepError(f"{where} is false")
            continue
        try:
            polynomial = sympy.Poly(difference, variable)
        except sympy.PolynomialError:
            raise _StepError(f"{where} is not a linear equation") from None
        if polynomial.degree() != 1:
            raise _StepError(f"{where} is not a linear equation: it has degree {polynomial.degree()}")
        slope, intercept = polynomial.all_coeffs()
        root = -intercept / slope
        if not equal(root, equation.solution, tolerance):
            raise _StepError(
                f"{where} does not have the solution of the equation: it gives {variable} = {show(root)}"
            )
        pair = {sympy.expand(exprs[i - 1]), sympy.expand(exprs[i])}
        if pair != set(equation.sides):
            rearranges = True

    stated = segments[-1] if exprs[0] == variable and variable not in exprs[-1].free_symbols else None
    return _Line(text=text, rearranges=rearranges, stated=stated)


def _answer_problem(line: _Line, equation: _Equation) -> str | None:
    """Why the line doesn't state the value, or None when it does."""
    variable = equation.variable
    if line.stated is None:
        return f"does not state the value as {variable} = .."
    if not _is_simplified(line.stated):
        return f"leaves {variable} = {line.stated} as an unsimplified value"
    return None


_NO_CONCLUDING_WORD = "has no concluding word"


def _conclusion_problem(line: str, equation: _Equation) -> str | None:
    """Why the line isn't a concluding statement, or None when it is: it must hold a
    concluding word and the solution's value."""
    if not CONCLUDING_RE.search(line.replace("∴", " therefore ")):
        return _NO_CONCLUDING_WORD
    # Prose is dropped; what's left is read clause by clause
    text = PROSE_RE.sub(";", _normalise(line))
    for clause in CLAUSE_SPLIT_RE.split(text):
        for segment in clause.split("="):
            segment = segment.strip()
            value = parse_arithmetic(segment, set()) if segment else None
            if value is not None and equal(value, equation.solution, rounding_tolerance(segment)):
                return None
    return f"does not give the value {equation.variable} = {show(equation.solution)}"


# A mark's (earned, reason, the 1-based number of the line its reason names, if any)
_Outcome = tuple[bool, str, int | None]


@register
class LinearEquationProcedure(Procedure):
    """Marks any linear equation in one unknown line by line; see the module docstring."""

    name = "linear_eq"

    def default_marks(self) -> list[SchemeMark]:
        return marks_of(FIRST_STEP_CODE, STEP_CODE, ANSWER_CODE, CONCLUSION_CODE)

    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        if params:
            raise ValueError(f"linear_eq procedure has no parameter(s) {', '.join(sorted(params))}")
        # None declared: the procedure's own
        marks = marks or self.default_marks()
        codes = [mark.id for mark in marks]
        check_mark_codes(codes, "linear_eq procedure scheme", self.step_marks)
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
        step_marks = [i for i, code in enumerate(codes) if code == STEP_CODE]
        # M marks beyond the step this question type needs
        surplus = set(step_marks[STEPS_NEEDED:])
        surplus_note = (
            f"The scheme declares {len(step_marks)} M marks, more steps than this question type "
            f"needs: a linear equation takes {STEPS_NEEDED} rearrangement step, so this M stands "
            "for no step of the working."
        )

        def unfilled(code: str | None = None) -> list[int]:
            return [
                i for i, c in enumerate(codes) if outcomes[i] is None and (code is None or c == code)
            ]

        def fill(code: str | None, outcome: _Outcome) -> None:
            for i in unfilled(code):
                earned, reason, line = outcome
                outcomes[i] = (earned, f"{reason} {surplus_note}" if i in surplus else reason, line)

        def result() -> list[_Outcome]:
            assert all(outcome is not None for outcome in outcomes)
            return [outcome for outcome in outcomes if outcome is not None]

        if not lines:
            fill(None, (False, "Not awarded: no working written.", None))
            return result()

        def at(number: int) -> str:
            return f"Line {number} '{lines[number - 1]}'"

        def stopped(number: int, why: str) -> list[_Outcome]:
            # Errors quote the text they are about; don't quote a whole line twice
            why = why.removeprefix(f"'{_normalise(lines[number - 1])}' ")
            answer_lost = bool(unfilled(ANSWER_CODE))
            first = unfilled()[0]
            # The first mark still open is the one this line would have earned
            outcomes[first] = (False, f"{at(number)} {why}. {STOP_NOTE}", number)
            if first in surplus:
                outcomes[first] = (False, f"{outcomes[first][1]} {surplus_note}", number)
            later = f"Not awarded: marking stopped at line {number} '{lines[number - 1]}' ({why})."
            fill(None, (False, f"{later} {STOP_NOTE}", number))
            # Line 1 failing leaves no equation to check an answer against
            if answer_lost and number > 1 and later_answer_is_correct(number):
                for i in [i for i, c in enumerate(codes) if c == ANSWER_CODE]:
                    earned, reason, line = outcomes[i] or (False, "", number)
                    outcomes[i] = (
                        earned,
                        f"{reason} A later line states the correct value, but a correct answer "
                        "reached through incorrect working earns nothing.",
                        line,
                    )
            return result()

        def later_answer_is_correct(number: int) -> bool:
            for line in lines[number:]:
                try:
                    if _answer_problem(_read_line(line, equation, ""), equation) is None:
                        return True
                except _StepError:
                    continue
            return False

        try:
            equation = _read_equation(lines[0])
        except _StepError as error:
            return stopped(1, str(error))
        v = equation.variable
        fill(
            FIRST_STEP_CODE,
            (
                True,
                f"{at(1)}: linear equation in {v} identified, which collects to "
                f"{_times(equation.a, v)} = {show(equation.c)} (a = {show(equation.a)}, "
                f"c = {show(equation.c)} in the form a{v} = c).",
                1,
            ),
        )

        if len(lines) == 1:
            fill(None, (False, "Not awarded: no working after the equation on line 1.", 1))
            return result()

        # Rearrangement lines, until the first line that states the value
        tail = _normalise(lines[0]).split("=")[-1].strip()
        answer_line: int | None = None
        last: _Line | None = None
        for number in range(2, len(lines) + 1):
            try:
                line = last = _read_line(lines[number - 1], equation, tail)
            except _StepError as error:
                return stopped(number, str(error))
            tail = line.text.split("=")[-1].strip()
            if _answer_problem(line, equation) is None:
                answer_line = number
                break
            steps = unfilled(STEP_CODE)
            if line.rearranges and steps:
                outcomes[steps[0]] = (True, f"{at(number)}: correct rearrangement step.", number)

        if answer_line is None:
            assert last is not None
            final = at(len(lines))
            for i in surplus & set(unfilled(STEP_CODE)):
                outcomes[i] = (
                    False,
                    f"{surplus_note} It is awarded only with a correct answer, and {final} ends "
                    f"the working without {v}'s value stated.",
                    len(lines),
                )
            fill(
                STEP_CODE,
                (
                    False,
                    f"Not awarded: no line rearranges the equation; the working ends at {final}.",
                    len(lines),
                ),
            )
            fill(
                ANSWER_CODE,
                (
                    False,
                    f"Not awarded: every step is correct, but no line states {v}'s value: "
                    f"{final} {_answer_problem(last, equation)}.",
                    len(lines),
                ),
            )
            fill(
                CONCLUSION_CODE,
                (False, f"Not awarded: a concluding statement counts only once {v}'s value is stated.", None),
            )
            return result()

        answer_at = at(answer_line)
        skipped = [i for i in unfilled(STEP_CODE) if i not in surplus]
        if skipped:
            # The rearrangement the question needs never appeared; marks run in order, so nothing after it counts
            outcomes[skipped[0]] = (
                False,
                f"Not awarded: {answer_at} states the value, but no rearrangement of the equation "
                "was shown before it.",
                answer_line,
            )
            fill(
                None,
                (
                    False,
                    "Not awarded: the M was not earned, and marks are earned in order, so none is "
                    f"awarded after it. {answer_at} states the value, but the working skips the "
                    "rearrangement.",
                    answer_line,
                ),
            )
            return result()

        for i in unfilled(STEP_CODE):
            outcomes[i] = (
                True, f"{answer_at}: {surplus_note} It is awarded with the correct answer.", answer_line
            )
        fill(
            ANSWER_CODE,
            (True, f"{answer_at}: {v} = {show(equation.solution)} stated, every step verified.", answer_line),
        )

        if not unfilled(CONCLUSION_CODE):
            return result()
        # After the answer, each line is either the conclusion or another correct step
        for number in range(answer_line + 1, len(lines) + 1):
            text = lines[number - 1]
            problem = _conclusion_problem(text, equation)
            if problem is None:
                fill(
                    CONCLUSION_CODE,
                    (True, f"{at(number)}: concluding statement giving {v}'s value.", number),
                )
                return result()
            if problem != _NO_CONCLUDING_WORD:
                return stopped(number, problem)
            try:
                tail = _read_line(text, equation, tail).text.split("=")[-1].strip()
            except _StepError as error:
                return stopped(number, str(error))
        words = ", ".join(f"'{word}'" for word in CONCLUDING_WORDS)
        fill(
            CONCLUSION_CODE,
            (
                False,
                f"Not awarded: no concluding statement after the answer on line {answer_line}. "
                f"It must give {v}'s value with a concluding word ({words}).",
                answer_line,
            ),
        )
        return result()
