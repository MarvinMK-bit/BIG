"""Simultaneous linear equations in two unknowns, marked line by line.

Marking model
-------------
The scheme carries no fixed system, so it marks ANY pair of linear equations in two unknowns.
The student's first TWO lines are read as the system: each a linear equation using both of the
same two unknowns (any letters), in any arrangement ("2x + y = 8", "y = 2x - 1"), with
coefficients that may be negative, fractional or implicit. The pair must have exactly one
solution.

The route is decided from the student's third line:
  - elimination: the line multiplies an equation to match coefficients ("4x + 2y = 16"), or
    adds or subtracts the equations to leave an equation in one unknown ("5x = 15");
  - substitution: the line makes one unknown the subject ("y = 8 - 2x"), or is an equation in
    one unknown with the other's expression substituted in brackets ("3x - 2(8 - 2x) = 5"),
    or, where a given equation already has an unknown as its subject, any equation in the
    remaining unknown.
A third line that fits neither (a value stated without working, a given equation copied out,
arithmetic alone) is the first incorrect step.

Every remaining line is then checked, in order, as a legitimate step. Algebra is compared with
sympy, never as strings. Each equation on a line must be linear and hold at the system's
solution; because the system has exactly one solution, that is the same as following from the
two equations. Arithmetic must evaluate correctly. Equations in one unknown, values found and
values substituted back are allowed on either route; scaling or combining the equations is
elimination only, making an unknown the subject is substitution only, and a line that switches
route after line 3 is incorrect.

Mark points use BIG's mark codes (docs/MARK-CODES.md), declared by code alone. Each is
earned on its own line, and reads "T - 1" when earned and "T - 0" when not:
  T  lines 1 and 2: the system identified, two linear equations in the same two unknowns with
     coefficients extracted. One T for the pair, not one per equation.
  M  a subsequent correct step. Two or three typically: eliminating one unknown, solving for
     the remaining one, substituting back. Each declared M is earned independently, in order:
     the first on line 3, the second on line 4, and so on until the answer line. Method lines
     beyond the scheme's M marks must still be correct, but earn nothing.
     This question type needs at most STEPS_NEEDED steps. An M a scheme declares beyond those
     that no method line earned is not held against the student: it is awarded with a correct
     answer, and its reason says the scheme declares more steps than this question type needs.
     An M within those steps whose step never appears before the answer is lost, and with it,
     by the prefix rule, every mark after it, the answer included.
  A  both values stated, e.g. "x = 3, y = 2": the first line from line 4 on that states the
     value of each unknown, as plain numbers, with every line before it verified. Both correct
     or no mark.
  D  a concluding statement on a line after the answer. Checked by pattern, not by a model:
     the line must contain both values and one of CONCLUDING_WORDS, shared with the quadratic
     procedure; a value written "x = .." must be x's. Awarded only when A was earned.

Marking STOPS at the first incorrect step. Every mark from that point on is
zero, including marks that would otherwise follow from the student's own
working. This is deliberate, and stricter than UNEB follow-through marking,
which would credit later working done correctly from an earlier slip. A
correct final answer reached through incorrect working earns nothing. Lines
after the answer must each be a correct step or the conclusion.

Reading conventions: a label ending in ":" or "=>" at the start of a line ("(1) × 2:",
"eq1 + eq2 =>") is ignored, as is an equation label at the end of a line: "(1)" after dots,
dashes or two spaces ("...(1)"), since after one space it may be a multiplication ("8 - 2 (3)"),
except on lines 1 and 2, where it is always a label; a roman "(ii)" after any space. Decimals are accepted when correctly rounded to the places written; "or",
"and", "," and ";" separate the statements on a line; a line starting with "=" continues the
previous line.
"""

import re
import string
from dataclasses import dataclass, field
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
    mark_labels,
)

ELIMINATION = "elimination"
SUBSTITUTION = "substitution"

# Eliminating (or substituting for) one unknown, solving for the other, substituting back
STEPS_NEEDED = 3
_STEPS_IN_WORDS = (
    "eliminate or substitute for one unknown, solve for the other, and substitute back"
)

