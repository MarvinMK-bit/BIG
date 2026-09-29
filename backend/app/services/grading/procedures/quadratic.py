"""Quadratic equations, marked line by line.

Marking model
-------------
The scheme carries no fixed equation, so it marks ANY quadratic. The student's
own first line is read as the equation, in the form ax^2 + bx + c = 0: any
single variable letter, coefficients that may be negative, an implicit 1
("x^2") or omitted ("x^2 - 9 = 0"). The right-hand side must be 0.

The route is decided from the student's second line:
  - quadratic formula: the line substitutes into the formula, lists
    a = .., b = .., c = .., or works out the discriminant b^2 - 4ac;
  - product-sum (factorisation): the line gives the product ac and sum b, the
    pair of numbers with that product and sum, or rewrites the equation
    (splitting the middle term, grouping, or factorising).

Every remaining line is then checked, in order, as a legitimate step on that
route. Algebra is compared with sympy, never as strings, so "(x+3)(x+2) = 0"
and "x(x+2) + 3(x+2) = 0" are both accepted as equivalent to the equation. A
step is legitimate when it is true: an equation that is a multiple of the
original, a factor set to zero, arithmetic that evaluates correctly,
coefficients or a discriminant with the right values, the product-sum pair,
or x = value where every value is a root. Lines stating x = .. are allowed on
either route; other lines must stay on the route chosen on line 2.

Mark points use BIG's mark codes (docs/MARK-CODES.md), declared by code alone. Each is
earned on its own line, and reads "T - 1" when earned and "T - 0" when not:
  T  line 1: the equation identified and its coefficients extracted.
  M  a correct factorisation or quadratic formula step, earned on line 2. A scheme may
     declare up to four; the second is earned on line 3, and so on, until the answer
     line. Method lines beyond the scheme's M marks must still be correct, but earn
     nothing. A quadratic needs STEPS_NEEDED working step, so an M beyond the first that
     no method line earned is not held against the student: it is awarded with a correct
     answer, and its reason says the scheme declares more steps than this question type
     needs. Losing it while A is earned would break the prefix rule (docs/MARK-CODES.md).
  A  the answer: the first line from line 3 on that states every root correctly, with
     every line before it verified. Rational roots must be written as plain numbers
     ("-2", "1/2", "0.5"), not left as an unsimplified expression. A line saying there
     are no real roots is the answer when the discriminant is negative.
  D  a concluding statement on a line after the answer, e.g. "the roots are 2 and 3".
     Checked by pattern, not by a model: the line must contain every root's value and
     one of CONCLUDING_WORDS. Awarded only when A's answer was stated correctly.

Marking STOPS at the first incorrect step. Every mark from that point on is
zero, including marks that would otherwise follow from the student's own
working. This is deliberate, and stricter than UNEB follow-through marking,
which would credit later working done correctly from an earlier slip. A
correct final answer reached through incorrect working earns nothing. Lines
after the answer must each be a correct step or the conclusion.

Reading conventions: "±" is read as two branches; decimals are accepted when
correctly rounded to the places written; a number written directly after "/"
together with what it multiplies ("/2a", "/2(1)", "/2×1") is read as the whole
denominator, as students write it; "or", "and", "," and ";" separate the
statements on a line; a line starting with "=" continues the previous line.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import sympy

from app.services.grading.procedures.base import MarkAward, Procedure, marks_of
from app.services.grading.procedures.common import (
    CLAUSE_SPLIT_RE,
    CONCLUDING_RE,
    CONCLUDING_WORDS,
    LETTERS,
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

FORMULA = "quadratic formula"
FACTORISATION = "product-sum (factorisation)"

# The one working step between the equation and its roots
STEPS_NEEDED = 1

_ANSWER_LABEL_RE = re.compile(r"^\s*(?:answer|ans)\s*[:=]\s*", re.IGNORECASE)
_LABEL_RE = re.compile(
    r"^\s*(?:(?:solve|solution|therefore|hence|thus|so|the|roots?|numbers?|factors?|are|is)"
    r"\b\s*:?\s*)+",
    re.IGNORECASE,
)
_ASIDE_RE = re.compile(
    r"\(\s*(?:twice|repeated(?:\s+root)?|equal\s+roots|double\s+root)\s*\)", re.IGNORECASE
)
_SQRT_OPEN_RE = re.compile(r"√\s*\(")
_SQRT_TERM_RE = re.compile(r"√\s*(\d+(?:\.\d+)?|[A-Za-z])")
_DENOMINATOR_RE = re.compile(
    r"/\s*(\d+(?:\.\d+)?(?:\s*\*\s*\d+(?:\.\d+)?|[A-Za-z]|\([^()]*\))+)"
)
_NAMED_SYMBOLS = ("a", "b", "c", "D")


class _StepError(Exception):
    """The line is not a legitimate step; the message says why."""


@dataclass
class _Equation:
    variable: sympy.Symbol
    polynomial: sympy.Poly
    a: sympy.Expr
    b: sympy.Expr
    c: sympy.Expr
    roots: list[sympy.Expr]

    @property
    def discriminant(self) -> sympy.Expr:
        return self.b**2 - 4 * self.a * self.c

    @property
    def known(self) -> dict[sympy.Symbol, sympy.Expr]:
        """Values for a, b, c and the discriminant D, unless the student's variable uses that letter."""
        values = {"a": self.a, "b": self.b, "c": self.c, "D": self.discriminant}
        return {
            LETTERS[name]: value for name, value in values.items() if LETTERS[name] != self.variable
        }


