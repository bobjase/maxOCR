"""More even digits (James, 2026-10-14): under damage that thins the ink, the thin parts of our digits vanish and the
digits fall apart (DejaVu Sans' even strokes survive). Each digit's outline is grown evenly by t font units (a smooth
offset of its own curves, sharp corners kept), then scaled back onto its original box: the size stays the same, thin
strokes gain proportionally far more than thick ones.

    python scripts/even_digits.py SRC.ttf DST.ttf --t 12
"""
import argparse
import os
import sys

import pathops
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, transformed, write  # noqa: E402


def grow(p: pathops.Path, t: float) -> pathops.Path:
    band = pathops.Path()
    band.addPath(p)
    band.stroke(2 * t, pathops.LineCap.BUTT_CAP, pathops.LineJoin.MITER_JOIN, 4)
    band.convertConicsToQuads()
    g = pathops.op(p, band, pathops.PathOp.UNION)
    (x0, y0, x1, y1), (a0, b0, a1, b1) = p.bounds, g.bounds
    sx, sy = (x1 - x0) / (a1 - a0), (y1 - y0) / (b1 - b0)
    return transformed(g, (sx, 0, 0, sy, x0 - a0 * sx, y0 - b0 * sy))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--t", type=float, default=12)
    ap.add_argument("--chars", default="0123456789")
    a = ap.parse_args()
    f = TTFont(a.src)
    for c in a.chars:
        write(f, c, grow(glyph_path(f, c), a.t))
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