_ARROW_RE = re.compile(r"=>|⇒|→|->")
# An equation label at the end of a line: "(1)" or "[2]" after dots, dashes or two spaces, since
# after one space it may be a multiplication ("8 - 2 (3)"); a roman "(ii)" after any space.
# On lines 1 and 2, the given equations, a label after one space is read as a label too.
_EQUATION_LABEL_RE = re.compile(
    r"(?:(?:\s{2,}|\.{2,}|-{2,}|…)\s*[(\[]\s*\d{1,2}\s*[)\]]"
    r"|\s+[(\[]\s*(?:i{1,3}|iv|v)\s*[)\]])\s*$",
    re.IGNORECASE,
)
_GIVEN_LABEL_RE = re.compile(r"(?:\s|\.{2,}|-{2,}|…)\s*[(\[]\s*\d{1,2}\s*[)\]]\s*$")
_LABEL_RE = re.compile(
    r"^\s*(?:(?:solve|solutions?|therefore|hence|thus|so|the|answer|ans|values?|are|is)"
    r"\b\s*)+",
    re.IGNORECASE,
)
_BRACKET_RE = re.compile(r"\(([^()]*)\)")
_ALL_LETTERS = set(string.ascii_letters)


class _StepError(Exception):
    """The line is not a legitimate step; the message says why."""


@dataclass
class _System:
    unknowns: tuple[sympy.Symbol, sympy.Symbol]
    # Each equation as an expression equal to zero
    equations: tuple[sympy.Expr, sympy.Expr]
    solution: dict[sympy.Symbol, sympy.Expr]
    # A given equation already has an unknown as its subject, e.g. "y = 2x - 1"
    subject_given: bool

    def other(self, unknown: sympy.Symbol) -> sympy.Symbol:
        u, v = self.unknowns
        return v if unknown == u else u

    def answer(self) -> str:
        return ", ".join(f"{u} = {show(self.solution[u])}" for u in self.unknowns)


@dataclass
class _Clause:
    kind: str  # "value", "subject", "single", "combined", "given", "arithmetic"
    route: str | None = None
    # value and subject: the unknown on its own; single: the unknown remaining
    unknown: sympy.Symbol | None = None
    value: sympy.Expr | None = None
    final_text: str = ""
    # single: the other unknown's expression written in, in brackets
    substituted: bool = False


@dataclass
class _Line:
    route: str | None
    clauses: list[_Clause]
    values: dict[sympy.Symbol, tuple[sympy.Expr, str]] = field(default_factory=dict)
    tail: str = ""


def _normalise(line: str, given: bool = False) -> str:
    text = line
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = _ARROW_RE.sub(":", text)
    text = text.rsplit(":", 1)[-1]
    text = _EQUATION_LABEL_RE.sub("", text)
    if given:
        text = _GIVEN_LABEL_RE.sub("", text)
    text = _LABEL_RE.sub("", text)
    text = text.replace("*", " * ")
    return " ".join(text.split()).rstrip(".").strip()


def _parse(text: str, letters: set[str]) -> sympy.Expr:
    expr = parse_arithmetic(text, letters)
    if expr is None:
        raise _StepError(f"'{text}' could not be read as mathematics")
    return expr


def _linear(expr: sympy.Expr, unknowns: tuple[sympy.Symbol, ...]) -> sympy.Poly | None:
    try:
        polynomial = sympy.Poly(expr, *unknowns)
    except sympy.PolynomialError:
        return None
    return polynomial if polynomial.total_degree() <= 1 else None


def _coefficients(expr: sympy.Expr, unknowns: tuple[sympy.Symbol, sympy.Symbol]) -> list[sympy.Expr]:
    """[a, b, c] for the equation written as a*u + b*v = c."""
    u, v = unknowns
    expanded = sympy.expand(expr)
    return [expanded.coeff(u), expanded.coeff(v), -expanded.subs({u: 0, v: 0})]


def _read_given(line: str) -> tuple[sympy.Expr, bool]:
    """A given equation as an expression equal to zero, and whether it has an unknown as its subject."""
    text = _normalise(line, given=True)
    sides = text.split("=")
    if len(sides) != 2 or not all(side.strip() for side in sides):
        raise _StepError("is not a single linear equation")
    lhs, rhs = (_parse(side.strip(), _ALL_LETTERS) for side in sides)
    expr = sympy.expand(lhs - rhs)
    unknowns = tuple(sorted(expr.free_symbols, key=lambda s: s.name))
    if not unknowns:
        raise _StepError("has no unknowns")
    if len(unknowns) > 2:
        names = ", ".join(s.name for s in unknowns)
        raise _StepError(f"uses {names}: a system in two unknowns uses exactly two")
    if _linear(expr, unknowns) is None:
        raise _StepError("is not a linear equation")
    subject = any(
        side.is_Symbol and side not in other.free_symbols and other.free_symbols
        for side, other in ((lhs, rhs), (rhs, lhs))
    )
    return expr, subject