@dataclass
class _Clause:
    kind: str  # "equation", "factor", "root", "arithmetic", "product", "sum", "number"
    route: str | None = None
    # A root clause using sqrt or a, b, c hints at the formula route when it opens the method
    route_hint: str | None = None
    values: list[sympy.Expr] = field(default_factory=list)
    final_text: str = ""


@dataclass
class _Line:
    route: str | None
    route_hint: str | None
    stated_roots: list[sympy.Expr]
    final_texts: list[str]
    tail: str
    no_real_roots: bool = False


def _normalise(line: str) -> str:
    text = line
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = _ANSWER_LABEL_RE.sub("", text)
    text = _LABEL_RE.sub("", text)
    text = _ASIDE_RE.sub("", text)
    text = _SQRT_OPEN_RE.sub("sqrt(", text)
    text = _SQRT_TERM_RE.sub(r"sqrt(\1)", text)
    text = text.replace("*", " * ")
    text = _DENOMINATOR_RE.sub(lambda m: f"/({m.group(1)})", text)
    return " ".join(text.split()).rstrip(".").strip()


def _parse(text: str, variable: sympy.Symbol) -> sympy.Expr:
    expr = parse_arithmetic(text, set(_NAMED_SYMBOLS) | {variable.name})
    if expr is None:
        raise _StepError(f"'{text}' could not be read as mathematics")
    return expr


def _read_equation(line: str) -> _Equation:
    text = _normalise(line)
    sides = text.split("=")
    if len(sides) != 2:
        raise _StepError("is not a single equation of the form ax^2 + bx + c = 0")
    # The variable isn't known yet: parse with a placeholder, then find it
    lhs = _parse(sides[0], sympy.Symbol("x"))
    rhs = _parse(sides[1], sympy.Symbol("x"))
    if rhs != 0:
        raise _StepError("is not in the form ax^2 + bx + c = 0: the right-hand side must be 0")
    symbols = lhs.free_symbols
    if len(symbols) != 1:
        raise _StepError("must be an equation in exactly one variable")
    (variable,) = symbols
    variable = sympy.Symbol(variable.name)
    try:
        polynomial = sympy.Poly(sympy.expand(lhs), variable)
    except sympy.PolynomialError:
        raise _StepError("is not a polynomial equation") from None
    if polynomial.degree() != 2:
        raise _StepError(f"is not a quadratic: it has degree {polynomial.degree()}")
    a, b, c = polynomial.all_coeffs()
    return _Equation(
        variable=variable,
        polynomial=polynomial,
        a=a,
        b=b,
        c=c,
        roots=list(sympy.roots(polynomial).keys()),
    )


def _branches(text: str) -> list[str]:
    return [text.replace("±", "+"), text.replace("±", "-")] if "±" in text else [text]


def _values(text: str, equation: _Equation) -> tuple[list[sympy.Expr], bool]:
    """A segment's value(s), one per ± branch, with a, b, c and D substituted.

    Also reports whether the segment uses formula notation (sqrt or a named coefficient).
    """
    values: list[sympy.Expr] = []
    formula = "sqrt" in text
    for branch in _branches(text):
        expr = _parse(branch, equation.variable)
        if expr.free_symbols & set(equation.known):
            formula = True
        values.append(sympy.expand(expr.subs(equation.known)))
    return values, formula


def _check_chain(segments: list[str], value_sets: list[list[sympy.Expr]], tolerance: float) -> None:
    """Each segment must equal the one before it; it may pick out one branch of a ±."""
    for i in range(1, len(value_sets)):
        for value in value_sets[i]:
            if not any(equal(value, earlier, tolerance) for earlier in value_sets[i - 1]):
                raise _StepError(f"'{segments[i]}' does not equal '{segments[i - 1]}'")


