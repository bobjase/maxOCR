"""R2/R2a/R2b/R2c: programmatic post-build invariants for candidate fonts.

A candidate is compared with the rung parent (R30a: frozen per rung) on every primary-alphabet
character:
  - advance width equal to the parent's (R2, R2c);
  - ink box within the per-glyph tolerance box (R2a);
  - ink area at least 85% of the parent glyph's (R2b), measured by rasterizing at 1 px per unit;
  - every contour non-self-intersecting (R2c).
Any failure rejects the candidate with a logged reason. No prose rule substitutes for this check.
"""
from dataclasses import dataclass
from functools import lru_cache

import freetype
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from shapely.geometry import LinearRing

from .corpus import PRIMARY_ALPHABET

MIN_INK_FRACTION = 0.85
CURVE_STEPS = 8


@dataclass(frozen=True)
class Glyph:
    advance: int
    bbox: tuple[float, float, float, float]   # xMin, yMin, xMax, yMax in font units
    ink_area: float                          # in square font units
    simple: bool                             # all contours non-self-intersecting


class _ContourPen(BasePen):
    """Flattens outlines into point lists, one per contour."""

    def __init__(self, glyphset):
        super().__init__(glyphset)
        self.contours, self._cur = [], []

    def _moveTo(self, p):
        self._cur = [p]

    def _lineTo(self, p):
        self._cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self._cur[-1]
        for t in np.linspace(0, 1, CURVE_STEPS + 1)[1:]:
            u = 1 - t
            self._cur.append(tuple(u**3 * np.array(p0) + 3 * u * u * t * np.array(p1)
                                   + 3 * u * t * t * np.array(p2) + t**3 * np.array(p3)))

    def _qCurveToOne(self, p1, p2):
        p0 = self._cur[-1]
        for t in np.linspace(0, 1, CURVE_STEPS + 1)[1:]:
            u = 1 - t
            self._cur.append(tuple(u * u * np.array(p0) + 2 * u * t * np.array(p1) + t * t * np.array(p2)))

    def _closePath(self):
        if len(self._cur) >= 3:
            self.contours.append(self._cur)
        self._cur = []

    _endPath = _closePath


def _ink_area(path: str, ch: str, upem: int) -> float:
    face = freetype.Face(path)
    face.set_pixel_sizes(upem, upem)    # 1 px per font unit
    face.load_char(ch, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_RENDER)
    bmp = face.glyph.bitmap
    if not (bmp.width and bmp.rows):
        return 0.0
    a = np.array(bmp.buffer, dtype=np.uint8).reshape(bmp.rows, bmp.pitch)[:, :bmp.width]
    return float(a.sum()) / 255.0


@lru_cache(maxsize=256)
def measure(path: str, chars: str = PRIMARY_ALPHABET) -> dict[str, Glyph]:
    f = TTFont(path)
    cmap, gs, upem = f.getBestCmap(), f.getGlyphSet(), f["head"].unitsPerEm
    out = {}
    for c in chars:
        name = cmap[ord(c)]
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        cp = _ContourPen(gs)
        gs[name].draw(cp)
        simple = all(LinearRing(pts).is_simple for pts in cp.contours if len(set(pts)) >= 3)
        out[c] = Glyph(f["hmtx"][name][0], bp.bounds, _ink_area(path, c, upem), simple)
    return out


def tolerance(fonts: list[str], chars: str = PRIMARY_ALPHABET, q: float = 95) -> dict[str, tuple]:
    """R2a: per glyph, the q-th percentile ink box over a variant set (nearest rank, so a glyph with
    few variants keeps its extremes): lower bounds from the (100-q)-th percentile of xMin/yMin,
    upper bounds from the q-th of xMax/yMax."""
    boxes = {c: np.array([measure(p)[c].bbox for p in fonts]) for c in chars}
    return {c: (np.percentile(b[:, 0], 100 - q, method="lower"), np.percentile(b[:, 1], 100 - q, method="lower"),
                np.percentile(b[:, 2], q, method="higher"), np.percentile(b[:, 3], q, method="higher"))
            for c, b in boxes.items()}


def check(candidate: str, parent: str, tol: dict[str, tuple] | None) -> list[str]:
    """Returns the list of violations (empty = passes R2c)."""
    cand, par = measure(candidate), measure(parent)
    problems = []
    for c in PRIMARY_ALPHABET:
        g, p = cand[c], par[c]
        if g.advance != p.advance:
            problems.append(f"{c}: advance {g.advance} != parent {p.advance}")
        if tol is not None:
            x0, y0, x1, y1 = tol[c]
            gx0, gy0, gx1, gy1 = g.bbox
            if gx0 < x0 - 0.5 or gy0 < y0 - 0.5 or gx1 > x1 + 0.5 or gy1 > y1 + 0.5:
                problems.append(f"{c}: ink box {tuple(round(v) for v in g.bbox)} outside tolerance "
                                f"{tuple(round(v) for v in tol[c])}")
        if g.ink_area < MIN_INK_FRACTION * p.ink_area:
            problems.append(f"{c}: ink area {g.ink_area:.0f} < {MIN_INK_FRACTION:.0%} of parent {p.ink_area:.0f}")
        if not g.simple:
            problems.append(f"{c}: self-intersecting contour")
    return problems