def _read_system(first: str, second: str) -> _System:
    """Raises _StepError with the line number (1 or 2) the problem is on as args[1]."""
    try:
        e1, subject1 = _read_given(first)
    except _StepError as error:
        raise _StepError(str(error), 1) from None
    try:
        e2, subject2 = _read_given(second)
    except _StepError as error:
        raise _StepError(str(error), 2) from None
    symbols = e1.free_symbols | e2.free_symbols
    if len(symbols) != 2:
        names = ", ".join(sorted(s.name for s in symbols))
        raise _StepError(
            f"is not in the same two unknowns as line 1: together they use {names}", 2
        )
    unknowns = tuple(sorted(symbols, key=lambda s: s.name))
    for number, expr in ((1, e1), (2, e2)):
        missing = [u.name for u in unknowns if u not in expr.free_symbols]
        if missing:
            raise _StepError(
                f"does not use {missing[0]}: each equation of the pair must use both unknowns",
                number,
            )
    (a1, b1, _), (a2, b2, _) = _coefficients(e1, unknowns), _coefficients(e2, unknowns)
    if sympy.simplify(a1 * b2 - a2 * b1) == 0:
        raise _StepError(
            "does not give a system with one solution: its coefficients are in proportion to "
            "line 1's",
            2,
        )
    (solution,) = sympy.solve([e1, e2], list(unknowns), dict=True)
    return _System(
        unknowns=unknowns,  # type: ignore[arg-type]
        equations=(e1, e2),
        solution=solution,
        subject_given=subject1 or subject2,
    )


def _describe_given(expr: sympy.Expr, system: _System) -> str:
    (u, v), (a, b, c) = system.unknowns, _coefficients(expr, system.unknowns)
    return f"{u} coefficient {show(a)}, {v} coefficient {show(b)}, constant {show(c)}"


def _restates_given(expr: sympy.Expr, system: _System) -> bool:
    """Whether the equation is a given one rearranged, not scaled: the same up to sign."""
    mine = _coefficients(expr, system.unknowns)
    for given in system.equations:
        theirs = _coefficients(given, system.unknowns)
        if all(sympy.expand(m - t) == 0 for m, t in zip(mine, theirs)) or all(
            sympy.expand(m + t) == 0 for m, t in zip(mine, theirs)
        ):
            return True
    return False


def _substitutes(text: str, remaining: sympy.Symbol, eliminated: sympy.Symbol) -> bool:
    """Whether the text has a bracketed expression in the remaining unknown, e.g. "(8 - 2x)"."""
    for group in _BRACKET_RE.findall(text):
        letters = set(re.findall(r"[A-Za-z]", group))
        if remaining.name in letters and eliminated.name not in letters and re.search(
            r"[+-]", group.strip()[1:]
        ):
            return True
    return False


