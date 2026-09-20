import re
from dataclasses import dataclass

# "1." / "1)" / "3(a)" / "3(a)." / "3a." / "3a)". The trailing lookahead stops
# "56.5 apples" or "3rd." being read as question starts.
_QUESTION_RE = re.compile(
    r"""^\s*
    (?P<number>\d+)
    (?:
        \((?P<paren_sub>[A-Za-z]{1,4})\)[.)]?
      | (?P<bare_sub>[A-Za-z])[.)]
      | [.)]
    )
    (?=\s|$)
    """,
    re.VERBOSE,
)
_ANSWER_RE = re.compile(r"answer\s*:", re.IGNORECASE)
_PAGE_SEPARATOR_RE = re.compile(r"^\s*-{3,}\s*$")


@dataclass
class ParsedAnswer:
    number: str
    sub_part: str | None
    raw_answer: str


def parse_answers(markdown: str) -> list[ParsedAnswer]:
    """Parse OCR Markdown into one ParsedAnswer per question, in document order.

    The answer is whatever follows the first "Answer:" on any line belonging to
    the question. Questions without one get raw_answer "".
    """
    answers: list[ParsedAnswer] = []
    current: ParsedAnswer | None = None
    has_answer = False

    for line in markdown.splitlines():
        if _PAGE_SEPARATOR_RE.match(line):
            continue

        question = _QUESTION_RE.match(line)
        if question:
            current = ParsedAnswer(
                number=question["number"],
                sub_part=question["paren_sub"] or question["bare_sub"],
                raw_answer="",
            )
            answers.append(current)
            has_answer = False

        if current is None or has_answer:
            continue

        answer = _ANSWER_RE.search(line)
        if answer:
            current.raw_answer = line[answer.end() :].strip()
            has_answer = True

    return answers
