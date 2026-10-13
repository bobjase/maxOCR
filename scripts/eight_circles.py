"""8 with round counters (James, 2026-10-12: "make the inside of the 8 circles"): the 8's own outside is kept, both
counters become circles centred in their loops.
    python scripts/eight_circles.py SRC.ttf DST.ttf [--upper cx,cy,r] [--lower cx,cy,r]
"""
import argparse
import os
import sys

import pathops
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import write

K = 0.5523


def circle(cx, cy, r) -> pathops.Path:
    p = pathops.Path(); pen = p.getPen()
    pen.moveTo((cx - r, cy))
    pen.curveTo((cx - r, cy + K * r), (cx - K * r, cy + r), (cx, cy + r))
    pen.curveTo((cx + K * r, cy + r), (cx + r, cy + K * r), (cx + r, cy))
    pen.curveTo((cx + r, cy - K * r), (cx + K * r, cy - r), (cx, cy - r))
    pen.curveTo((cx - K * r, cy - r), (cx - r, cy - K * r), (cx - r, cy))
    pen.closePath()
    return p


def outside(f: TTFont, ch: str) -> pathops.Path:
    """The glyph's largest contour only (its outside), filled."""
    rec = RecordingPen()
    f.getGlyphSet()[f.getBestCmap()[ord(ch)]].draw(rec)
    contours, cur = [], []
    for op, args in rec.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            contours.append(cur); cur = []
    best = None
    for c in contours:
        p = pathops.Path(); pen = p.getPen()
        for op, args in c:
            getattr(pen, op)(*args)
        x0, y0, x1, y1 = p.bounds
        if best is None or (x1 - x0) * (y1 - y0) > best[0]:
            best = ((x1 - x0) * (y1 - y0), p)
    return best[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--upper", default="333,498,125")
    ap.add_argument("--lower", default="321,118,160")
    a = ap.parse_args()
    f = TTFont(a.src)
    p = outside(f, "8")
    for spec in (a.upper, a.lower):
        cx, cy, r = map(float, spec.split(","))
        p = pathops.op(p, circle(cx, cy, r), pathops.PathOp.DIFFERENCE)
    write(f, "8", p)
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