def _read_clause(text: str, system: _System) -> _Clause:
    segments = [segment.strip() for segment in text.split("=")]
    if len(segments) == 1:
        raise _StepError(f"'{text}' is an expression on its own, not a step")
    if any(not segment for segment in segments):
        raise _StepError(f"'{text}' has nothing on one side of an equals sign")
    within = rounding_tolerance(text)
    letters = {u.name for u in system.unknowns}
    exprs = [_parse(segment, letters) for segment in segments]
    stray = set().union(*(e.free_symbols for e in exprs)) - set(system.unknowns)
    if stray:
        names = ", ".join(sorted(s.name for s in stray))
        raise _StepError(f"'{text}' uses {names}, which is not part of the system")

    stated: sympy.Expr | None = None
    for i in range(1, len(exprs)):
        where = f"'{segments[i - 1]} = {segments[i]}'"
        difference = sympy.expand(exprs[i - 1] - exprs[i])
        if _linear(difference, system.unknowns) is None:
            raise _StepError(f"{where} is not a linear equation")
        if not difference.free_symbols:
            if not equal(difference, 0, within):
                raise _StepError(f"{where} is false")
            continue
        if not equal(difference.subs(system.solution), 0, within):
            raise _StepError(f"{where} does not follow from the two equations")
        stated = stated if stated is not None else difference

    symbols = set().union(*(e.free_symbols for e in exprs))
    if not symbols:
        return _Clause(kind="arithmetic")
    if stated is None:
        raise _StepError(f"'{text}' states nothing: its sides are the same expression")

    for lone, rest, final in ((exprs[0], exprs[1:], segments[-1]), (exprs[-1], exprs[:-1], segments[0])):
        if lone not in system.unknowns:
            continue
        rest_symbols = set().union(*(e.free_symbols for e in rest))
        if not rest_symbols:
            return _Clause(kind="value", unknown=lone, value=system.solution[lone], final_text=final)
        if rest_symbols == {system.other(lone)}:
            return _Clause(kind="subject", route=SUBSTITUTION, unknown=lone)

    if len(symbols) == 1:
        (remaining,) = symbols
        return _Clause(
            kind="single",
            unknown=remaining,
            substituted=_substitutes(text, remaining, system.other(remaining)),
        )
    if _restates_given(stated, system):
        return _Clause(kind="given")
    return _Clause(kind="combined", route=ELIMINATION)


def _read_line(line: str, system: _System, previous_tail: str) -> _Line:
    text = _normalise(line)
    if text.startswith("=") and previous_tail:
        text = previous_tail + " " + text
    clauses = [_read_clause(part, system) for part in CLAUSE_SPLIT_RE.split(text) if part.strip()]
    if not clauses:
        raise _StepError("has no working on it")
    routes = {clause.route for clause in clauses} - {None}
    if len(routes) > 1:
        raise _StepError("mixes elimination with substitution")
    values = {
        clause.unknown: (clause.value, clause.final_text)
        for clause in clauses
        if clause.kind == "value" and clause.unknown is not None and clause.value is not None
    }
    return _Line(
        route=next(iter(routes), None),
        clauses=clauses,
        values=values,
        tail=text.split("=")[-1].strip(),
    )


def _opening_route(line: _Line, system: _System) -> str | None:
    """The route line 3 begins, or None when it fits neither."""
    if line.route is not None:
        return line.route
    singles = [clause for clause in line.clauses if clause.kind == "single"]
    if not singles:
        return None
    if system.subject_given or any(clause.substituted for clause in singles):
        return SUBSTITUTION
    return ELIMINATION


def _fits_neither(line: _Line) -> str:
    kinds = {clause.kind for clause in line.clauses}
    if "value" in kinds:
        return "states a value without first eliminating or substituting for an unknown"
    if "given" in kinds:
        return "copies out a given equation without starting elimination or substitution"
    return "does not begin elimination or substitution"


def _step_done(line: _Line, system: _System, route: str, found: set[sympy.Symbol]) -> str:
    """What a verified method line did, for its M's reason; found holds the unknowns whose
    values earlier lines stated."""
    by_kind = {clause.kind: clause for clause in reversed(line.clauses)}
    if "value" in by_kind:
        clause = by_kind["value"]
        return f"{clause.unknown} = {show(clause.value)} found"
    if "single" in by_kind and by_kind["single"].unknown is not None:
        remaining = by_kind["single"].unknown
        gone = system.other(remaining)
        if gone in found:
            return f"{gone}'s value substituted back"
        done = "substituted for" if route == SUBSTITUTION else "eliminated"
        return f"{gone} {done}, leaving an equation in {remaining}"
    if "subject" in by_kind:
        return f"{by_kind['subject'].unknown} made the subject"
    if "combined" in by_kind:
        return "equations scaled or combined"
    if "given" in by_kind:
        return "a given equation rearranged"
    return "arithmetic correct"


def _answer_problem(line: _Line, system: _System) -> str | None:
    """Why the line doesn't state both values, or None when it does."""
    missing = [u.name for u in system.unknowns if u not in line.values]
    if len(missing) == 2:
        return "does not state the values as " + ", ".join(f"{u} = .." for u in system.unknowns)
    if missing:
        return f"states one value, not both: {missing[0]} is missing"
    if not all(PLAIN_NUMBER_RE.match(text.replace(" ", "")) for _, text in line.values.values()):
        return "leaves a value as an unsimplified expression"
    return None


