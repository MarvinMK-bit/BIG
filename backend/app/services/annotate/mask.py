"""The Mask of Marks: a script's marks on white, for printing onto the student's original paper.

The mask is the page's own size, with nothing of the student's work on it: fed back through a
printer, the paper keeps the student's writing and gains only the marks. It is laid out by
the same plan as the annotated image (renderer.plan_marks), so every mark sits at the same
height. The one difference is across: the annotated image has its marks in a margin added
beside the page, which the paper doesn't have, so the mask draws that column over the
right-hand strip of the page itself, the same width as the margin.

Faint registration crosses near each corner mark where the photographed page's corners were,
so a teacher can hold a test print against the script and check the two line up.
"""

import io
from typing import Literal

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

from app.services.annotate.renderer import (
    Placement,
    ScriptAnnotations,
    Style,
    draw_marks,
    plan_marks,
    png_bytes,
    registration_inset,
)

Paper = Literal["A4", "Letter"]

PAPER_SIZES: dict[str, tuple[float, float]] = {"A4": A4, "Letter": LETTER}

INSTRUCTION = (
    "Feed the student's original script face up, top edge first. "
    "Check the corner marks align before printing."
)

_REGISTRATION = (185, 185, 185)
# What printers can't reach at the page's edges, and the strip at the foot for the instruction
_EDGE = 6 * mm
_FOOT = 12 * mm


def _draw_registration(draw: ImageDraw.ImageDraw, width: int, height: int, line: int) -> None:
    """A cross in a circle near each corner, inset by registration_inset."""
    inset, arm = registration_inset(width, height)
    radius = arm * 0.6
    for x in (inset, width - inset):
        for y in (inset, height - inset):
            draw.line([(x - arm, y), (x + arm, y)], fill=_REGISTRATION, width=line)
            draw.line([(x, y - arm), (x, y + arm)], fill=_REGISTRATION, width=line)
            draw.ellipse([(x - radius, y - radius), (x + radius, y + radius)], outline=_REGISTRATION, width=line)


def render_mask(
    image_bytes: bytes,
    mime_type: str,
    annotations: ScriptAnnotations,
    style: Style = "symbols",
    placement: Placement = "lines",
) -> tuple[bytes, Placement]:
    """The marks alone as a PNG the size of the page, white everywhere else, with registration
    crosses at the corners, and the placement actually used, as render_annotated_script."""
    plan = plan_marks(image_bytes, mime_type, annotations, style, placement)
    width, height = plan.page.size
    mask = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(mask)
    _draw_registration(draw, width, height, max(1, plan.canvas.unit // 10))
    # The annotated image's margin column, moved onto the page's right-hand strip
    draw_marks(draw, plan, style, dx=-plan.canvas.margin)
    return png_bytes(mask), plan.placement


def mask_to_pdf(mask_png: bytes, paper: str = "A4") -> bytes:
    """One page of the given paper, A4 or Letter, holding the mask scaled to fit the printable
    area with its aspect ratio kept, centred, and the feeding instruction in small grey type at
    the foot."""
    if paper not in PAPER_SIZES:
        raise ValueError(f"Unknown paper size {paper!r}: use {' or '.join(PAPER_SIZES)}")
    page_width, page_height = PAPER_SIZES[paper]
    image = ImageReader(io.BytesIO(mask_png))
    pixels_wide, pixels_high = image.getSize()

    area_width = page_width - 2 * _EDGE
    area_height = page_height - _EDGE - _FOOT
    scale = min(area_width / pixels_wide, area_height / pixels_high)
    width, height = pixels_wide * scale, pixels_high * scale
    x = (page_width - width) / 2
    y = _FOOT + (area_height - height) / 2

    buffer = io.BytesIO()
    pdf = pdf_canvas.Canvas(buffer, pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle("Mask of Marks")
    pdf.setCreator("BIG")
    pdf.drawImage(image, x, y, width=width, height=height)
    pdf.setFillColorRGB(0.45, 0.45, 0.45)
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(page_width / 2, _FOOT / 2 - 1.5, INSTRUCTION)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
