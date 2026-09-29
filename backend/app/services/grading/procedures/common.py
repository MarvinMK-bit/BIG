"""Reading and checking student working, shared by the procedures.

Student text reaches sympy's parse_expr, which evaluates Python, so every procedure parses
through parse_arithmetic here and nowhere else.
"""

import re
import string

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)

# A D line needs one of these, as a whole word, ignoring case. Extend the list as needed.
CONCLUDING_WORDS: tuple[str, ...] = (
    "root",
    "roots",
    "solution",
    "solutions",
    "therefore",
    "hence",
    "thus",
    "answer",
    "so",
)
CONCLUDING_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in CONCLUDING_WORDS) + r")\b", re.IGNORECASE
)
# Words in a conclusion that aren't mathematics: removed before its values are read
PROSE_RE = re.compile(r"[A-Za-z]{2,}")

STOP_NOTE = (
    "Marking stops at the first incorrect step: no later mark is awarded, even for "
    "working that follows correctly from it. This is stricter than UNEB "
    "follow-through marking."
)

# LaTeX and typed symbols, rewritten into what parse_arithmetic reads
REPLACEMENTS: tuple[tuple[str, str], ...] = (
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
# "or", "and", "," and ";" separate the statements on a line
CLAUSE_SPLIT_RE = re.compile(r"\s+(?:or|and)\s+|\s*[,;&]\s*", re.IGNORECASE)
PLAIN_NUMBER_RE = re.compile(r"^\(?[+-]?\d+(?:\.\d+)?(?:/\d+)?\)?$")
_DECIMAL_RE = re.compile(r"\d\.(\d+)")

# Arithmetic only reaches parse_expr
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
LETTERS: dict[str, sympy.Symbol] = {letter: sympy.Symbol(letter) for letter in string.ascii_letters}


def parse_arithmetic(text: str, allowed_letters: set[str]) -> sympy.Expr | None:
    """The expression written in text, or None when it can't be read safely as arithmetic in
    the allowed letters (and sqrt)."""
    compact = text.strip()
    if (
        not compact
        or len(compact) > _MAX_EXPRESSION_LENGTH
        or not _ALLOWED_RE.match(compact)
        or "**" in compact
        or compact.count("^") > _MAX_POWERS
        or len(_EXPONENT_RE.findall(compact)) != compact.count("^")
    ):
        return None
    for word in _WORD_RE.findall(compact):
        if word != "sqrt" and not set(word) <= allowed_letters:
            return None
    try:
        expr = parse_expr(compact, local_dict=dict(LETTERS), transformations=_TRANSFORMATIONS)
    except Exception:
        return None
    return expr if isinstance(expr, sympy.Expr) else None


def terms_of(text: str) -> list[str]:
    """The terms of an expression as written, split at each + or - outside brackets, each
    keeping its minus sign: "3x - 2(x + 1)" -> ["3x", "-2(x+1)"]."""
    terms: list[str] = []
    current = ""
    depth = 0
    previous = ""
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char in "+-" and depth == 0 and current.strip() and previous not in "*/^(":
            terms.append(current)
            current = "-" if char == "-" else ""
        else:
            current += char
        if not char.isspace():
            previous = char
    terms.append(current)
    return ["".join(term.split()) for term in terms if term.strip()]


def rounding_tolerance(text: str) -> float:
    """How far a value may be from the exact one: decimals are accepted when correctly rounded
    to the places written."""
    places = [len(match) for match in _DECIMAL_RE.findall(text)]
    return 0.5 * 10 ** -max(places) + 1e-9 if places else 0.0


def equal(u: sympy.Expr, v: sympy.Expr, within: float) -> bool:
    try:
        difference = complex(sympy.N(u - v, 30))
    except (TypeError, ValueError):
        return False
    return abs(difference) <= max(within, 1e-20)


def show(value: sympy.Expr) -> str:
    return sympy.sstr(sympy.nsimplify(value) if value.is_Float else value)
