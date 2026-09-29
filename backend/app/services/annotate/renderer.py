"""The student's script with its marks drawn beside it, in a white margin added on the right.

The page itself is copied, never drawn on: every mark, score and note goes in the added margin, so
nothing covers the student's work.
"""

import io
import math
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from app.services.annotate.lines import TextBand, detect_text_bands, load_page
from app.services.grading.parser import ink_line_indices

Style = Literal["symbols", "codes"]
Placement = Literal["lines", "margin"]

SUPPORTED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")

# The added margin, as a fraction of the page width
MARGIN_FRACTION = 0.22
# The rendered page's longer side is at most this many pixels, which keeps a phone photo's PNG
# to a size a browser shows without a wait
MAX_PAGE_SIZE = 2000

_FONTS = Path(__file__).parent / "fonts"
_REGULAR = _FONTS / "DejaVuSans.ttf"
_BOLD = _FONTS / "DejaVuSans-Bold.ttf"

_WHITE = (255, 255, 255)
_GREEN = (22, 128, 61)
_RED = (200, 30, 30)
_AMBER = (180, 110, 0)
_GREY = (110, 110, 110)
_RULE = (215, 215, 215)


@dataclass
class MarkAnnotation:
    code: str
    awarded: float
    max_mark: float
    # The OCR markdown line (index into its splitlines()) that earned or lost the mark, if known
    line_index: int | None = None


@dataclass
class QuestionAnnotation:
    label: str
    mark_awarded: float
    max_mark: float
    marks: list[MarkAnnotation]
    # Where the question's answer sits in the OCR markdown, for marks with no line of their own;
    # None when the question wasn't found on the script
    line_index: int | None = None


@dataclass
class ScriptAnnotations:
    questions: list[QuestionAnnotation]
    ocr_markdown: str
    marked_on: date
    scheme_version: str | None = None
    total_awarded: float = field(init=False)
    total_max: float = field(init=False)

    def __post_init__(self) -> None:
        self.total_awarded = sum(q.mark_awarded for q in self.questions)
        self.total_max = sum(q.max_mark for q in self.questions)


@cache
def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_BOLD if bold else _REGULAR), size)


def _number(value: float) -> str:
    """2.0 as "2", 1.5 as "1.5"."""
    return f"{value:g}"


def _colour(awarded: float, max_mark: float) -> tuple[int, int, int]:
    if awarded <= 0:
        return _RED
    return _GREEN if awarded >= max_mark else _AMBER


# One thing drawn in the margin: a question's marks on one row of the page, or its score
@dataclass
class _Item:
    kind: Literal["marks", "score"]
    # The y, in pixels, the item goes at if nothing is in the way: its centre, or with
    # anchor "top" its top
    target: float
    anchor: Literal["centre", "top"] = "centre"
    marks: list[MarkAnnotation] = field(default_factory=list)
    text: str = ""
    height: float = 0.0
    top: float = 0.0


