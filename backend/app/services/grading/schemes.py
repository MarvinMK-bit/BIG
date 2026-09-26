from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

# Matchers that compare a final answer; the guide import offers only these
VALID_MATCHERS: frozenset[str] = frozenset({"exact", "numeric"})
# Marks the student's working step by step through a named procedure instead of an answer
PROCEDURE_MATCHER = "procedure"
VALID_SOURCES: frozenset[str] = frozenset({"manual", "generated", "feedback-derived"})

# BIG's mark codes for procedure questions, in the order they must appear; see docs/MARK-CODES.md.
# A mark is declared by its code alone; the mark it earns is written after it: "T - 1", "T - 0".
FIRST_STEP_CODE = "T"
STEP_CODE = "M"
ANSWER_CODE = "A"
CONCLUSION_CODE = "D"
MARK_CODES: tuple[str, ...] = (FIRST_STEP_CODE, STEP_CODE, ANSWER_CODE, CONCLUSION_CODE)
MAX_STEP_MARKS = 4
# What each code is for, in words that give away nothing about any particular question
MARK_CODE_MEANINGS: dict[str, str] = {
    FIRST_STEP_CODE: "a correct first step",
    STEP_CODE: "a subsequent correct step",
    ANSWER_CODE: "the answer stated",
    CONCLUSION_CODE: "a concluding statement",
}
_ORDINALS = ("first", "second", "third", "fourth")

_SCHEME_SUFFIXES = (".yaml", ".yml")


@dataclass
class SchemeMark:
    id: str
    description: str
    max_mark: Decimal = Decimal(1)


@dataclass
class SchemeQuestion:
    number: str
    max_mark: Decimal
    matcher: str
    # None only for the procedure matcher, which marks working rather than an answer
    answer: str | Decimal | None = None
    sub_part: str | None = None
    procedure: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    marks: list[SchemeMark] = field(default_factory=list)


@dataclass
class MarkScheme:
    name: str
    version: str
    subject: str
    source: str
    description: str | None
    questions: list[SchemeQuestion]
    # Set for schemes loaded from a repo file; None for schemes parsed from uploaded text
    path: Path | None = None

    @property
    def scheme_version(self) -> str:
        return f"{self.name}@{self.version}"


def _to_decimal(value: Any, where: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{where} must be a number, got {value!r}")
    try:
        # str() keeps floats like 0.1 exact rather than expanding their binary value
        result = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError(f"{where} must be a number, got {value!r}") from None
    if not result.is_finite():
        raise ValueError(f"{where} must be a finite number, got {value!r}")
    return result


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise ValueError(f"{where} is missing required field {key!r}")
    return mapping[key]


def _require_str(mapping: dict[str, Any], key: str, where: str) -> str:
    value = _require(mapping, key, where)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{where} field {key!r} must be a non-empty string (quote it in YAML), got {value!r}"
        )
    return value


def _parse_mark(raw: Any, index: int, where: str) -> SchemeMark:
    if not isinstance(raw, dict):
        raise ValueError(f"{where} mark #{index} must be a mapping, got {type(raw).__name__}")
    mark_id = _require_str(raw, "id", f"{where} mark #{index}")
    where = f"{where} mark {mark_id!r}"
    description = _require_str(raw, "description", where)
    max_mark = Decimal(1)
    if raw.get("max_mark") is not None:
        max_mark = _to_decimal(raw["max_mark"], f"{where} field 'max_mark'")
        if max_mark <= 0:
            raise ValueError(f"{where} field 'max_mark' must be greater than zero, got {max_mark}")
    return SchemeMark(id=mark_id, description=description, max_mark=max_mark)


def check_mark_codes(codes: list[str], where: str) -> None:
    """A procedure question's marks: T first and once, then 1 to MAX_STEP_MARKS M, then at most one
    A, then at most one D. Raises ValueError naming the rule that was broken."""
    for code in codes:
        if code not in MARK_CODES:
            raise ValueError(
                f"{where} has unknown mark code {code!r}. Procedure questions use BIG's mark codes: "
                f"{', '.join(MARK_CODES)}"
            )
    if not codes or codes[0] != FIRST_STEP_CODE:
        raise ValueError(f"{where} must start with {FIRST_STEP_CODE}, the correct first step")
    if codes.count(FIRST_STEP_CODE) != 1:
        raise ValueError(f"{where} must have exactly one {FIRST_STEP_CODE}")
    steps = codes.count(STEP_CODE)
    if not 1 <= steps <= MAX_STEP_MARKS:
        raise ValueError(
            f"{where} must have between 1 and {MAX_STEP_MARKS} {STEP_CODE} marks, got {steps}"
        )
    for code in (ANSWER_CODE, CONCLUSION_CODE):
        if codes.count(code) > 1:
            raise ValueError(f"{where} may have at most one {code}")
    for before, after in zip(codes, codes[1:]):
        if MARK_CODES.index(after) < MARK_CODES.index(before):
            raise ValueError(
                f"{where} has {after} after {before}: marks must run in the order "
                f"{' then '.join(MARK_CODES)}"
            )


def format_award(code: str, awarded: Decimal) -> str:
    """How a mark reads once marked: its code, then the mark it earned. "T - 1", "M - 0"."""
    return f"{code} - {awarded.normalize():f}"


