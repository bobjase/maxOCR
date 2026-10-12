"""Blend glyphs from several fonts into one font ("amalgam" fonts).

A recipe maps each character to weighted ingredients: (font path, weight), plus optional geometry
adjustments. For each character:
  1. every ingredient glyph is rasterized at high resolution, cropped to its ink, and normalized to
     a common square; its geometry (ink width, ink height, bottom, left sidebearing, advance) is
     measured relative to the font's capital height;
  2. shapes are blended as the weighted mean of signed distance fields (SDFs) of the normalized masks,
     so different topologies blend without tearing; geometry is blended as weighted means;
  3. the blended mask is resized to the blended geometry, traced into contours (outer clockwise,
     holes counter-clockwise for TrueType) and assembled into a new font with fontTools FontBuilder.
A global `boldness` shifts the SDF threshold (positive = heavier), in units of the normalized box.

Ingredients for a released font must be OFL; blending installed proprietary fonts is for local
measurement only.
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from scipy.ndimage import distance_transform_edt, gaussian_filter

from .render import render, split_face

NORM = 256          # normalized shape box, px
UPEM = 1000
CAP = 700           # capital height of the built font, font units
RENDER_CAP_PX = 512  # ingredient rasterization: cap height in px


@dataclass(frozen=True)
class Geometry:
    """Relative to capital height (cap = 1)."""
    width: float
    height: float
    bottom: float     # yMin (negative = below baseline)
    lsb: float        # left sidebearing
    advance: float


@dataclass
class Ingredient:
    font: str
    weight: float


@dataclass
class CharRecipe:
    ingredients: list[Ingredient]
    width_scale: float = 1.0
    height_scale: float = 1.0
    bottom_shift: float = 0.0     # in cap units
    boldness: float = 0.0         # extra SDF offset for this glyph, px of the normalized box
    smooth: float = 0.0           # Gaussian blur of the blended SDF (px of the normalized box): rounds off lumps


@dataclass
class Recipe:
    chars: dict[str, CharRecipe]
    boldness: float = 0.0
    name: str = "MaxOCR Blend"
    meta: dict = field(default_factory=dict)


@lru_cache(maxsize=None)
def _cap_units(font: str) -> tuple[float, int]:
    path, idx = split_face(font)
    f = TTFont(path, fontNumber=idx) if path.lower().endswith(".ttc") else TTFont(path)
    gs = f.getGlyphSet()
    pen = BoundsPen(gs)
    gs[f.getBestCmap()[ord("H")]].draw(pen)
    return pen.bounds[3] - pen.bounds[1], f["head"].unitsPerEm


@lru_cache(maxsize=None)
def _geometry(font: str, ch: str) -> Geometry:
    path, idx = split_face(font)
    f = TTFont(path, fontNumber=idx) if path.lower().endswith(".ttc") else TTFont(path)
    gs, cmap = f.getGlyphSet(), f.getBestCmap()
    name = cmap[ord(ch)]
    pen = BoundsPen(gs)
    gs[name].draw(pen)
    x0, y0, x1, y1 = pen.bounds
    cap, _ = _cap_units(font)
    adv = f["hmtx"][name][0]
    return Geometry((x1 - x0) / cap, (y1 - y0) / cap, y0 / cap, x0 / cap, adv / cap)


@lru_cache(maxsize=None)
def normalized_sdf(font: str, ch: str) -> np.ndarray:
    """SDF (px of the NORM box; >0 outside, <0 inside) of the ingredient glyph normalized to NORM x NORM."""
    cap, upem = _cap_units(font)
    # Point size giving RENDER_CAP_PX cap height at 72 dpi: px = pt * cap/upem.
    size_pt = RENDER_CAP_PX * upem / cap
    img = render(font, ch, size_pt, 72)
    m = img < 128
    ys, xs = np.nonzero(m)
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
    pad = NORM // 8
    norm = cv2.resize(crop, (NORM - 2 * pad, NORM - 2 * pad), interpolation=cv2.INTER_AREA) >= 128
    canvas = np.zeros((NORM, NORM), bool)
    canvas[pad:NORM - pad, pad:NORM - pad] = norm
    return distance_transform_edt(~canvas) - distance_transform_edt(canvas)


def _blend(ch: str, r: CharRecipe, boldness: float) -> tuple[np.ndarray, Geometry]:
    total = sum(i.weight for i in r.ingredients)
    ws = [i.weight / total for i in r.ingredients]
    sdf = sum(w * normalized_sdf(i.font, ch) for w, i in zip(ws, r.ingredients))
    if r.smooth > 0:
        sdf = gaussian_filter(sdf, r.smooth)
    mask = _clean(sdf < (boldness + r.boldness))
    geos = [_geometry(i.font, ch) for i in r.ingredients]
    g = Geometry(*(sum(w * getattr(x, k) for w, x in zip(ws, geos))
                   for k in ("width", "height", "bottom", "lsb", "advance")))
    g = Geometry(g.width * r.width_scale, g.height * r.height_scale, g.bottom + r.bottom_shift,
                 g.lsb, g.advance + g.width * (r.width_scale - 1))
    return mask, g


MIN_PART = 0.01   # ink pieces / holes smaller than this share of the glyph's ink are blending debris


def _clean(mask: np.ndarray) -> np.ndarray:
    """Remove blending debris: tiny ink fragments (half-present serifs) and pinholes."""
    ink = mask.sum()
    if ink == 0:
        return mask
    out = mask.copy()
    for target, value in ((out, False), (~out, True)):
        n, lab, stats, _ = cv2.connectedComponentsWithStats(target.astype(np.uint8), connectivity=8)
        for k in range(1, n):
            if stats[k, cv2.CC_STAT_AREA] < MIN_PART * ink:
                out[lab == k] = value
    return out


def _contours(mask: np.ndarray, g: Geometry) -> list[list[tuple[int, int]]]:
    """Trace the blended normalized mask into font-unit contours placed by geometry g."""
    pad = NORM // 8
    inner = mask[pad:NORM - pad, pad:NORM - pad]
    # Undo the normalization: the shape box maps to the blended ink box.
    w_u, h_u = g.width * CAP, g.height * CAP
    scale = 4  # trace at higher resolution for smoother outlines
    big = cv2.resize(inner.astype(np.uint8) * 255, (max(8, int(w_u * scale / 4)), max(8, int(h_u * scale / 4))),
                     interpolation=cv2.INTER_LINEAR)
    cnts, hier = cv2.findContours((big >= 128).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    if hier is None:
        return out
    sx, sy = w_u / big.shape[1], h_u / big.shape[0]
    x0, y_top = g.lsb * CAP, (g.bottom + g.height) * CAP
    for c, h in zip(cnts, hier[0]):
        c = cv2.approxPolyDP(c, 0.6, True)[:, 0, :]
        if len(c) < 3:
            continue
        pts = [(int(round(x0 + px * sx)), int(round(y_top - py * sy))) for px, py in c]
        area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                   for i in range(len(pts))) / 2
        is_hole = h[3] != -1
        # TrueType: outer contours clockwise (negative signed area in y-up), holes counter-clockwise.
        if (not is_hole and area > 0) or (is_hole and area < 0):
            pts = pts[::-1]
        out.append(pts)
    return out


def build_font(recipe: Recipe, path: str) -> str:
    glyph_order = [".notdef", "space"] + [f"uni{ord(c):04X}" for c in recipe.chars]
    glyphs, metrics = {}, {}
    pen = TTGlyphPen(None)
    glyphs[".notdef"] = pen.glyph()
    metrics[".notdef"] = (500, 0)
    glyphs["space"] = TTGlyphPen(None).glyph()
    metrics["space"] = (int(0.35 * CAP), 0)
    for ch, r in recipe.chars.items():
        mask, g = _blend(ch, r, recipe.boldness)
        pen = TTGlyphPen(None)
        for pts in _contours(mask, g):
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
        name = f"uni{ord(ch):04X}"
        glyphs[name] = pen.glyph()
        metrics[name] = (int(round(g.advance * CAP)), int(round(g.lsb * CAP)))
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({ord(c): f"uni{ord(c):04X}" for c in recipe.chars} | {32: "space"})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-250)
    ps = re.sub(r"[^A-Za-z0-9-]", "", recipe.name.replace(" ", "-"))[:29] + "-Regular"
    # Full name (4) and PostScript name (6) are required by Windows Font Viewer and installers.
    fb.setupNameTable({"familyName": recipe.name, "styleName": "Regular",
                       "uniqueFontIdentifier": f"0.1;MAXOCR;{ps}", "fullName": f"{recipe.name} Regular",
                       "version": "Version 0.1", "psName": ps,
                       "copyright": "Blend of SIL Open Font License fonts; see recipe",
                       "licenseDescription": "SIL Open Font License 1.1"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-250, usWinAscent=950, usWinDescent=300, sCapHeight=CAP)
    fb.setupPost()
    fb.save(path)
    return path
