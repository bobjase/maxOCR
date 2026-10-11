"""Digit-height variants of a font (digit-only lines lost digits when heights were inconsistent).

Each digit glyph is scaled uniformly (width follows, advance and sidebearing adjusted) and moved so its
ink spans a target vertical range:
  lining   - baseline to cap height, every digit;
  original - each digit's own range in the original amalgam (its old-style heights, new shapes);
  short    - baseline to SHORT x cap height, every digit;
optionally with a mark in the 0's counter to tell a short 0 from a lowercase o: slash or dot.

    python scripts/digit_heights.py SRC.ttf DST.ttf --mode short [--zero slash|dot]
"""
import argparse
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ORIGINAL = str(Path.home() / "maxocr-work/amalgam_opt/08BDEOQ/g06_09.ttf")
SHORT = 0.74     # short digits: about the x-height of the serif ingredients, relative to cap height
DIGITS = "0123456789"


def bounds(f: TTFont, ch: str):
    gs, cm = f.getGlyphSet(), f.getBestCmap()
    p = BoundsPen(gs)
    gs[cm[ord(ch)]].draw(p)
    return p.bounds


def cap_height(f: TTFont) -> float:
    b = bounds(f, "H")
    return b[3] - b[1]


def zero_mark(f: TTFont, name: str, kind: str, pen: TTGlyphPen) -> None:
    """Add a contour inside the 0's counter: a diagonal bar (slash) or an oval (dot), same winding as
    the outer contour so it unites with the ring."""
    g = f["glyf"][name]
    coords, ends, _ = g.getCoordinates(f["glyf"])
    x0, y0, x1, y1 = g.xMin, g.yMin, g.xMax, g.yMax
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    if kind == "dot":
        import math
        rx, ry = 0.13 * w, 0.11 * h
        pts = [(cx + rx * math.cos(-2 * math.pi * k / 16), cy + ry * math.sin(-2 * math.pi * k / 16)) for k in range(16)]
    else:
        t = 0.09 * w
        a, b = (cx - 0.28 * w, cy - 0.30 * h), (cx + 0.28 * w, cy + 0.30 * h)
        pts = [(a[0] - t, a[1]), (b[0] - t, b[1]), (b[0] + t, b[1]), (a[0] + t, a[1])]   # clockwise
    pen.moveTo(tuple(map(round, pts[0])))
    for p in pts[1:]:
        pen.lineTo(tuple(map(round, p)))
    pen.closePath()


def build(src: str, dst: str, mode: str, zero: str | None = None) -> str:
    f = TTFont(src)
    orig = TTFont(ORIGINAL)
    cap = cap_height(f)
    gs, cm = f.getGlyphSet(), f.getBestCmap()
    new = {}
    for ch in DIGITS:
        name = cm[ord(ch)]
        x0, y0, x1, y1 = bounds(f, ch)
        if mode == "lining":
            t0, t1 = 0.0, cap
        elif mode == "short":
            t0, t1 = 0.0, SHORT * cap
        else:
            ob = bounds(orig, ch)
            k = cap / cap_height(orig)
            t0, t1 = ob[1] * k, ob[3] * k
        s = (t1 - t0) / (y1 - y0)
        lsb = f["hmtx"][name][1]
        adv = f["hmtx"][name][0]
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(rec)
        pen = TTGlyphPen(None)
        # x: keep the left sidebearing, scale the ink; y: map [y0, y1] to [t0, t1].
        rec.replay(TransformPen(pen, (s, 0, 0, s, lsb - s * x0, t0 - s * y0)))
        new[name] = (pen, round(adv - (x1 - x0) * (1 - s)), lsb)
    for name, (pen, adv, lsb) in new.items():
        f["glyf"][name] = pen.glyph()
        f["hmtx"][name] = (adv, lsb)
    if zero:
        name = cm[ord("0")]
        f["glyf"][name].recalcBounds(f["glyf"])
        rec = DecomposingRecordingPen(f.getGlyphSet())
        f.getGlyphSet()[name].draw(rec)
        pen = TTGlyphPen(None)
        rec.replay(pen)
        zero_mark(f, name, zero, pen)
        f["glyf"][name] = pen.glyph()
    for name in new:
        f["glyf"][name].recalcBounds(f["glyf"])
    f.save(dst)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--mode", choices=["lining", "original", "short"], required=True)
    ap.add_argument("--zero", choices=["slash", "dot"])
    a = ap.parse_args()
    print(build(a.src, a.dst, a.mode, a.zero))


if __name__ == "__main__":
    main()
