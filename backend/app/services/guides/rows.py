import re
from decimal import Decimal
from typing import TypedDict

# The review table's header, in order. build_guide_docx writes it; parse_guide_docx requires it.
GUIDE_TABLE_HEADER: tuple[str, ...] = ("Question", "Sub-part", "Answer", "Marks", "Matcher")

# Optional sign (OCR often emits the Unicode minus), then a plain or thousands-grouped number.
_NUMERIC_RE = re.compile(r"^[-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)?(?:\.\d+)?$")
_GROUPED_RE = re.compile(r"^[-+−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")


class GuideRow(TypedDict):
    question: str
    sub_part: str | None
    answer: str
    marks: Decimal
    matcher: str


def is_numeric_answer(answer: str) -> bool:
    text = answer.strip()
    return any(ch.isdigit() for ch in text) and _NUMERIC_RE.match(text) is not None


def default_matcher(answer: str) -> str:
    return "numeric" if is_numeric_answer(answer) else "exact"


def normalise_numeric(answer: str) -> str:
    """"−1,234.5" -> "-1234.5". Commas are only dropped when they group thousands."""
    text = answer.strip().replace("−", "-")
    return text.replace(",", "") if _GROUPED_RE.match(text) else text


def format_decimal(value: Decimal) -> str:
    """1 -> "1", 0.50 -> "0.5", never scientific notation."""
    if value == value.to_integral_value():
        return str(value.quantize(Decimal(1)))
    return format(value.normalize(), "f")
