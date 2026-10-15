"""White centre lines inside strokes (James, 2026-10-14: "track out white lines inside the arms of the numbers"),
for ink bleed: spreading ink fills the line instead of thickening the stroke outward. The glyph is shrunk inward
by (stroke/2 - line/2), which leaves a thin core along the middle of every stroke; that core is cut away.

    python scripts/inline_lines.py SRC.ttf DST.ttf --chars 0123456789 --stroke 170 --line 20
"""
import argparse
import os
import sys

import pathops
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, write  # noqa: E402


class Flat(BasePen):
    """Outline as closed polylines (curves cut into short segments)."""
    def __init__(self, n=16):
        super().__init__(None); self.rings, self.cur, self.n = [], [], n
    def _moveTo(self, p): self.cur = [p]
    def _lineTo(self, p): self.cur.append(p)
    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.n + 1):
            t = i / self.n
            self.cur.append(((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0], (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]))
    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.n + 1):
            t = i / self.n; s = 1 - t
            self.cur.append(tuple(s**3*a + 3*s*s*t*b + 3*s*t*t*c + t**3*d for a, b, c, d in zip(p0, p1, p2, p3)))
    def _closePath(self):
        if len(self.cur) > 2: self.rings.append(self.cur)
        self.cur = []


def to_shape(p: pathops.Path):
    pen = Flat(); p.draw(pen)
    # even-odd assembly: xor of all rings gives the glyph with its holes
    shape = None
    for r in pen.rings:
        poly = Polygon(r).buffer(0)
        shape = poly if shape is None else shape.symmetric_difference(poly)
    return shape


def to_path(shape) -> pathops.Path:
    p = pathops.Path(); pen = p.getPen()
    polys = getattr(shape, "geoms", [shape])
    for poly in polys:
        if poly.is_empty: continue
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)[:-1]
            pen.moveTo(pts[0])
            for q in pts[1:]: pen.lineTo(q)
            pen.closePath()
    out = pathops.Path(); pathops.op(p, pathops.Path(), pathops.PathOp.UNION)
    return pathops.op(p, pathops.Path(), pathops.PathOp.UNION)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--chars", default="0123456789")
    ap.add_argument("--stroke", type=float, default=170)
    ap.add_argument("--line", type=float, default=20)
    a = ap.parse_args()
    f = TTFont(a.src)
    for c in a.chars:
        g = to_shape(glyph_path(f, c))
        core = g.buffer(-(a.stroke - a.line) / 2, quad_segs=16)
        core = core.buffer(-a.line / 4, quad_segs=16).buffer(a.line / 4, quad_segs=16)  # drop slivers
        res = g.difference(core).simplify(1.5)
        write(f, c, to_path(res))
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
