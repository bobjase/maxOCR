"""Deliberate edits to our own glyph outlines, one visible change at a time (James, 2026-10-12).

mirror_foot: make a foot serif symmetric. The stem's centre is found from a horizontal slice through the stem
(above the foot); the foot region on the kept side is cut out, mirrored across the stem centre, and joined with the
rest of the letter (boolean union), replacing the other side.

    python scripts/glyph_edit.py SRC.ttf DST.ttf mirror_foot --char f --stem-y 250 --foot-top 110 [--keep left]
    python scripts/glyph_edit.py SRC.ttf DST.ttf mirror_foot --char q --stem-y -60 --foot-top -125 [--keep left]
mirror_band: make a horizontal band symmetric about the stem (the arms of the f's crossbar).
flat_bar: replace a crossbar with a flat-topped, flat-bottomed symmetric bar with subtly rounded ends (James).
    python scripts/glyph_edit.py SRC.ttf DST.ttf mirror_band --char f --stem-y 250 --y0 440 --y1 565 --keep right
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


def mirror_band(p: pathops.Path, stem_y: float, y0: float, y1: float, keep: str = "right") -> pathops.Path:
    """Make the arms between heights y0 and y1 symmetric about the stem (e.g. an f's crossbar): the kept arm (outside
    the stem) is mirrored across the stem centre and replaces the other arm; the stem and the rest are untouched."""
    x0, x1 = stem_span(p, stem_y)
    xc = (x0 + x1) / 2
    # only the arms change: the stem itself (between its edges) is left exactly as it is, so nothing above or below
    # the band shifts against it
    if keep == "right":
        arm, other = (x1, y0, BIG, y1), (-BIG, y0, x0, y1)
    else:
        arm, other = (-BIG, y0, x0, y1), (x1, y0, BIG, y1)
    mirrored = transformed(clip(p, arm), (-1, 0, 0, 1, 2 * xc, 0))
    rest = pathops.op(p, rect(*other), pathops.PathOp.DIFFERENCE)
    return pathops.op(rest, mirrored, pathops.PathOp.UNION)


def rounded_rect(x0, y0, x1, y1, r) -> pathops.Path:
    """Rectangle with flat sides and corners rounded by r (quarter-circle arcs, kappa 0.5523)."""
    k = 0.5523 * r
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((x0 + r, y0))
    pen.lineTo((x1 - r, y0))
    pen.curveTo((x1 - r + k, y0), (x1, y0 + r - k), (x1, y0 + r))
    pen.lineTo((x1, y1 - r))
    pen.curveTo((x1, y1 - r + k), (x1 - r + k, y1), (x1 - r, y1))
    pen.lineTo((x0 + r, y1))
    pen.curveTo((x0 + r - k, y1), (x0, y1 - r + k), (x0, y1 - r))
    pen.lineTo((x0, y0 + r))
    pen.curveTo((x0, y0 + r - k), (x0 + r - k, y0), (x0 + r, y0))
    pen.closePath()
    return p


def flat_bar(p: pathops.Path, stem_y: float, lo: float, hi: float, round_frac: float = 0.3) -> pathops.Path:
    """Replace a crossbar (found between heights lo and hi: the rows clearly wider than the stem) with one bar that is
    flat on top and bottom, as thick as the old bar, symmetric about the stem with the longer arm's length, and with
    subtly rounded ends (corner radius = round_frac x thickness). The stem is left as it is."""
    x0, x1 = stem_span(p, stem_y)
    xc = (x0 + x1) / 2
    rows = []
    for y in range(int(lo), int(hi) + 1, 2):
        a, _, b, _ = clip(p, (-BIG, y - 1, BIG, y + 1)).bounds
        if (b - a) > (x1 - x0) + 60:
            rows.append((y, a, b))
    y0, y1 = rows[0][0], rows[-1][0]
    arm = max(max(xc - a, b - xc) for _, a, b in rows)
    t = y1 - y0
    cut = pathops.op(rect(-BIG, y0 - 2, x0, y1 + 2), rect(x1, y0 - 2, BIG, y1 + 2), pathops.PathOp.UNION)
    rest = pathops.op(p, cut, pathops.PathOp.DIFFERENCE)
    bar = rounded_rect(xc - arm, y0, xc + arm, y1, round_frac * t)
    return pathops.op(rest, bar, pathops.PathOp.UNION)


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
    ap.add_argument("op", choices=["mirror_foot", "mirror_band", "flat_bar"])
    ap.add_argument("--char", required=True)
    ap.add_argument("--stem-y", type=float, required=True)
    ap.add_argument("--foot-top", type=float, help="mirror_foot: top of the foot region")
    ap.add_argument("--y0", type=float, help="mirror_band: bottom of the band")
    ap.add_argument("--y1", type=float, help="mirror_band: top of the band")
    ap.add_argument("--keep", default="left", choices=["left", "right"])
    a = ap.parse_args()
    f = TTFont(a.src)
    if a.op == "mirror_foot":
        p = mirror_foot(glyph_path(f, a.char), a.stem_y, a.foot_top, a.keep)
    elif a.op == "mirror_band":
        p = mirror_band(glyph_path(f, a.char), a.stem_y, a.y0, a.y1, a.keep)
    else:
        p = flat_bar(glyph_path(f, a.char), a.stem_y, a.y0, a.y1)
    write(f, a.char, p)
    f.save(a.dst)
    print(a.dst, a.char)


if __name__ == "__main__":
    main()
