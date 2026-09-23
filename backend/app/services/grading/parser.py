import re
from dataclasses import dataclass

# A question marker is a line holding nothing but the marker:
#   "1." / "1)" / "(1)" / "Item 1"
#   "3(a)" / "3(a)(ii)" / "3a", each optionally followed by "." or ")"
# Anything else on the line (e.g. "1. 56") means it isn't a marker, so answers
# like "56." or "3.5" are never read as question starts.
_MARKER_RE = re.compile(
    r"""^\s*
    (?:
        \((?P<paren_number>\d+)\)
      | (?:item\s+)?(?P<number>\d+)
        (?:
            \((?P<sub>[A-Za-z]{1,4})\)(?:\((?P<nested_sub>[A-Za-z]{1,4})\))?[.)]?
          | (?P<bare_sub>[A-Za-z])[.)]?
          | [.)]
        )
      | item\s+(?P<item_number>\d+)[.:]?
    )
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)
_ANSWER_RE = re.compile(r"^\s*answer\s*[:=]", re.IGNORECASE)
_LEADING_EQUALS_RE = re.compile(r"^=\s*")
_PAGE_SEPARATOR_RE = re.compile(r"^\s*-{3,}\s*$")


@dataclass
class ParsedAnswer:
    number: str
    sub_part: str | None
    raw_answer: str
    working: str = ""


def _match_marker(line: str) -> tuple[str, str | None] | None:
    match = _MARKER_RE.match(line)
    if match is None:
        return None
    number = match["paren_number"] or match["number"] or match["item_number"]
    if match["sub"] and match["nested_sub"]:
        return number, f"{match['sub']}({match['nested_sub']})"
    return number, match["sub"] or match["bare_sub"]


def _content_lines(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if not _PAGE_SEPARATOR_RE.match(line)]


def _strip_leading_equals(text: str) -> str:
    return _LEADING_EQUALS_RE.sub("", text.strip())


def _answer_from_block(lines: list[str]) -> str:
    """The text after the first "Answer:" / "Answer =" line, else the block's last non-empty line.

    A leading "=" is dropped, so a final working line "= 42" yields "42".
    """
    for line in lines:
        answer = _ANSWER_RE.match(line)
        if answer:
            return _strip_leading_equals(line[answer.end() :])
    for line in reversed(lines):
        if line.strip():
            return _strip_leading_equals(line)
    return ""


def has_question_markers(markdown: str) -> bool:
    return any(_match_marker(line) for line in _content_lines(markdown))


def parse_answers(markdown: str) -> list[ParsedAnswer]:
    """Parse OCR Markdown into one ParsedAnswer per question marker, in document order.

    Each question's block is every line after its marker up to the next marker.
    Text before the first marker is ignored. Returns [] when there are no
    markers; it never falls back to treating lines as questions.
    """
    answers: list[ParsedAnswer] = []
    blocks: list[list[str]] = []

    for line in _content_lines(markdown):
        marker = _match_marker(line)
        if marker:
            number, sub_part = marker
            answers.append(ParsedAnswer(number=number, sub_part=sub_part, raw_answer=""))
            blocks.append([])
        elif blocks:
            blocks[-1].append(line)

    for parsed, block in zip(answers, blocks):
        parsed.raw_answer = _answer_from_block(block)
        parsed.working = "\n".join(block).strip()

    return answers


def parse_lines_as_questions(markdown: str) -> list[ParsedAnswer]:
    """Opt-in fallback for unnumbered scripts: each non-empty line is one question, numbered from 1."""
    lines = [line.strip() for line in _content_lines(markdown) if line.strip()]
    return [
        ParsedAnswer(number=str(i), sub_part=None, raw_answer=line, working=line)
        for i, line in enumerate(lines, start=1)
    ]