def _matching_root(value: sympy.Expr, equation: _Equation, tolerance: float) -> sympy.Expr | None:
    return next((root for root in equation.roots if equal(value, root, tolerance)), None)


def _is_root(value: sympy.Expr, equation: _Equation, tolerance: float) -> bool:
    return _matching_root(value, equation, tolerance) is not None


def _read_clause(text: str, equation: _Equation) -> _Clause:
    segments = [segment.strip() for segment in text.split("=")]
    if any(not segment for segment in segments):
        raise _StepError(f"'{text}' has nothing on one side of an equals sign")
    tolerance = rounding_tolerance(text)
    variable = equation.variable

    label = segments[0].casefold()
    if label in ("product", "sum") and len(segments) > 1:
        target = equation.a * equation.c if label == "product" else equation.b
        for segment in segments[1:]:
            for value in _values(segment, equation)[0]:
                if value.free_symbols or not equal(value, target, tolerance):
                    raise _StepError(
                        f"the {label} should be {show(target)} "
                        f"({'ac' if label == 'product' else 'b'}), not {segment}"
                    )
        return _Clause(kind=label, route=FACTORISATION)

    value_sets: list[list[sympy.Expr]] = []
    formula = False
    for segment in segments:
        values, uses_formula = _values(segment, equation)
        value_sets.append(values)
        formula = formula or uses_formula

    stray = {s for values in value_sets for v in values for s in v.free_symbols} - {variable}
    if stray:
        names = ", ".join(sorted(s.name for s in stray))
        raise _StepError(f"'{text}' uses {names}, which is not part of the equation")
    uses_variable = [any(variable in v.free_symbols for v in values) for values in value_sets]

    if len(segments) == 1:
        if uses_variable[0]:
            raise _StepError(f"'{text}' is an expression on its own, not a step")
        return _Clause(kind="number", values=value_sets[0], final_text=segments[0])

    if not any(uses_variable):
        _check_chain(segments, value_sets, tolerance)
        return _Clause(kind="arithmetic", route=FORMULA if formula else None)

    if value_sets[0] == [variable] and not any(uses_variable[1:]):
        for value in value_sets[1]:
            if not _is_root(value, equation, tolerance):
                raise _StepError(
                    f"'{segments[1]}' gives {variable} = {show(value)}, which is not a root"
                )
        _check_chain(segments[1:], value_sets[1:], tolerance)
        return _Clause(
            kind="root",
            route_hint=FORMULA if formula else None,
            # A rounded decimal stands for the exact root it was checked against
            values=[_matching_root(value, equation, tolerance) for value in value_sets[-1]],
            final_text=segments[-1],
        )

    if "±" in text:
        raise _StepError(f"'{text}' uses ± outside a statement {variable} = ..")
    exprs = [values[0] for values in value_sets]
    factor_roots: list[sympy.Expr] = []
    for i in range(1, len(exprs)):
        difference = sympy.expand(exprs[i - 1] - exprs[i])
        if difference == 0:
            continue
        where = f"'{segments[i - 1]} = {segments[i]}'"
        try:
            step = sympy.Poly(difference, variable)
        except sympy.PolynomialError:
            raise _StepError(f"{where} is not a polynomial equation") from None
        if step.degree() == 0:
            raise _StepError(f"{where} is false")
        if step.degree() > 2 or not equation.polynomial.rem(step).is_zero:
            raise _StepError(f"{where} is not equivalent to the equation or a factor of it")
        if step.degree() == 1:
            slope, intercept = step.all_coeffs()
            factor_roots.append(-intercept / slope)
    if factor_roots:
        return _Clause(kind="factor", values=factor_roots)
    return _Clause(kind="equation", route=FACTORISATION)


