"""R1/R3: render a string to a grayscale raster under the frozen raster contract.

Unhinted, no stem darkening, no LCD filtering, no subpixel positioning.
Pen origins are integer pixels; fractional jitter belongs to the degradation bank.
Output is uint8, 0 = ink, 255 = paper.
"""
import os
from functools import lru_cache

# R3: stem darkening off for every driver. Must be set before FreeType initializes.
os.environ["FREETYPE_PROPERTIES"] = "cff:no-stem-darkening=1 autofitter:no-stem-darkening=1"

import freetype  # noqa: E402
import numpy as np
import uharfbuzz as hb

PAD = 4  # px of paper around the line


def split_face(font: str) -> tuple[str, int]:
    """'file.ttc#2' selects face 2 of a collection; plain paths are face 0."""
    path, _, index = font.partition("#")
    return path, int(index or 0)


@lru_cache(maxsize=None)
def _load(font: str):
    path, index = split_face(font)
    data = open(path, "rb").read()
    hb_font = hb.Font(hb.Face(data, index))
    return freetype.Face(path, index=index), hb_font


def render(font_path: str, text: str, size_pt: float = 8.0, dpi: int = 200,
           origin_px: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
    ft_face, hb_font = _load(font_path)
    ft_face.set_char_size(int(round(size_pt * 64)), 0, dpi, dpi)
    upem = ft_face.units_per_EM
    px_per_unit = size_pt * dpi / 72.0 / upem

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    # Contextual alternates stay off (glyph-level measurements), except for runs that test fonts whose
    # calt feature is the point (MaxOCR Smart): set MAXOCR_CALT=1 in the environment of that run.
    hb.shape(hb_font, buf, {"liga": False, "calt": os.environ.get("MAXOCR_CALT") == "1"})

    ascender = int(np.ceil(ft_face.ascender * px_per_unit))
    descender = int(np.ceil(-ft_face.descender * px_per_unit))
    width = int(np.ceil(sum(p.x_advance for p in buf.glyph_positions) * px_per_unit))
    h = ascender + descender + 2 * PAD
    w = width + 2 * PAD
    canvas = np.zeros((h, w), dtype=np.float32)  # coverage, 0..1

    # Integer pen origins; the fractional part of origin_px (bank jitter) goes into FreeType's
    # transform delta so outlines are rasterized at the sub-pixel offset.
    ox_int, oy_int = int(np.floor(origin_px[0])), int(np.floor(origin_px[1]))
    fx, fy = origin_px[0] - ox_int, origin_px[1] - oy_int
    ft_face.set_transform(freetype.Matrix(0x10000, 0, 0, 0x10000),
                          freetype.Vector(int(round(fx * 64)), int(round(-fy * 64))))

    pen_x = 0.0
    baseline = PAD + ascender + oy_int
    # Always rasterize outlines: some fonts (e.g. MS Gothic) carry embedded 1-bit bitmaps for small
    # sizes, which FreeType would otherwise use instead of the outline.
    flags = freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_RENDER
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        ft_face.load_glyph(info.codepoint, flags)
        slot = ft_face.glyph
        bmp = slot.bitmap
        if bmp.width and bmp.rows:
            glyph = np.array(bmp.buffer, dtype=np.uint8).reshape(bmp.rows, bmp.pitch)[:, :bmp.width]
            x0 = PAD + int(round(pen_x + pos.x_offset * px_per_unit)) + ox_int + slot.bitmap_left
            y0 = baseline - slot.bitmap_top
            ys, xs = slice(max(y0, 0), min(y0 + bmp.rows, h)), slice(max(x0, 0), min(x0 + bmp.width, w))
            sub = glyph[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0] / 255.0
            canvas[ys, xs] = np.maximum(canvas[ys, xs], sub)
        pen_x += pos.x_advance * px_per_unit

    out = (255 - np.round(canvas * 255)).astype(np.uint8)
    if os.environ.get("MAXOCR_CROP") == "ink":
        # Fair line boxes across fonts: real OCR pipelines crop a text line close to its ink, so the
        # font's own ascender/descender padding should not change the letter size an engine sees.
        # Keep the ink rows plus a margin of CROP_MARGIN x the font's capital height above and below.
        rows = np.nonzero(canvas.max(axis=1) > 0.05)[0]
        if len(rows):
            m = int(round(CROP_MARGIN * _cap_px(font_path, size_pt, dpi)))
            out = out[max(rows[0] - m, 0):min(rows[-1] + m + 1, out.shape[0])]
    return out


CROP_MARGIN = 0.25


@lru_cache(maxsize=None)
def _cap_upem(font: str) -> float:
    path, index = split_face(font)
    face = freetype.Face(path, index=index)
    face.set_char_size(1000 * 64, 0, 72, 72)
    face.load_char("H", freetype.FT_LOAD_NO_SCALE)
    return face.glyph.metrics.height / face.units_per_EM


def _cap_px(font: str, size_pt: float, dpi: int) -> float:
    return _cap_upem(font) * size_pt * dpi / 72.0