def mark_labels(codes: list[str]) -> list[str | None]:
    """Tells repeated codes apart by position for output, e.g. "second M"; None where a code
    appears once. The codes themselves are never renamed."""
    seen: dict[str, int] = {}
    labels: list[str | None] = []
    for code in codes:
        index = seen.get(code, 0)
        seen[code] = index + 1
        labels.append(f"{_ORDINALS[index]} {code}" if codes.count(code) > 1 else None)
    return labels


def _parse_procedure_fields(
    raw: dict[str, Any], max_mark: Decimal, where: str
) -> tuple[str, dict[str, Any], list[SchemeMark]]:
    procedure = _require_str(raw, "procedure", where)

    params = raw.get("params")
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        raise ValueError(f"{where} field 'params' must be a mapping, got {params!r}")

    raw_marks = _require(raw, "marks", where)
    if not isinstance(raw_marks, list) or not raw_marks:
        raise ValueError(f"{where} field 'marks' must be a non-empty list")
    marks = [_parse_mark(item, i, where) for i, item in enumerate(raw_marks, start=1)]

    check_mark_codes([mark.id for mark in marks], where)

    total = sum((mark.max_mark for mark in marks), Decimal(0))
    if total != max_mark:
        raise ValueError(
            f"{where} field 'max_mark' is {max_mark} but its marks add up to {total}"
        )
    return procedure, params, marks


def _parse_question(raw: Any, index: int) -> SchemeQuestion:
    where = f"question #{index}"
    if not isinstance(raw, dict):
        raise ValueError(f"{where} must be a mapping, got {type(raw).__name__}")

    number = _require_str(raw, "number", where)
    where = f"question {number!r}"

    sub_part: str | None = None
    if raw.get("sub_part") is not None:
        sub_part = _require_str(raw, "sub_part", where)
        where = f"question {number!r} part {sub_part!r}"

    matcher = _require_str(raw, "matcher", where)
    if matcher not in VALID_MATCHERS and matcher != PROCEDURE_MATCHER:
        valid = ", ".join(sorted(VALID_MATCHERS | {PROCEDURE_MATCHER}))
        raise ValueError(f"{where} has unknown matcher {matcher!r}. Valid matchers: {valid}")

    max_mark = _to_decimal(_require(raw, "max_mark", where), f"{where} field 'max_mark'")
    if max_mark <= 0:
        raise ValueError(f"{where} field 'max_mark' must be greater than zero, got {max_mark}")

    if matcher == PROCEDURE_MATCHER:
        procedure, params, marks = _parse_procedure_fields(raw, max_mark, where)
        return SchemeQuestion(
            number=number,
            max_mark=max_mark,
            matcher=matcher,
            sub_part=sub_part,
            procedure=procedure,
            params=params,
            marks=marks,
        )

    raw_answer = _require(raw, "answer", where)
    answer: str | Decimal
    if matcher == "numeric":
        answer = _to_decimal(raw_answer, f"{where} field 'answer' (numeric matcher)")
    elif isinstance(raw_answer, str):
        answer = raw_answer
    else:
        answer = _to_decimal(raw_answer, f"{where} field 'answer'")

    return SchemeQuestion(
        number=number, max_mark=max_mark, matcher=matcher, answer=answer, sub_part=sub_part
    )


def parse_scheme(yaml_text: str) -> MarkScheme:
    """Parse and validate a mark scheme from YAML text. Raises ValueError on any problem."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("top level must be a mapping")

    name = _require_str(data, "name", "scheme")
    version = _require_str(data, "version", "scheme")
    subject = _require_str(data, "subject", "scheme")
    source = _require_str(data, "source", "scheme")
    if source not in VALID_SOURCES:
        raise ValueError(
            f"scheme has unknown source {source!r}. Valid sources: {', '.join(sorted(VALID_SOURCES))}"
        )

    description = data.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"scheme field 'description' must be a string, got {description!r}")

    raw_questions = _require(data, "questions", "scheme")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("scheme field 'questions' must be a non-empty list")

    questions: list[SchemeQuestion] = []
    seen: set[tuple[str, str | None]] = set()
    for index, raw in enumerate(raw_questions, start=1):
        question = _parse_question(raw, index)
        key = (question.number, question.sub_part)
        if key in seen:
            label = question.number + (f" part {question.sub_part}" if question.sub_part else "")
            raise ValueError(f"duplicate question number {label!r}")
        seen.add(key)
        questions.append(question)

    return MarkScheme(
        name=name,
        version=version,
        subject=subject,
        source=source,
        description=description,
        questions=questions,
    )


def load_scheme(path: Path) -> MarkScheme:
    try:
        scheme = parse_scheme(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc
    scheme.path = path
    return scheme


def load_all_schemes(directory: Path) -> dict[str, MarkScheme]:
    schemes: dict[str, MarkScheme] = {}
    paths = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix in _SCHEME_SUFFIXES)

    for path in paths:
        scheme = load_scheme(path)
        if scheme.scheme_version in schemes:
            raise ValueError(f"{path}: duplicate scheme version {scheme.scheme_version!r}")
        schemes[scheme.scheme_version] = scheme

    return schemes