def _read_line(line: str, equation: _Equation, previous_tail: str) -> _Line:
    text = _normalise(line)
    if text.startswith("=") and previous_tail:
        text = previous_tail + " " + text

    if "no real" in text.casefold():
        if equation.discriminant >= 0:
            raise _StepError("says there are no real roots, but the equation has real roots")
        return _Line(
            route=None, route_hint=None, stated_roots=[], final_texts=[], tail="", no_real_roots=True
        )

    clauses = [_read_clause(part, equation) for part in CLAUSE_SPLIT_RE.split(text) if part.strip()]
    if not clauses:
        raise _StepError("has no working on it")

    numbers = [clause for clause in clauses if clause.kind == "number"]
    others = [clause for clause in clauses if clause.kind != "number"]
    if numbers:
        values = [value for clause in numbers for value in clause.values]
        tolerance = rounding_tolerance(text)
        shown = ", ".join(clause.final_text for clause in numbers)
        states_roots = any(clause.kind in ("root", "factor") for clause in others) or not others
        if states_roots and all(_is_root(value, equation, tolerance) for value in values):
            for clause in numbers:
                clause.kind = "root"
                clause.values = [_matching_root(v, equation, tolerance) for v in clause.values]
        elif (
            len(values) == 2
            and equal(values[0] * values[1], equation.a * equation.c, tolerance)
            and equal(values[0] + values[1], equation.b, tolerance)
        ):
            for clause in numbers:
                clause.route = FACTORISATION
        elif any(clause.kind in ("root", "factor") for clause in others):
            raise _StepError(f"{shown} is not a root of the equation")
        else:
            raise _StepError(
                f"{shown} is neither the roots nor a pair with product ac = "
                f"{show(equation.a * equation.c)} and sum b = {show(equation.b)}"
            )

    routes = {clause.route for clause in clauses} - {None}
    if len(routes) > 1:
        raise _StepError("mixes the quadratic formula with product-sum working")
    hints = {clause.route_hint for clause in clauses} - {None}
    roots = [clause for clause in clauses if clause.kind == "root"]
    return _Line(
        route=next(iter(routes), None),
        route_hint=next(iter(hints), None),
        stated_roots=[value for clause in roots for value in clause.values],
        final_texts=[branch for clause in roots for branch in _branches(clause.final_text)],
        tail=text.split("=")[-1].strip(),
    )


def _answer_problem(line: _Line, equation: _Equation) -> str | None:
    """Why the last line doesn't state both roots, or None when it does."""
    if line.no_real_roots:
        return None
    if not line.stated_roots:
        return f"does not state the roots as {equation.variable} = .."
    missing = [root for root in equation.roots if root not in line.stated_roots]
    if missing:
        shown = ", ".join(show(root) for root in missing)
        return f"does not state every root: {equation.variable} = {shown} is missing"
    if all(root.is_rational for root in equation.roots) and not all(
        PLAIN_NUMBER_RE.match(text.replace(" ", "")) for text in line.final_texts
    ):
        return "leaves the roots as unsimplified expressions"
    return None


_NO_CONCLUDING_WORD = "has no concluding word"


def _conclusion_problem(line: str, equation: _Equation) -> str | None:
    """Why the line isn't a concluding statement, or None when it is: it must hold a
    concluding word and the value of every root (or say there are no real roots)."""
    if not CONCLUDING_RE.search(line.replace("∴", " therefore ")):
        return _NO_CONCLUDING_WORD
    text = _normalise(line)
    if "no real" in text.casefold():
        if equation.discriminant >= 0:
            return "says there are no real roots, but the equation has real roots"
        return None
    # Prose is dropped, keeping sqrt; what's left is read clause by clause
    text = PROSE_RE.sub(lambda m: m.group(0) if m.group(0) == "sqrt" else ";", text)
    found: list[tuple[sympy.Expr, float]] = []
    for clause in CLAUSE_SPLIT_RE.split(text):
        value_text = clause.split("=")[-1].strip()
        if not value_text:
            continue
        try:
            values, _ = _values(value_text, equation)
        except _StepError:
            continue
        found.extend((value, rounding_tolerance(value_text)) for value in values if not value.free_symbols)
    missing = [
        root for root in equation.roots if not any(equal(v, root, tol) for v, tol in found)
    ]
    if missing:
        shown = ", ".join(show(root) for root in missing)
        return f"does not give the root{'s' if len(missing) > 1 else ''} {shown}"
    return None


# A mark's (earned, reason, the 1-based number of the line its reason names, if any)
_Outcome = tuple[bool, str, int | None]


