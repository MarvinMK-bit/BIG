import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any

# Thousands-grouped numbers are tried first so "1,234" is not read as "1".
# A sign only counts when it is not glued to a preceding word, so "x-5" reads as 5.
_NUMBER_RE = re.compile(
    r"(?:(?<![\w.])(?P<sign>[-+]))?"
    r"(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
)


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def _strip_leading_equals(text: str) -> str:
    text = text.strip()
    return text[1:] if text.startswith("=") else text


def match_exact(expected: str, actual: str) -> bool:
    return _normalise(_strip_leading_equals(expected)) == _normalise(_strip_leading_equals(actual))


def match_numeric(expected: Decimal, actual: str) -> bool:
    # OCR often emits the Unicode minus sign
    found = _NUMBER_RE.search(actual.replace("−", "-"))
    if found is None:
        return False
    value = Decimal((found["sign"] or "") + found["number"].replace(",", ""))
    return value == expected


MATCHERS: dict[str, Callable[[Any, str], bool]] = {
    "exact": match_exact,
    "numeric": match_numeric,
}