_NO_CONCLUDING_WORD = "has no concluding word"


def _conclusion_problem(line: str, system: _System) -> str | None:
    """Why the line isn't a concluding statement, or None when it is: it must hold a concluding
    word and both values, and a value written "x = .." must be x's."""
    if not CONCLUDING_RE.search(line.replace("∴", " therefore ")):
        return _NO_CONCLUDING_WORD
    # Prose is dropped; what's left is read clause by clause
    text = PROSE_RE.sub(";", _normalise(line))
    letters = {u.name for u in system.unknowns}
    named: set[sympy.Symbol] = set()
    bare: list[tuple[sympy.Expr, float]] = []
    for clause in CLAUSE_SPLIT_RE.split(text):
        # A chain like "x = 1/3 = y" gives its value to every unknown in it
        parsed = [
            (segment.strip(), parse_arithmetic(segment, letters))
            for segment in clause.split("=")
            if segment.strip()
        ]
        values = [(t, e) for t, e in parsed if e is not None and not e.free_symbols]
        if not values:
            continue
        value_text, value = values[-1]
        within = rounding_tolerance(value_text)
        unknowns = [e for _, e in parsed if e in system.unknowns]
        for unknown in unknowns:
            if not equal(value, system.solution[unknown], within):
                return f"gives {unknown} = {value_text}, which is not {unknown}'s value"
            named.add(unknown)
        if not unknowns:
            bare.append((value, within))
    missing = [
        u
        for u in system.unknowns
        if u not in named and not any(equal(v, system.solution[u], w) for v, w in bare)
    ]
    if missing:
        return "does not give the value of " + " or ".join(u.name for u in missing)
    return None


# A mark's (earned, reason, the 1-based number of the line its reason names, if any)
_Outcome = tuple[bool, str, int | None]


