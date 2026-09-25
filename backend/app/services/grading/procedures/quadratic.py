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

Marking STOPS at the first incorrect step. Every mark from that point on is
zero, including marks that would otherwise follow from the student's own
working. This is deliberate, and stricter than UNEB follow-through marking,
which would credit later working done correctly from an earlier slip. A
correct final answer reached through incorrect working earns nothing.

Mark points (default ids; a scheme renames them with params.mark_ids):
  M1   correct equation identified and coefficients extracted (line 1)
  M1b  correct method applied to the next step (line 2)
  A1   both roots correct and stated, on the last line, with every step verified.
       Rational roots must be written as plain numbers ("-2", "1/2", "0.5"),
       not left as an unsimplified expression. A line saying there are no
       real roots earns A1 when the discriminant is negative.

Reading conventions: "±" is read as two branches; decimals are accepted when
correctly rounded to the places written; a number written directly after "/"
together with what it multiplies ("/2a", "/2(1)", "/2×1") is read as the whole
denominator, as students write it; "or", "and", "," and ";" separate the
statements on a line; a line starting with "=" continues the previous line.
"""

import re
import string
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)

from app.services.grading.procedures.base import MarkAward, Procedure
from app.services.grading.procedures.registry import register
from app.services.grading.schemes import SchemeMark

FORMULA = "quadratic formula"
FACTORISATION = "product-sum (factorisation)"

_ROLES = ("equation", "method", "answer")
_DEFAULT_MARK_IDS: dict[str, str] = {"equation": "M1", "method": "M1b", "answer": "A1"}

_STOP_NOTE = (
    "Marking stops at the first incorrect step: no later mark is awarded, even for "
    "working that follows correctly from it. This is stricter than UNEB "
    "follow-through marking."
)

_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("$", ""),
    ("`", ""),
    ("\\left", ""),
    ("\\right", ""),
    ("\\pm", "±"),
    ("+/-", "±"),
    ("\\times", "*"),
    ("\\cdot", "*"),
    ("\\sqrt", "√"),
    ("\\frac", ""),
    ("}{", ")/("),
    ("{", "("),
    ("}", ")"),
    ("−", "-"),
    ("–", "-"),
    ("—", "-"),
    ("×", "*"),
    ("·", "*"),
    ("÷", "/"),
    ("²", "^2"),
    ("Δ", "D"),
    ("∆", "D"),
    ("½", "(1/2)"),
    ("¼", "(1/4)"),
    ("¾", "(3/4)"),
    ("⅓", "(1/3)"),
    ("⅔", "(2/3)"),
    ("∴", "therefore "),
)
_ANSWER_LABEL_RE = re.compile(r"^\s*(?:answer|ans)\s*[:=]\s*", re.IGNORECASE)
_LABEL_RE = re.compile(
    r"^\s*(?:(?:solve|solution|therefore|hence|thus|so|the|roots?|numbers?|factors?|are|is)"
    r"\b\s*:?\s*)+",
    re.IGNORECASE,
)
_ASIDE_RE = re.compile(
    r"\(\s*(?:twice|repeated(?:\s+root)?|equal\s+roots|double\s+root)\s*\)", re.IGNORECASE
)
_CLAUSE_SPLIT_RE = re.compile(r"\s+(?:or|and)\s+|\s*[,;&]\s*", re.IGNORECASE)
_SQRT_OPEN_RE = re.compile(r"√\s*\(")
_SQRT_TERM_RE = re.compile(r"√\s*(\d+(?:\.\d+)?|[A-Za-z])")
_DENOMINATOR_RE = re.compile(
    r"/\s*(\d+(?:\.\d+)?(?:\s*\*\s*\d+(?:\.\d+)?|[A-Za-z]|\([^()]*\))+)"
)
_DECIMAL_RE = re.compile(r"\d\.(\d+)")
_PLAIN_NUMBER_RE = re.compile(r"^\(?[+-]?\d+(?:\.\d+)?(?:/\d+)?\)?$")

# Student text reaches parse_expr, which evaluates Python: allow arithmetic only
_ALLOWED_RE = re.compile(r"^[0-9A-Za-z+\-*/^().\s]+$")
_WORD_RE = re.compile(r"[A-Za-z]{2,}")
# Exponents stay single digits, few and unchained, so 9^9^9^9 cannot stall the grader
_EXPONENT_RE = re.compile(r"\^\s*(?:\(\s*\d\s*\)|\d(?![\d.]))(?!\s*\^)")
_MAX_POWERS = 4
_MAX_EXPRESSION_LENGTH = 160

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
    rationalize,
)
# Every letter is a plain symbol, so "E", "I", "S" and friends aren't read as sympy constants
_LETTERS: dict[str, sympy.Symbol] = {letter: sympy.Symbol(letter) for letter in string.ascii_letters}
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
            _LETTERS[name]: value for name, value in values.items() if _LETTERS[name] != self.variable
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
    for old, new in _REPLACEMENTS:
        text = text.replace(old, new)
    text = _ANSWER_LABEL_RE.sub("", text)
    text = _LABEL_RE.sub("", text)
    text = _ASIDE_RE.sub("", text)
    text = _SQRT_OPEN_RE.sub("sqrt(", text)
    text = _SQRT_TERM_RE.sub(r"sqrt(\1)", text)
    text = text.replace("*", " * ")
    text = _DENOMINATOR_RE.sub(lambda m: f"/({m.group(1)})", text)
    return " ".join(text.split()).rstrip(".").strip()


def _tolerance(text: str) -> float:
    places = [len(match) for match in _DECIMAL_RE.findall(text)]
    return 0.5 * 10 ** -max(places) + 1e-9 if places else 0.0


def _equal(u: sympy.Expr, v: sympy.Expr, tolerance: float) -> bool:
    try:
        difference = complex(sympy.N(u - v, 30))
    except (TypeError, ValueError):
        return False
    return abs(difference) <= max(tolerance, 1e-20)


def _parse(text: str, variable: sympy.Symbol) -> sympy.Expr:
    compact = text.strip()
    if (
        not compact
        or len(compact) > _MAX_EXPRESSION_LENGTH
        or not _ALLOWED_RE.match(compact)
        or "**" in compact
        or compact.count("^") > _MAX_POWERS
        or len(_EXPONENT_RE.findall(compact)) != compact.count("^")
    ):
        raise _StepError(f"'{text}' could not be read as mathematics")
    allowed_letters = set(_NAMED_SYMBOLS) | {variable.name}
    for word in _WORD_RE.findall(compact):
        if word != "sqrt" and not set(word) <= allowed_letters:
            raise _StepError(f"'{text}' could not be read as mathematics")
    try:
        expr = parse_expr(compact, local_dict=dict(_LETTERS), transformations=_TRANSFORMATIONS)
    except Exception:
        raise _StepError(f"'{text}' could not be read as mathematics") from None
    if not isinstance(expr, sympy.Expr):
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


def _show(value: sympy.Expr) -> str:
    return sympy.sstr(sympy.nsimplify(value) if value.is_Float else value)


def _check_chain(segments: list[str], value_sets: list[list[sympy.Expr]], tolerance: float) -> None:
    """Each segment must equal the one before it; it may pick out one branch of a ±."""
    for i in range(1, len(value_sets)):
        for value in value_sets[i]:
            if not any(_equal(value, earlier, tolerance) for earlier in value_sets[i - 1]):
                raise _StepError(f"'{segments[i]}' does not equal '{segments[i - 1]}'")


def _matching_root(value: sympy.Expr, equation: _Equation, tolerance: float) -> sympy.Expr | None:
    return next((root for root in equation.roots if _equal(value, root, tolerance)), None)


def _is_root(value: sympy.Expr, equation: _Equation, tolerance: float) -> bool:
    return _matching_root(value, equation, tolerance) is not None


def _read_clause(text: str, equation: _Equation) -> _Clause:
    segments = [segment.strip() for segment in text.split("=")]
    if any(not segment for segment in segments):
        raise _StepError(f"'{text}' has nothing on one side of an equals sign")
    tolerance = _tolerance(text)
    variable = equation.variable

    label = segments[0].casefold()
    if label in ("product", "sum") and len(segments) > 1:
        target = equation.a * equation.c if label == "product" else equation.b
        for segment in segments[1:]:
            for value in _values(segment, equation)[0]:
                if value.free_symbols or not _equal(value, target, tolerance):
                    raise _StepError(
                        f"the {label} should be {_show(target)} "
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
                    f"'{segments[1]}' gives {variable} = {_show(value)}, which is not a root"
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

    clauses = [_read_clause(part, equation) for part in _CLAUSE_SPLIT_RE.split(text) if part.strip()]
    if not clauses:
        raise _StepError("has no working on it")

    numbers = [clause for clause in clauses if clause.kind == "number"]
    others = [clause for clause in clauses if clause.kind != "number"]
    if numbers:
        values = [value for clause in numbers for value in clause.values]
        tolerance = _tolerance(text)
        shown = ", ".join(clause.final_text for clause in numbers)
        states_roots = any(clause.kind in ("root", "factor") for clause in others) or not others
        if states_roots and all(_is_root(value, equation, tolerance) for value in values):
            for clause in numbers:
                clause.kind = "root"
                clause.values = [_matching_root(v, equation, tolerance) for v in clause.values]
        elif (
            len(values) == 2
            and _equal(values[0] * values[1], equation.a * equation.c, tolerance)
            and _equal(values[0] + values[1], equation.b, tolerance)
        ):
            for clause in numbers:
                clause.route = FACTORISATION
        elif any(clause.kind in ("root", "factor") for clause in others):
            raise _StepError(f"{shown} is not a root of the equation")
        else:
            raise _StepError(
                f"{shown} is neither the roots nor a pair with product ac = "
                f"{_show(equation.a * equation.c)} and sum b = {_show(equation.b)}"
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
        shown = ", ".join(_show(root) for root in missing)
        return f"does not state every root: {equation.variable} = {shown} is missing"
    if all(root.is_rational for root in equation.roots) and not all(
        _PLAIN_NUMBER_RE.match(text.replace(" ", "")) for text in line.final_texts
    ):
        return "leaves the roots as unsimplified expressions"
    return None


@register
class QuadraticProcedure(Procedure):
    """Marks any quadratic equation line by line; see the module docstring."""

    name = "quadratic"

    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        mark_ids = self._mark_ids(params, marks)
        by_id = {mark.id: mark for mark in marks}
        lines = [line.strip() for line in working if line.strip()]
        outcomes = self._mark(lines)
        return [
            MarkAward(
                mark_id=mark_ids[role],
                awarded=by_id[mark_ids[role]].max_mark if earned else Decimal(0),
                reason=reason,
            )
            for role, (earned, reason) in outcomes.items()
        ]

    @staticmethod
    def _mark_ids(params: dict[str, Any], marks: list[SchemeMark]) -> dict[str, str]:
        unknown = set(params) - {"mark_ids"}
        if unknown:
            raise ValueError(f"quadratic procedure has no parameter(s) {', '.join(sorted(unknown))}")
        overrides = params.get("mark_ids") or {}
        if not isinstance(overrides, dict) or set(overrides) - set(_ROLES):
            raise ValueError(
                f"quadratic procedure param 'mark_ids' must map some of {', '.join(_ROLES)} to mark ids"
            )
        mark_ids = {role: str(overrides.get(role, _DEFAULT_MARK_IDS[role])) for role in _ROLES}
        if len(set(mark_ids.values())) != len(_ROLES):
            raise ValueError("quadratic procedure mark ids must be distinct")
        scheme_ids = {mark.id for mark in marks}
        if scheme_ids != set(mark_ids.values()):
            raise ValueError(
                f"quadratic procedure awards marks {', '.join(mark_ids.values())} but the scheme "
                f"defines {', '.join(mark.id for mark in marks)}"
            )
        return mark_ids

    @staticmethod
    def _mark(lines: list[str]) -> dict[str, tuple[bool, str]]:
        """Each role's (earned, reason). Line 1 carries the equation mark, line 2 the method
        mark, and the answer mark needs every line through the last to be correct."""
        if not lines:
            return {role: (False, "Not awarded: no working written.") for role in _ROLES}

        def at(number: int) -> str:
            return f"Line {number} '{lines[number - 1]}'"

        def stopped(number: int, why: str) -> dict[str, tuple[bool, str]]:
            # Errors quote the text they are about; don't quote a whole line twice
            why = why.removeprefix(f"'{_normalise(lines[number - 1])}' ")
            later = f"Not awarded: marking stopped at line {number} '{lines[number - 1]}' ({why})."
            lost_here = min(number, 3) - 1  # the role this line would have earned
            outcomes = dict(done)
            for index, role in enumerate(_ROLES):
                if role in outcomes:
                    continue
                if index == lost_here:
                    outcomes[role] = (False, f"{at(number)} {why}. {_STOP_NOTE}")
                else:
                    outcomes[role] = (False, f"{later} {_STOP_NOTE}")
            # Line 1 failing leaves no equation to check an answer against
            if 1 < number < len(lines) and final_answer_is_correct():
                earned, reason = outcomes["answer"]
                outcomes["answer"] = (
                    earned,
                    f"{reason} {at(len(lines))} states the correct roots, but a correct answer "
                    "reached through incorrect working earns nothing.",
                )
            return outcomes

        def final_answer_is_correct() -> bool:
            try:
                return _answer_problem(_read_line(lines[-1], equation, ""), equation) is None
            except _StepError:
                return False

        done: dict[str, tuple[bool, str]] = {}
        try:
            equation = _read_equation(lines[0])
        except _StepError as error:
            return stopped(1, str(error))
        done["equation"] = (
            True,
            f"{at(1)}: equation in {equation.variable} identified, "
            f"a = {_show(equation.a)}, b = {_show(equation.b)}, c = {_show(equation.c)}.",
        )

        if len(lines) == 1:
            nothing = "Not awarded: no working after the equation on line 1."
            return {**done, "method": (False, nothing), "answer": (False, nothing)}

        route: str | None = None
        tail = ""
        last: _Line | None = None
        for number in range(2, len(lines) + 1):
            try:
                last = _read_line(lines[number - 1], equation, tail)
            except _StepError as error:
                return stopped(number, str(error))
            if number == 2:
                route = last.route or last.route_hint
                if route is None:
                    return stopped(number, "does not show a product-sum or quadratic formula step")
                done["method"] = (True, f"{at(2)}: correct {route} step.")
            elif last.route is not None and last.route != route:
                return stopped(
                    number, f"switches to the {last.route} route after line 2 used the {route}"
                )
            tail = last.tail

        assert last is not None
        final = at(len(lines))
        problem = _answer_problem(last, equation)
        if problem is not None:
            done["answer"] = (False, f"Not awarded: every step is correct, but {final} {problem}.")
        elif last.no_real_roots:
            done["answer"] = (True, f"{final}: correctly states there are no real roots.")
        else:
            stated = ", ".join(f"{equation.variable} = {_show(root)}" for root in equation.roots)
            done["answer"] = (True, f"{final}: roots {stated} stated, every step verified.")
        return done
