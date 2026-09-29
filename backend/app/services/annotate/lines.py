"""Where the rows of writing sit on a script photo, read from its pixels alone.

This finds where rows of ink sit, not what they say: the text itself comes from OCR. It makes no
model calls and uses no randomness, so the same image always gives the same bands.
"""

import io
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

# Detection runs on a copy scaled so its longer side is at most this many pixels: plenty to
# separate handwritten rows, and it keeps the arithmetic quick on a 12-megapixel photo
_WORKING_SIZE = 1600
# Bradley-Roth adaptive threshold: a pixel is ink when it is this much darker than the mean of the
# square around it, whose side is this fraction of the image width. A local threshold copes with
# the shadows and uneven light of a phone photo, which a single global one does not.
_WINDOW_FRACTION = 1 / 16
_DARKER_BY = 0.15
# Page edges, table shadows and the binder margin are not writing: this fraction of each side is ignored
_MARGIN_FRACTION = 0.04
# A row this full of ink is a ruled line or a fold, not handwriting
_RULE_DENSITY = 0.5
# A row counts as writing when its density reaches this fraction of the page's busy rows (the
# 95th percentile), and never below the floor
_ROW_THRESHOLD = 0.02
_ROW_FLOOR = 0.003
# Rows closer than this are one line (an i's dot, a fraction bar): the larger of this fraction of
# the page height and this fraction of the typical band's height
_MERGE_GAP_FRACTION = 0.004
_MERGE_GAP_OF_BAND = 0.3
# Bands thinner than this are specks or stray strokes: the larger of this fraction of the page
# height and this fraction of the typical band's height
_MIN_HEIGHT_FRACTION = 0.005
_MIN_HEIGHT_OF_BAND = 0.35


@dataclass
class TextBand:
    # Fractions of the page height, 0.0 at the top to 1.0 at the bottom
    top: float
    bottom: float
    # Mean ink density of the band's rows: the fraction of each row's pixels that are ink
    density: float


def load_page(image_bytes: bytes) -> Image.Image:
    """The image upright, as the camera held it: EXIF orientation applied."""
    image = Image.open(io.BytesIO(image_bytes))
    image.load()
    return ImageOps.exif_transpose(image)


def _greyscale(image: Image.Image) -> NDArray[np.float64]:
    if image.mode in ("RGBA", "LA", "P"):
        # Transparent areas are paper, not black
        rgba = image.convert("RGBA")
        backdrop = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(backdrop, rgba)
    grey = image.convert("L")
    scale = _WORKING_SIZE / max(grey.size)
    if scale < 1:
        size = (max(1, round(grey.width * scale)), max(1, round(grey.height * scale)))
        grey = grey.resize(size, Image.Resampling.BOX)
    return np.asarray(grey, dtype=np.float64)


def _ink_mask(grey: NDArray[np.float64]) -> NDArray[np.bool_]:
    """True where a pixel is ink, by comparison with the mean brightness around it."""
    height, width = grey.shape
    half = max(1, round(width * _WINDOW_FRACTION) // 2)
    # Integral image, padded with a zero row and column so every window sum is four lookups
    integral = np.zeros((height + 1, width + 1), dtype=np.float64)
    integral[1:, 1:] = grey.cumsum(axis=0).cumsum(axis=1)
    rows = np.arange(height)
    cols = np.arange(width)
    top = np.clip(rows - half, 0, height)[:, None]
    bottom = np.clip(rows + half + 1, 0, height)[:, None]
    left = np.clip(cols - half, 0, width)[None, :]
    right = np.clip(cols + half + 1, 0, width)[None, :]
    window = integral[bottom, right] - integral[top, right] - integral[bottom, left] + integral[top, left]
    mean = window / ((bottom - top) * (right - left))
    return grey < mean * (1 - _DARKER_BY)


def _runs(active: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """Each contiguous run of True as (first, last + 1)."""
    padded = np.concatenate(([False], active, [False])).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    return [(int(start), int(end)) for start, end in zip(edges[::2], edges[1::2])]


def detect_text_bands(image_bytes: bytes) -> list[TextBand]:
    """The horizontal bands of the page that hold rows of writing, top to bottom.

    This finds where rows of ink sit, not what they say; the text itself comes from OCR.

    A horizontal projection profile: the image is made greyscale, each pixel is judged ink or
    paper by an adaptive threshold, and the ink in each row is counted. Contiguous rows with
    enough ink form bands. Bands separated by less than a small gap are merged, bands thinner
    than a minimum height are dropped, and the outer margins of the page are ignored.
    Deterministic: the same image gives the same bands.
    """
    grey = _greyscale(load_page(image_bytes))
    height, width = grey.shape
    if height < 8 or width < 8:
        return []

    ink = _ink_mask(grey)
    margin_x = round(width * _MARGIN_FRACTION)
    margin_y = round(height * _MARGIN_FRACTION)
    density = ink[:, margin_x : width - margin_x].mean(axis=1)
    density[:margin_y] = 0
    density[height - margin_y :] = 0
    density[density >= _RULE_DENSITY] = 0
    # A three-row moving average, so one clean row inside a line of writing doesn't split it
    smoothed = np.convolve(density, np.ones(3) / 3, mode="same")

    busy = smoothed[smoothed > 0]
    if busy.size == 0:
        return []
    threshold = max(_ROW_FLOOR, _ROW_THRESHOLD * float(np.percentile(busy, 95)))
    runs = _runs(smoothed >= threshold)
    if not runs:
        return []

    typical = float(np.median([end - start for start, end in runs]))
    merge_gap = max(height * _MERGE_GAP_FRACTION, typical * _MERGE_GAP_OF_BAND)
    merged: list[tuple[int, int]] = [runs[0]]
    for start, end in runs[1:]:
        if start - merged[-1][1] < merge_gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))

    typical = float(np.median([end - start for start, end in merged]))
    min_height = max(height * _MIN_HEIGHT_FRACTION, typical * _MIN_HEIGHT_OF_BAND)
    return [
        TextBand(top=start / height, bottom=end / height, density=float(density[start:end].mean()))
        for start, end in merged
        if end - start >= min_height
    ]
