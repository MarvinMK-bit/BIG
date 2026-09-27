"""Read a question paper's text straight out of a Word document, as Markdown. No OCR is involved.

python-docx's Paragraph.text drops two things a question paper depends on: equations (Office
Math, which it skips entirely) and automatic list numbering (the "1." or "(a)" Word draws but
does not store in the text). Both are recovered here, so the grader sees "Question 3(a)" and
"x^(2) + 5x + 6 = 0" rather than a bare "+ 5x + 6 = 0".
"""

import io
from collections.abc import Iterator
from dataclasses import dataclass

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml.etree import _Element

MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _m(tag: str) -> str:
    return f"{{{MATH_NS}}}{tag}"


# --- Equations ------------------------------------------------------------------------------


def _group(text: str) -> str:
    """Parenthesise a multi-character operand so "x^(n+1)" doesn't read as "x^n+1"."""
    return text if len(text) <= 1 else f"({text})"


def _math_child(element: _Element, tag: str) -> str:
    child = element.find(_m(tag))
    return _math_text(child) if child is not None else ""


def _math_prop(element: _Element, prop_tag: str, tag: str, default: str) -> str:
    node = element.find(f"{_m(prop_tag)}/{_m(tag)}")
    if node is None:
        return default
    # An explicitly empty value (m:val="") means no character, e.g. a one-sided delimiter
    return node.get(_m("val"), default)


def _math_text(element: _Element) -> str:
    """Office Math as plain linear text: a/b, x^(2), √(x), (a, b)."""
    tag = element.tag
    if tag == _m("t"):
        return element.text or ""
    if tag == _m("f"):
        return f"{_group(_math_child(element, 'num'))}/{_group(_math_child(element, 'den'))}"
    if tag == _m("sSup"):
        return f"{_math_child(element, 'e')}^{_group(_math_child(element, 'sup'))}"
    if tag == _m("sSub"):
        return f"{_math_child(element, 'e')}_{_group(_math_child(element, 'sub'))}"
    if tag == _m("sSubSup"):
        base, sub, sup = (_math_child(element, t) for t in ("e", "sub", "sup"))
        return f"{base}_{_group(sub)}^{_group(sup)}"
    if tag == _m("rad"):
        degree, body = _math_child(element, "deg"), _math_child(element, "e")
        return f"root({degree}, {body})" if degree else f"√{_group(body)}"
    if tag == _m("d"):
        begin = _math_prop(element, "dPr", "begChr", "(")
        end = _math_prop(element, "dPr", "endChr", ")")
        separator = _math_prop(element, "dPr", "sepChr", "|")
        parts = [_math_text(e) for e in element.findall(_m("e"))]
        return f"{begin}{separator.join(parts)}{end}"
    if tag == _m("nary"):
        operator = _math_prop(element, "naryPr", "chr", "∫")
        sub, sup, body = (_math_child(element, t) for t in ("sub", "sup", "e"))
        limits = (f"_{_group(sub)}" if sub else "") + (f"^{_group(sup)}" if sup else "")
        return f"{operator}{limits} {body}"
    if tag == _m("func"):
        return f"{_math_child(element, 'fName')}{_group(_math_child(element, 'e'))}"
    if tag.endswith("Pr"):
        return ""  # Properties (rPr, ctrlPr, fPr, ...) carry formatting, not text
    return "".join(_math_text(child) for child in element)


# --- Runs and paragraphs --------------------------------------------------------------------


def _inline_text(element: _Element) -> str:
    """A paragraph's visible text in document order, including equations and text boxes."""
    tag = element.tag
    if tag in (_m("oMath"), _m("oMathPara")):
        return f" {_math_text(element).strip()} "
    if tag == qn("w:t"):
        return element.text or ""
    if tag == qn("w:tab"):
        return "\t"
    if tag in (qn("w:br"), qn("w:cr")):
        return "\n"
    if tag in (qn("w:del"), qn("w:pPr"), qn("w:rPr"), qn("w:instrText")):
        return ""  # Deleted tracked changes, formatting, and field codes aren't what's shown
    return "".join(_inline_text(child) for child in element)


def _paragraph_text(paragraph: Paragraph) -> str:
    text = _inline_text(paragraph._p)
    # Tidy the spaces an inline equation adds, without touching intended line breaks
    return "\n".join(" ".join(line.split()) for line in text.split("\n")).strip()


# --- Automatic numbering --------------------------------------------------------------------


@dataclass
class _Level:
    start: int
    fmt: str
    text: str  # e.g. "%1." or "(%2)"


def _roman(n: int) -> str:
    numerals = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
        (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
    ]
    out = ""
    for value, numeral in numerals:
        while n >= value:
            out += numeral
            n -= value
    return out


