"""Deliberate edits to our own glyph outlines, one visible change at a time (James, 2026-10-12).

mirror_foot: make a foot serif symmetric. The stem's centre is found from a horizontal slice through the stem
(above the foot); the foot region on the kept side is cut out, mirrored across the stem centre, and joined with the
rest of the letter (boolean union), replacing the other side.

    python scripts/glyph_edit.py SRC.ttf DST.ttf mirror_foot --char f --stem-y 250 --foot-top 110 [--keep left]
    python scripts/glyph_edit.py SRC.ttf DST.ttf mirror_foot --char q --stem-y -60 --foot-top -125 [--keep left]
"""
import argparse

import pathops
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

BIG = 5000


def glyph_path(f: TTFont, c: str) -> pathops.Path:
    gs, cm = f.getGlyphSet(), f.getBestCmap()
    p = pathops.Path()
    rec = DecomposingRecordingPen(gs)
    gs[cm[ord(c)]].draw(rec)
    rec.replay(p.getPen())
    return p


def rect(x0, y0, x1, y1) -> pathops.Path:
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0)); pen.closePath()
    return p


def clip(p, box) -> pathops.Path:
    return pathops.op(p, rect(*box), pathops.PathOp.INTERSECTION)


def transformed(p, m) -> pathops.Path:
    out = pathops.Path()
    p.draw(TransformPen(out.getPen(), m))
    return out


def stem_span(p: pathops.Path, y: float) -> tuple[float, float]:
    """Left and right edge of the ink in a 2-unit slice at height y (the stem, where nothing else is at that y)."""
    s = clip(p, (-BIG, y - 1, BIG, y + 1))
    x0, _, x1, _ = s.bounds
    return x0, x1


def mirror_foot(p: pathops.Path, stem_y: float, foot_top: float, keep: str = "left") -> pathops.Path:
    x0, x1 = stem_span(p, stem_y)
    xc = (x0 + x1) / 2
    upper = clip(p, (-BIG, foot_top, BIG, BIG))
    half = clip(p, (-BIG, -BIG, xc, foot_top) if keep == "left" else (xc, -BIG, BIG, foot_top))
    mirrored = transformed(half, (-1, 0, 0, 1, 2 * xc, 0))
    return pathops.op(pathops.op(upper, half, pathops.PathOp.UNION), mirrored, pathops.PathOp.UNION)


def write(f: TTFont, c: str, p: pathops.Path) -> None:
    p.simplify(fix_winding=True)
    tt = TTGlyphPen(None)
    p.draw(Cu2QuPen(tt, max_err=0.5, reverse_direction=True))
    name = f.getBestCmap()[ord(c)]
    g = tt.glyph()
    g.recalcBounds(f["glyf"])
    adv, _ = f["hmtx"][name]
    f["glyf"][name] = g
    f["hmtx"][name] = (adv, g.xMin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("op", choices=["mirror_foot"])
    ap.add_argument("--char", required=True)
    ap.add_argument("--stem-y", type=float, required=True)
    ap.add_argument("--foot-top", type=float, required=True)
    ap.add_argument("--keep", default="left", choices=["left", "right"])
    a = ap.parse_args()
    f = TTFont(a.src)
    p = mirror_foot(glyph_path(f, a.char), a.stem_y, a.foot_top, a.keep)
    write(f, a.char, p)
    f.save(a.dst)
    print(a.dst, a.char)


if __name__ == "__main__":
    main()
