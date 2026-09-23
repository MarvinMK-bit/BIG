from decimal import Decimal, InvalidOperation
from typing import Any

import yaml

from app.services.grading.schemes import MarkScheme, parse_scheme
from app.services.guides.rows import GuideRow, format_decimal, normalise_numeric


def _yaml_number(value: Decimal) -> int | float | str:
    """Emit a plain YAML number where that round-trips exactly, else a string parse_scheme accepts."""
    if value == value.to_integral_value():
        return int(value)
    as_float = float(value)
    return as_float if Decimal(str(as_float)) == value else format_decimal(value)


def _question(row: GuideRow) -> dict[str, Any]:
    question: dict[str, Any] = {"number": row["question"]}
    if row["sub_part"]:
        question["sub_part"] = row["sub_part"]
    question["max_mark"] = _yaml_number(row["marks"])
    question["matcher"] = row["matcher"]
    question["answer"] = _numeric_answer(row["answer"]) if row["matcher"] == "numeric" else row["answer"]
    return question


def _numeric_answer(answer: str) -> int | float | str:
    """"1,234" -> 1234 as a YAML number. Anything non-numeric is left as text for parse_scheme
    to reject with a message naming the question."""
    text = normalise_numeric(answer)
    try:
        value = Decimal(text)
    except InvalidOperation:
        return text
    return _yaml_number(value) if value.is_finite() else text


def build_scheme_yaml(
    rows: list[GuideRow],
    *,
    name: str,
    version: str,
    subject: str,
    description: str | None,
) -> tuple[str, MarkScheme]:
    """Build scheme YAML (source: generated) from reviewed rows and validate it.

    Raises ValueError, via parse_scheme, if the result isn't a valid scheme.
    """
    data: dict[str, Any] = {
        "name": name,
        "version": version,
        "subject": subject,
        "source": "generated",
    }
    if description:
        data["description"] = description
    data["questions"] = [_question(row) for row in rows]

    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return text, parse_scheme(text)
