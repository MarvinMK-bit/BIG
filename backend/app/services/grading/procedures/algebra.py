"""Algebra of any of the kinds BIG marks, routed to the specialist procedure that fits.

This procedure does no marking itself. It reads the shape of the student's working, chooses a
specialist, and returns that specialist's awards unchanged, except that the first award's reason
opens by naming the route taken, so a reader can see which specialist ran.

Routing, in this order:
  - two linear equations in the same two unknowns on the first two lines -> simultaneous
  - a quadratic equation in one unknown on the first line -> quadratic
  - a linear expression in one unknown on the first line -> like_terms. A first line with an
    equals sign counts when every side is the same expression ("3x + 3x = 6x") or the last side
    still has the unknown ("3x + 3x = 5x", an incorrect simplification, not an equation to solve).

Routing looks at shape only: the specialist decides whether the working is right. Two parallel
equations still go to simultaneous, whose T explains why they have no single solution;
"x^2 = 5x - 6" still goes to quadratic, whose T asks for the form ax^2 + bx + c = 0.

A question that declares no marks passes an empty list through, and the chosen specialist
awards its own default_marks. The algebra procedure has no default_marks of its own: its marks
depend on the route.

When nothing fits, every declared mark is zero with the reason NO_ROUTE. With no marks declared
there are none to zero, so it awards a single T, the mark for identifying what the question is,
zero with that reason.
"""

import re
import string
from dataclasses import replace
from decimal import Decimal
from typing import Any

import sympy

from app.services.grading.procedures.base import MarkAward, Procedure, marks_of
from app.services.grading.procedures.common import REPLACEMENTS, parse_arithmetic
from app.services.grading.procedures.registry import get_procedure, register
from app.services.grading.schemes import FIRST_STEP_CODE, MAX_STEP_MARKS, SchemeMark

NO_ROUTE = (
    "this working does not match any question type the algebra scheme covers: collection of "
    "like terms, quadratic equations, or simultaneous equations in two unknowns."
)

# Specialist procedure name -> what it marks, for the route named in the first reason
ROUTES: dict[str, str] = {
    "simultaneous": "simultaneous equations in two unknowns",
    "quadratic": "a quadratic equation",
    "like_terms": "collection of like terms",
}

_LEADING_WORDS_RE = re.compile(r"^\s*(?:(?:simplify|solve|collect|expand|find)\b\s*)+", re.IGNORECASE)
_TRAILING_LABEL_RE = re.compile(
    r"(?:\s|\.{2,}|-{2,}|…)\s*[(\[]\s*(?:\d{1,2}|i{1,3}|iv|v)\s*[)\]]\s*$", re.IGNORECASE
)
_LETTER_RE = re.compile(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])")
_ALL_LETTERS = set(string.ascii_letters)


def _sides(line: str) -> tuple[list[str], list[sympy.Expr]] | None:
    """Each side of the line's equals signs, as written and read, or None when a side can't be read."""
    text = line
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = text.rsplit(":", 1)[-1]
    text = _LEADING_WORDS_RE.sub("", text)
    text = _TRAILING_LABEL_RE.sub("", text)
    written = [side.strip() for side in text.split("=")]
    read = [parse_arithmetic(side, _ALL_LETTERS) for side in written]
    if not all(written) or any(expr is None for expr in read):
        return None
    return written, [expr for expr in read if expr is not None]


def _degree(expr: sympy.Expr) -> int | None:
    """Total degree in the expression's symbols, or None when it isn't a polynomial."""
    try:
        return sympy.Poly(expr, *sorted(expr.free_symbols, key=lambda s: s.name)).total_degree()
    except (sympy.PolynomialError, sympy.GeneratorsNeeded):
        return None


def _equation(line: str) -> sympy.Expr | None:
    """The line as an expression equal to zero, when it is a single equation."""
    sides = _sides(line)
    if sides is None or len(sides[1]) != 2:
        return None
    lhs, rhs = sides[1]
    return sympy.expand(lhs - rhs)


def _is_simultaneous(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False
    equations = [_equation(line) for line in lines[:2]]
    if any(e is None or _degree(e) != 1 for e in equations):
        return False
    unknowns = [e.free_symbols for e in equations if e is not None]
    return len(unknowns[0]) == 2 and unknowns[0] == unknowns[1]


def _is_quadratic(lines: list[str]) -> bool:
    equation = _equation(lines[0])
    return equation is not None and len(equation.free_symbols) == 1 and _degree(equation) == 2


def _is_like_terms(lines: list[str]) -> bool:
    sides = _sides(lines[0])
    if sides is None:
        return False
    written, read = sides
    letters = set(_LETTER_RE.findall(written[0]))
    if len(letters) != 1:
        return False
    first = sympy.expand(read[0])
    if first.free_symbols - {sympy.Symbol(letter) for letter in letters}:
        return False
    if first.free_symbols and _degree(first) != 1:
        return False
    if len(read) == 1:
        return True
    same = all(sympy.expand(expr - first) == 0 for expr in read[1:])
    return same or bool(set(_LETTER_RE.findall(written[-1])) & letters)


def route(working: list[str]) -> str | None:
    """The specialist procedure for this working, or None when none fits."""
    lines = [line.strip() for line in working if line.strip()]
    if not lines:
        return None
    if _is_simultaneous(lines):
        return "simultaneous"
    if _is_quadratic(lines):
        return "quadratic"
    if _is_like_terms(lines):
        return "like_terms"
    return None


@register
class AlgebraProcedure(Procedure):
    """Routes the working to simultaneous, quadratic or like_terms; see the module docstring."""

    name = "algebra"
    # Declared marks are checked by the specialist chosen, which may take none
    step_marks = (0, MAX_STEP_MARKS)

    def default_marks(self) -> list[SchemeMark]:
        raise ValueError(
            "the algebra procedure has no fixed mark structure: its marks depend on the route "
            "chosen from the working, so the specialist it routes to supplies them"
        )

    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        if params:
            raise ValueError(f"algebra procedure has no parameter(s) {', '.join(sorted(params))}")
        chosen = route(working)
        if chosen is None:
            reason = f"Not awarded: {NO_ROUTE}"
            unmatched = marks or marks_of(FIRST_STEP_CODE)
            return [MarkAward(mark_id=mark.id, awarded=Decimal(0), reason=reason) for mark in unmatched]
        # An empty marks list passes through: the specialist then awards its own
        awards = get_procedure(chosen).grade(working, {}, marks)
        if awards:
            named = f"Algebra route: {ROUTES[chosen]} (the {chosen} procedure). {awards[0].reason}"
            awards[0] = replace(awards[0], reason=named)
        return awards