@register
class SimultaneousProcedure(Procedure):
    """Marks any pair of simultaneous linear equations line by line; see the module docstring."""

    name = "simultaneous"

    def default_marks(self) -> list[SchemeMark]:
        # The same as simultaneous-any
        return marks_of(FIRST_STEP_CODE, STEP_CODE, STEP_CODE, ANSWER_CODE, CONCLUSION_CODE)

    def grade(
        self, working: list[str], params: dict[str, Any], marks: list[SchemeMark]
    ) -> list[MarkAward]:
        if params:
            raise ValueError(
                f"simultaneous procedure has no parameter(s) {', '.join(sorted(params))}"
            )
        # None declared: the procedure's own
        marks = marks or self.default_marks()
        codes = [mark.id for mark in marks]
        check_mark_codes(codes, "simultaneous procedure scheme")
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
        labels = [label or code for label, code in zip(mark_labels(codes), codes)]
        step_marks = [i for i, code in enumerate(codes) if code == STEP_CODE]
        # M marks beyond the steps this question type needs
        surplus = set(step_marks[STEPS_NEEDED:])
        surplus_note = (
            f"The scheme declares {len(step_marks)} M marks, more steps than this question type "
            f"needs: simultaneous linear equations take at most {STEPS_NEEDED} ({_STEPS_IN_WORDS}), "
            "so this M stands for no step of the working."
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
            # Lines 1 and 2 failing leave no system to check an answer against
            if answer_lost and number > 2 and later_answer_is_correct(number):
                for i in [i for i, c in enumerate(codes) if c == ANSWER_CODE]:
                    earned, reason, line = outcomes[i] or (False, "", number)
                    outcomes[i] = (
                        earned,
                        f"{reason} A later line states the correct values, but a correct answer "
                        "reached through incorrect working earns nothing.",
                        line,
                    )
            return result()

        def later_answer_is_correct(number: int) -> bool:
            for line in lines[number:]:
                try:
                    if _answer_problem(_read_line(line, system, ""), system) is None:
                        return True
                except _StepError:
                    continue
            return False

        if len(lines) == 1:
            try:
                _read_given(lines[0])
            except _StepError as error:
                return stopped(1, str(error))
            fill(
                None,
                (False, f"Not awarded: {at(1)} is one equation; the system needs two, on lines 1 and 2.", 1),
            )
            return result()
        try:
            system = _read_system(lines[0], lines[1])
        except _StepError as error:
            why, number = error.args
            return stopped(number, why)
        u, v = system.unknowns
        fill(
            FIRST_STEP_CODE,
            (
                True,
                f"Lines 1 and 2 '{lines[0]}', '{lines[1]}': system in {u} and {v} identified; "
                f"line 1 {_describe_given(system.equations[0], system)}; "
                f"line 2 {_describe_given(system.equations[1], system)}.",
                # Lines 1 and 2 together earn it: the system is complete on line 2
                2,
            ),
        )

        if len(lines) == 2:
            fill(None, (False, "Not awarded: no working after the system on lines 1 and 2.", 2))
            return result()

        # Method lines, until the first line from line 4 on that states both values
        route: str | None = None
        found: set[sympy.Symbol] = set()
        tail = ""
        last: _Line | None = None
        answer_line: int | None = None
        for number in range(3, len(lines) + 1):
            try:
                last = _read_line(lines[number - 1], system, tail)
            except _StepError as error:
                return stopped(number, str(error))
            if number == 3:
                route = _opening_route(last, system)
                if route is None:
                    return stopped(number, _fits_neither(last))
            elif last.route is not None and last.route != route:
                return stopped(number, f"switches to {last.route} after line 3 began {route}")
            tail = last.tail
            if number >= 4 and _answer_problem(last, system) is None:
                answer_line = number
                break
            steps = unfilled(STEP_CODE)
            if steps:
                done = _step_done(last, system, route, found)
                outcomes[steps[0]] = (True, f"{at(number)}: correct {route} step, {done}.", number)
            found |= set(last.values)
        assert last is not None and route is not None

        if answer_line is None:
            final = at(len(lines))
            for i in surplus & set(unfilled(STEP_CODE)):
                outcomes[i] = (
                    False,
                    f"{surplus_note} It is awarded only with a correct answer, and {final} ends "
                    "the working without both values stated.",
                    len(lines),
                )
            fill(STEP_CODE, (False, f"Not awarded: no further {route} step after {final}.", len(lines)))
            problem = (
                _answer_problem(last, system)
                or "states both values on line 3, which begins the method; the answer comes after it"
            )
            fill(
                ANSWER_CODE,
                (
                    False,
                    f"Not awarded: every step is correct, but no line states both values, e.g. "
                    f"'{u} = .., {v} = ..'. {final} {problem}.",
                    len(lines),
                ),
            )
            fill(
                CONCLUSION_CODE,
                (
                    False,
                    "Not awarded: a concluding statement counts only once both values are stated correctly.",
                    None,
                ),
            )
            return result()

        answer_at = at(answer_line)
        skipped = [i for i in unfilled(STEP_CODE) if i not in surplus]
        if skipped:
            # A step the question needs never appeared; marks run in order, so nothing after it counts
            first = skipped[0]
            outcomes[first] = (
                False,
                f"Not awarded: {answer_at} states the answer, but no {labels[first]} step was shown "
                "before it.",
                answer_line,
            )
            fill(
                None,
                (
                    False,
                    f"Not awarded: the {labels[first]} was not earned, and marks are earned in order, "
                    f"so none is awarded after it. {answer_at} states the values, but the working "
                    "skips a step.",
                    answer_line,
                ),
            )
            return result()

        for i in unfilled(STEP_CODE):
            outcomes[i] = (
                True, f"{answer_at}: {surplus_note} It is awarded with the correct answer.", answer_line
            )
        fill(ANSWER_CODE, (True, f"{answer_at}: {system.answer()} stated, every step verified.", answer_line))

        if not unfilled(CONCLUSION_CODE):
            return result()
        # After the answer, each line is either the conclusion or another correct step
        for number in range(answer_line + 1, len(lines) + 1):
            line = lines[number - 1]
            problem = _conclusion_problem(line, system)
            if problem is None:
                fill(CONCLUSION_CODE, (True, f"{at(number)}: concluding statement giving both values.", number))
                return result()
            if problem != _NO_CONCLUDING_WORD:
                return stopped(number, problem)
            try:
                tail = _read_line(line, system, tail).tail
            except _StepError as error:
                return stopped(number, str(error))
        words = ", ".join(f"'{word}'" for word in CONCLUDING_WORDS)
        fill(
            CONCLUSION_CODE,
            (
                False,
                f"Not awarded: no concluding statement after the answer on line {answer_line}. "
                f"It must give both values with a concluding word ({words}).",
                answer_line,
            ),
        )
        return result()