class _Canvas:
    """Sizes and fonts for the margin, scaled to the page."""

    def __init__(self, page_width: int, unit: int) -> None:
        self.margin = max(1, round(page_width * MARGIN_FRACTION))
        self.unit = unit
        self.pad = max(4, unit // 3)
        self.gap = max(2, unit // 4)
        self.left = page_width + self.pad
        self.right = page_width + self.margin - self.pad
        self.mark_font = _font(True, max(10, round(unit * 0.8)))
        self.score_font = _font(False, max(10, round(unit * 0.8)))
        self.total_font = _font(True, max(12, round(unit * 1.1)))
        self.footer_font = _font(False, max(10, round(unit * 0.5)))
        self._scratch = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def text_size(self, text: str, font: ImageFont.FreeTypeFont) -> tuple[float, float]:
        left, top, right, bottom = self._scratch.textbbox((0, 0), text, font=font)
        return right - left, bottom - top

    def glyphs(self, mark: MarkAnnotation, style: Style) -> list[tuple[str, float]]:
        """What a mark is drawn as, each with its width: a tick per mark awarded and a cross
        per mark not, or its code and what it earned."""
        if style == "codes":
            text = f"{mark.code} - {_number(mark.awarded)}"
            return [(text, self.text_size(text, self.mark_font)[0])]
        worth = max(1, round(mark.max_mark))
        ticks = min(worth, math.floor(mark.awarded + 1e-9))
        return [("tick", float(self.unit))] * ticks + [("cross", float(self.unit))] * (worth - ticks)

    def spacing(self, style: Style) -> float:
        """Space between two glyphs on a row: codes need more than ticks to read apart."""
        return self.unit * 0.7 if style == "codes" else float(self.gap)

    def rows_of(
        self, marks: list[MarkAnnotation], style: Style
    ) -> list[list[tuple[MarkAnnotation, str, float]]]:
        """The marks' glyphs, wrapped into rows that fit across the margin."""
        rows: list[list[tuple[MarkAnnotation, str, float]]] = [[]]
        used = 0.0
        for mark in marks:
            for glyph, width in self.glyphs(mark, style):
                if rows[-1] and used + width > self.right - self.left:
                    rows.append([])
                    used = 0.0
                rows[-1].append((mark, glyph, width))
                used += width + self.spacing(style)
        return rows

    def measure(self, item: _Item, style: Style) -> None:
        if item.kind == "marks":
            rows = len(self.rows_of(item.marks, style))
            item.height = rows * self.unit + (rows - 1) * self.gap
        else:
            item.height = self.text_size(item.text, self.score_font)[1]

    def footer_lines(self, parts: list[str]) -> list[str]:
        """The footer on one line when it fits across the margin, else a line per part."""
        joined = " · ".join(parts)
        if self.text_size(joined, self.footer_font)[0] <= self.right - self.left:
            return [joined]
        return parts


def _layout(items: list[_Item], top: float, limit: float, gap: float) -> None:
    """Place items down the margin in order, each at its target where it fits, else just below
    the one before, and none below limit: when they run past it, they are packed upwards from
    it, still in order. Only when there are too many to fit between top and limit do any rise
    above top."""
    bottom = top
    for item in items:
        wanted = item.target - item.height / 2 if item.anchor == "centre" else item.target
        item.top = max(wanted, bottom)
        bottom = item.top + item.height + gap
    ceiling = limit
    for item in reversed(items):
        if item.top + item.height <= ceiling:
            break
        item.top = ceiling - item.height
        ceiling = item.top - gap


def _score(question: QuestionAnnotation) -> _Item:
    # Anchored at the top with no target of its own: it sits just under the question's marks
    return _Item(
        kind="score",
        target=0.0,
        anchor="top",
        text=f"{_number(question.mark_awarded)}/{_number(question.max_mark)}",
    )


def _alignment_cost(bands: list[TextBand], lengths: list[int]) -> float:
    """How far the bands' ink is from the lines' lengths, paired in order: a longer line of
    writing puts more ink in its row. Both are scaled to their mean, so only proportions count."""
    ink = [band.density for band in bands]
    ink_mean = sum(ink) / len(ink) or 1.0
    length_mean = sum(lengths) / len(lengths) or 1.0
    return sum(abs(d / ink_mean - n / length_mean) for d, n in zip(ink, lengths))


def band_for_lines(bands: list[TextBand], line_texts: list[str]) -> list[int]:
    """The band each line of writing sits in, in order: one band per line when the counts
    match. When there is one band too few (a line too faint or short to find) or one too many
    (a smudge or a heading OCR left out), the missing line or the extra band is the one whose
    removal best lines up the bands' ink with the lines' lengths, earliest on a tie."""
    lengths = [len(text.strip()) for text in line_texts]
    if len(bands) == len(lengths):
        return list(range(len(lengths)))
    if len(bands) == len(lengths) - 1:
        # Line k has no band of its own; it shares the band of the line before it (or after, for the first)
        best = min(
            range(len(lengths)), key=lambda k: (_alignment_cost(bands, lengths[:k] + lengths[k + 1 :]), k)
        )
        return [i if i < best else max(i - 1, 0) for i in range(len(lengths))]
    if len(bands) == len(lengths) + 1:
        best = min(range(len(bands)), key=lambda k: (_alignment_cost(bands[:k] + bands[k + 1 :], lengths), k))
        return [i if i < best else i + 1 for i in range(len(lengths))]
    raise ValueError(f"{len(bands)} bands can't be matched to {len(lengths)} lines")


def _line_items(annotations: ScriptAnnotations, bands: list[TextBand], page_height: int) -> list[_Item]:
    """Each question's marks beside the band of the line that earned them, then its score.

    The OCR text's lines of writing are matched to the bands in order (band_for_lines). A mark with no line of
    its own goes beside its question's answer; a question not found on the script follows the
    question before it."""
    markdown_lines = annotations.ocr_markdown.splitlines()
    ink_lines = ink_line_indices(annotations.ocr_markdown)
    bands_of_lines = band_for_lines(bands, [markdown_lines[index] for index in ink_lines])
    band_by_line = dict(zip(ink_lines, bands_of_lines))

    def band_of(line_index: int | None) -> int | None:
        return None if line_index is None else band_by_line.get(line_index)

    def centre(band: int) -> float:
        return (bands[band].top + bands[band].bottom) / 2 * page_height

    groups: list[tuple[float, list[_Item]]] = []
    previous = 0.0
    for question in annotations.questions:
        by_band: dict[int, list[MarkAnnotation]] = {}
        unplaced: list[MarkAnnotation] = []
        for mark in question.marks:
            band = band_of(mark.line_index)
            if band is None:
                band = band_of(question.line_index)
            if band is None:
                unplaced.append(mark)
            else:
                by_band.setdefault(band, []).append(mark)
        items = [_Item(kind="marks", target=centre(band), marks=by_band[band]) for band in sorted(by_band)]
        if unplaced or not items:
            after = items[-1].target if items else previous
            items.append(_Item(kind="marks", target=after, anchor="top", marks=unplaced))
        items.append(_score(question))
        groups.append((items[0].target, items))
        previous = items[-2].target
    # Down the page in the order each question's first mark appears; sorted() is stable, so
    # questions at the same height keep the scheme's order
    groups.sort(key=lambda group: group[0])
    return [item for _, items in groups for item in items]


def _margin_items(annotations: ScriptAnnotations, page_height: int, top: float) -> list[_Item]:
    """The page divided into equal bands, one per question in order, each holding its marks and score."""
    band = (page_height - top) / max(1, len(annotations.questions))
    items: list[_Item] = []
    for i, question in enumerate(annotations.questions):
        items.append(_Item(kind="marks", target=top + i * band, anchor="top", marks=question.marks))
        items.append(_score(question))
    return items


def _draw_tick(draw: ImageDraw.ImageDraw, x: float, y: float, size: float) -> None:
    width = max(2, round(size / 7))
    points = [(x + 0.1 * size, y + 0.55 * size), (x + 0.4 * size, y + 0.85 * size), (x + 0.9 * size, y + 0.15 * size)]
    draw.line(points, fill=_GREEN, width=width, joint="curve")


def _draw_cross(draw: ImageDraw.ImageDraw, x: float, y: float, size: float) -> None:
    width = max(2, round(size / 7))
    draw.line([(x + 0.2 * size, y + 0.2 * size), (x + 0.8 * size, y + 0.8 * size)], fill=_RED, width=width)
    draw.line([(x + 0.8 * size, y + 0.2 * size), (x + 0.2 * size, y + 0.8 * size)], fill=_RED, width=width)


def _unit_for(page_height: int, margin: int, bands: list[TextBand] | None) -> int:
    """The size of a tick, in pixels: about a line of writing high, and small enough that
    several fit across the margin."""
    if bands:
        typical = sorted((b.bottom - b.top) * page_height for b in bands)[len(bands) // 2]
        size = min(max(typical * 0.8, page_height * 0.012), page_height * 0.03)
    else:
        size = page_height * 0.022
    return max(12, round(min(size, margin / 5)))


def _prepare_page(image_bytes: bytes, mime_type: str) -> Image.Image:
    if mime_type == "application/pdf":
        raise NotImplementedError("Annotated scripts can't be made from a PDF (application/pdf) yet")
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(f"Can't annotate a script of type {mime_type!r}")
    page = load_page(image_bytes)
    if page.mode != "RGB":
        rgba = page.convert("RGBA")
        backdrop = Image.new("RGBA", rgba.size, (*_WHITE, 255))
        page = Image.alpha_composite(backdrop, rgba).convert("RGB")
    scale = MAX_PAGE_SIZE / max(page.size)
    if scale < 1:
        page = page.resize(
            (max(1, round(page.width * scale)), max(1, round(page.height * scale))),
            Image.Resampling.LANCZOS,
        )
    return page


def registration_inset(width: int, height: int) -> tuple[int, int]:
    """Where the corner registration crosses sit: their centre's inset from each edge, and the
    length of each arm, in pixels."""
    side = min(width, height)
    return max(8, round(side * 0.03)), max(5, round(side * 0.018))


@dataclass
class MarkPlan:
    """Where everything goes, in the annotated image's coordinates: the page at the left, the
    margin column from page_width to page_width + canvas.margin."""

    page: Image.Image
    canvas: _Canvas
    items: list[_Item]
    total_text: str
    footer: list[str]
    footer_line: float
    footer_height: float
    placement: Placement
    # Whether every item lies between the top reserve and the total; and the fraction of the
    # items' height that room holds
    fits: bool = True
    fits_ratio: float = 1.0


def plan_marks(
    image_bytes: bytes, mime_type: str, annotations: ScriptAnnotations, style: Style, placement: Placement
) -> MarkPlan:
    page = _prepare_page(image_bytes, mime_type)
    width, height = page.size

    used: Placement = placement
    bands: list[TextBand] | None = None
    if placement == "lines":
        found = detect_text_bands(image_bytes)
        lines = ink_line_indices(annotations.ocr_markdown)
        if found and lines and abs(len(found) - len(lines)) <= 1:
            bands = found
        else:
            used = "margin"

    unit = _unit_for(height, max(1, round(width * MARGIN_FRACTION)), bands)
    while True:
        plan = _plan_at(page, annotations, style, used, bands, unit)
        if plan.fits or unit <= _MIN_UNIT:
            return plan
        # Everything must fit on the page, which the mask can't grow past: smaller marks, same order
        unit = max(_MIN_UNIT, min(unit - 1, math.floor(unit * plan.fits_ratio)))


# The smallest tick, in pixels, marks shrink to so that a long script's marks fit the page
_MIN_UNIT = 6


def _plan_at(
    page: Image.Image,
    annotations: ScriptAnnotations,
    style: Style,
    used: Placement,
    bands: list[TextBand] | None,
    unit: int,
) -> MarkPlan:
    width, height = page.size
    canvas = _Canvas(width, unit)
    # Clear of the corner registration crosses, so the mask and the annotated image match
    inset, arm = registration_inset(width, height)
    reserved = max(float(canvas.pad), inset + arm + canvas.gap)

    total_text = f"Total {_number(annotations.total_awarded)}/{_number(annotations.total_max)}"
    footer_parts = ["Marked by BIG", annotations.marked_on.isoformat()]
    if annotations.scheme_version:
        footer_parts.append(f"Scheme {annotations.scheme_version}")
    footer = canvas.footer_lines(footer_parts)
    total_height = canvas.text_size(total_text, canvas.total_font)[1]
    footer_line = canvas.text_size("Mg", canvas.footer_font)[1]
    footer_height = len(footer) * footer_line + (len(footer) - 1) * canvas.gap

    items = (
        _line_items(annotations, bands, height) if bands else _margin_items(annotations, height, reserved)
    )
    for item in items:
        canvas.measure(item, style)
    # Marks stop above the total and footer, which sit above the bottom corner crosses
    limit = height - reserved - footer_height - canvas.gap - total_height - canvas.gap
    _layout(items, reserved, limit, canvas.gap)
    needed = sum(item.height for item in items) + canvas.gap * max(0, len(items) - 1)
    return MarkPlan(
        fits=not items or items[0].top >= reserved,
        fits_ratio=(limit - reserved) / needed if needed else 1.0,
        page=page,
        canvas=canvas,
        items=items,
        total_text=total_text,
        footer=footer,
        footer_line=footer_line,
        footer_height=footer_height,
        placement=used,
    )


def draw_marks(draw: ImageDraw.ImageDraw, plan: MarkPlan, style: Style, dx: float = 0.0) -> None:
    """Every mark, score, the total and the footer, shifted dx pixels across from where the
    annotated image has them."""
    canvas = plan.canvas
    left, right = canvas.left + dx, canvas.right + dx
    for item in plan.items:
        if item.kind == "score":
            draw.text((left, item.top), item.text, fill=_GREY, font=canvas.score_font, anchor="lt")
            continue
        y = item.top
        for row in canvas.rows_of(item.marks, style):
            x = left
            for mark, glyph, glyph_width in row:
                if glyph == "tick":
                    _draw_tick(draw, x, y, canvas.unit)
                elif glyph == "cross":
                    _draw_cross(draw, x, y, canvas.unit)
                else:
                    colour = _colour(mark.awarded, mark.max_mark)
                    draw.text((x, y + canvas.unit / 2), glyph, fill=colour, font=canvas.mark_font, anchor="lm")
                x += glyph_width + canvas.spacing(style)
            y += canvas.unit + canvas.gap

    width, height = plan.page.size
    inset, arm = registration_inset(width, height)
    y = height - max(float(canvas.pad), inset + arm + canvas.gap) - plan.footer_height
    draw.text((right, y - canvas.gap), plan.total_text, fill=(0, 0, 0), font=canvas.total_font, anchor="rb")
    for line in plan.footer:
        draw.text((right, y), line, fill=_GREY, font=canvas.footer_font, anchor="rt")
        y += plan.footer_line + canvas.gap


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


def render_annotated_script(
    image_bytes: bytes,
    mime_type: str,
    annotations: ScriptAnnotations,
    style: Style = "symbols",
    placement: Placement = "lines",
) -> tuple[bytes, Placement]:
    """The script as a PNG with its marks in a margin 22% of the page's width added on the
    right, and the placement actually used.

    placement "lines" puts each mark beside the row of writing that earned it, when the rows
    found on the image (detect_text_bands) are within one of the OCR text's lines in number;
    otherwise it falls back to "margin" and says so in the placement returned. "margin" divides
    the page into equal bands, one per question in order.

    style "symbols" draws a green tick per mark awarded and a red cross per mark not; "codes"
    writes each mark's code and what it earned, "T - 1", green when awarded and red when not.

    JPEG, PNG and WebP scripts only: a PDF raises NotImplementedError.
    """
    plan = plan_marks(image_bytes, mime_type, annotations, style, placement)
    width, height = plan.page.size
    out = Image.new("RGB", (width + plan.canvas.margin, height), _WHITE)
    out.paste(plan.page, (0, 0))
    draw = ImageDraw.Draw(out)
    draw.line([(width, 0), (width, height)], fill=_RULE, width=max(1, plan.canvas.unit // 12))
    draw_marks(draw, plan, style)
    return png_bytes(out), plan.placement