@register
class QuadraticProcedure(Procedure):
    """Marks any quadratic equation line by line; see the module docstring."""

    name = "quadratic"

    def default_marks(self) -> list[SchemeMark]:
        # The same as quadratic-any
        return marks_of(FIRST_STEP_CODE, STEP_CODE, ANSWER_CODE, CONCLUSION_CODE)

    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        if params:
            raise ValueError(f"quadratic procedure has no parameter(s) {', '.join(sorted(params))}")
        # None declared: the procedure's own
        marks = marks or self.default_marks()
        codes = [mark.id for mark in marks]
        check_mark_codes(codes, "quadratic procedure scheme")
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
            f"needs: a quadratic takes {STEPS_NEEDED} working step (a factorisation or quadratic "
            "formula step), so this M stands for no step of the working."
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
            remaining = unfilled()
            # The first mark still open is the one this line would have earned
            outcomes[remaining[0]] = (False, f"{at(number)} {why}. {STOP_NOTE}", number)
            if remaining[0] in surplus:
                outcomes[remaining[0]] = (False, f"{outcomes[remaining[0]][1]} {surplus_note}", number)
            later = f"Not awarded: marking stopped at line {number} '{lines[number - 1]}' ({why})."
            fill(None, (False, f"{later} {STOP_NOTE}", number))
            # Line 1 failing leaves no equation to check an answer against
            if answer_lost and number > 1 and later_answer_is_correct(number):
                for i in [i for i, c in enumerate(codes) if c == ANSWER_CODE]:
                    earned, reason, line = outcomes[i] or (False, "", number)
                    outcomes[i] = (
                        earned,
                        f"{reason} A later line states the correct roots, but a correct answer "
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
        fill(
            FIRST_STEP_CODE,
            (
                True,
                f"{at(1)}: equation in {equation.variable} identified, "
                f"a = {show(equation.a)}, b = {show(equation.b)}, c = {show(equation.c)}.",
                1,
            ),
        )

        if len(lines) == 1:
            fill(None, (False, "Not awarded: no working after the equation on line 1.", 1))
            return result()

        # Method lines, until the first line from line 3 on that states every root
        route: str | None = None
        tail = ""
        last: _Line | None = None
        answer_line: int | None = None
        for number in range(2, len(lines) + 1):
            try:
                last = _read_line(lines[number - 1], equation, tail)
            except _StepError as error:
                return stopped(number, str(error))
            if number == 2:
                route = last.route or last.route_hint
                if route is None:
                    return stopped(number, "does not show a product-sum or quadratic formula step")
            elif last.route is not None and last.route != route:
                return stopped(
                    number, f"switches to the {last.route} route after line 2 used the {route}"
                )
            tail = last.tail
            if number >= 3 and _answer_problem(last, equation) is None:
                answer_line = number
                break
            steps = unfilled(STEP_CODE)
            if steps:
                outcomes[steps[0]] = (True, f"{at(number)}: correct {route} step.", number)

        assert last is not None
        if answer_line is None:
            final = at(len(lines))
            for i in unfilled(STEP_CODE):
                outcomes[i] = (
                    False,
                    f"{surplus_note} It is awarded only with a correct answer, and {final} ends "
                    "the working without the roots stated.",
                    len(lines),
                )
            problem = _answer_problem(last, equation) or "does not state the roots on a line after line 2"
            fill(
                ANSWER_CODE,
                (False, f"Not awarded: every step is correct, but {final} {problem}.", len(lines)),
            )
            fill(
                CONCLUSION_CODE,
                (
                    False,
                    "Not awarded: a concluding statement counts only once the roots are stated correctly.",
                    None,
                ),
            )
            return result()

        answer_at = at(answer_line)
        # Line 2 always earns the first M, so any still open is one the question doesn't need
        for i in unfilled(STEP_CODE):
            outcomes[i] = (
                True, f"{answer_at}: {surplus_note} It is awarded with the correct answer.", answer_line
            )
        if last.no_real_roots:
            fill(ANSWER_CODE, (True, f"{answer_at}: correctly states there are no real roots.", answer_line))
        else:
            stated = ", ".join(f"{equation.variable} = {show(root)}" for root in equation.roots)
            fill(ANSWER_CODE, (True, f"{answer_at}: roots {stated} stated, every step verified.", answer_line))

        if not unfilled(CONCLUSION_CODE):
            return result()
        # After the answer, each line is either the conclusion or another correct step
        for number in range(answer_line + 1, len(lines) + 1):
            line = lines[number - 1]
            problem = _conclusion_problem(line, equation)
            if problem is None:
                gives = "that there are no real roots" if last.no_real_roots else "the roots"
                fill(CONCLUSION_CODE, (True, f"{at(number)}: concluding statement giving {gives}.", number))
                return result()
            if problem != _NO_CONCLUDING_WORD:
                return stopped(number, problem)
            try:
                tail = _read_line(line, equation, tail).tail
            except _StepError as error:
                return stopped(number, str(error))
        words = ", ".join(f"'{word}'" for word in CONCLUDING_WORDS)
        fill(
            CONCLUSION_CODE,
            (
                False,
                f"Not awarded: no concluding statement after the answer on line {answer_line}. "
                f"It must give the roots with a concluding word ({words}).",
                answer_line,
            ),
        )
        return result()