def _letters(n: int) -> str:
    # Word repeats the letter past z: aa, bb, ...
    return chr(ord("a") + (n - 1) % 26) * ((n - 1) // 26 + 1)


def _format_number(n: int, fmt: str) -> str:
    if fmt == "lowerLetter":
        return _letters(n)
    if fmt == "upperLetter":
        return _letters(n).upper()
    if fmt == "lowerRoman":
        return _roman(n)
    if fmt == "upperRoman":
        return _roman(n).upper()
    if fmt in ("bullet", "none"):
        return ""
    return str(n)  # decimal, and anything unusual


class _Numbering:
    """Works out the label Word would draw for each numbered paragraph, in document order."""

    def __init__(self, document: DocumentObject) -> None:
        self.levels: dict[str, dict[int, _Level]] = {}
        self.counters: dict[str, dict[int, int]] = {}
        try:
            root = document.part.numbering_part.element
        except (KeyError, NotImplementedError, AttributeError):
            return  # No numbering part: nothing in the document is auto-numbered

        abstract: dict[str, dict[int, _Level]] = {}
        for node in root.findall(qn("w:abstractNum")):
            abstract[node.get(qn("w:abstractNumId"))] = {
                int(lvl.get(qn("w:ilvl"), "0")): self._level(lvl) for lvl in node.findall(qn("w:lvl"))
            }
        for num in root.findall(qn("w:num")):
            ref = num.find(qn("w:abstractNumId"))
            if ref is None:
                continue
            levels = dict(abstract.get(ref.get(qn("w:val")), {}))
            for override in num.findall(qn("w:lvlOverride")):
                ilvl = int(override.get(qn("w:ilvl"), "0"))
                start = override.find(qn("w:startOverride"))
                if start is not None and ilvl in levels:
                    base = levels[ilvl]
                    levels[ilvl] = _Level(int(start.get(qn("w:val"), base.start)), base.fmt, base.text)
            self.levels[num.get(qn("w:numId"))] = levels

    @staticmethod
    def _level(lvl: _Element) -> _Level:
        def val(tag: str, default: str) -> str:
            node = lvl.find(qn(tag))
            return node.get(qn("w:val"), default) if node is not None else default

        return _Level(int(val("w:start", "1")), val("w:numFmt", "decimal"), val("w:lvlText", "%1."))

    def label(self, paragraph: Paragraph) -> str | None:
        """The list label for this paragraph, advancing the count; None if it isn't numbered."""
        num_pr = paragraph._p.pPr.numPr if paragraph._p.pPr is not None else None
        if num_pr is None:
            # A list style can carry the numbering instead of the paragraph
            style = paragraph.style
            style_pr = style.element.pPr if style is not None and style.element is not None else None
            num_pr = style_pr.numPr if style_pr is not None else None
        if num_pr is None or num_pr.numId is None:
            return None
        num_id = str(num_pr.numId.val)
        ilvl = num_pr.ilvl.val if num_pr.ilvl is not None else 0
        levels = self.levels.get(num_id)
        if not levels or ilvl not in levels or num_id == "0":
            return None

        counters = self.counters.setdefault(num_id, {})
        counters[ilvl] = counters.get(ilvl, levels[ilvl].start - 1) + 1
        for deeper in [k for k in counters if k > ilvl]:
            del counters[deeper]  # A new 1. restarts its (a), (b)

        level = levels[ilvl]
        if level.fmt == "bullet":
            return "-"
        text = level.text
        for i in range(ilvl, -1, -1):
            if f"%{i + 1}" in text and i in levels:
                count = counters.get(i, levels[i].start)
                text = text.replace(f"%{i + 1}", _format_number(count, levels[i].fmt))
        return text.strip() or None


# --- Blocks ---------------------------------------------------------------------------------


def _table_markdown(table: Table) -> str:
    rows: list[str] = []
    for index, row in enumerate(table.rows):
        cells: list[str] = []
        seen: list[object] = []
        for cell in row.cells:
            # A merged cell appears once per grid column it spans; show it once
            if any(cell._tc is tc for tc in seen):
                continue
            seen.append(cell._tc)
            text = " ".join(_paragraph_text(p) for p in cell.paragraphs if _paragraph_text(p))
            cells.append(text.replace("|", "\\|").replace("\n", " "))
        rows.append("| " + " | ".join(cells) + " |")
        if index == 0:
            rows.append("|" + " --- |" * len(cells))
    return "\n".join(rows)


def _blocks(document: DocumentObject) -> Iterator[str]:
    numbering = _Numbering(document)
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            yield _table_markdown(block)
            continue
        text = _paragraph_text(block)
        label = numbering.label(block)
        if not text and not label:
            continue
        style = block.style.name if block.style is not None else ""
        if style.startswith("Heading ") and style[8:].isdigit():
            text = f"{'#' * min(int(style[8:]), 6)} {text}"
        elif style == "Title":
            text = f"# {text}"
        if label:
            text = f"{label} {text}".rstrip()
        yield text


def docx_to_markdown(file_bytes: bytes) -> str:
    """The document's text as Markdown, in reading order. Raises ValueError for an unreadable file."""
    try:
        document = Document(io.BytesIO(file_bytes))
    except Exception:
        # python-docx raises several unrelated types (zip, XML, missing part) for a bad file
        raise ValueError("This file isn't a readable Word document (.docx).") from None
    return "\n\n".join(_blocks(document))
