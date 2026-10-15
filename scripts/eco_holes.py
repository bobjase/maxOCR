"""Ecofont-style holes (James, 2026-10-14): small round holes punched inside the strokes, the outline left solid.
Under ink bleed the spreading ink fills the holes first instead of fattening the stroke outward. Holes sit on a
grid; a hole is kept only where it fits inside the stroke with --margin of ink all around it.

    python scripts/eco_holes.py SRC.ttf DST.ttf --chars 0123456789 --r 22 --gap 14 --margin 22
"""
import argparse
import math
import os
import sys

from fontTools.ttLib import TTFont
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, write  # noqa: E402
from inline_lines import to_path, to_shape  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--chars", default="0123456789")
    ap.add_argument("--r", type=float, default=22, help="hole radius")
    ap.add_argument("--gap", type=float, default=14, help="ink between neighbouring holes")
    ap.add_argument("--margin", type=float, default=22, help="ink between a hole and the outline")
    a = ap.parse_args()
    f = TTFont(a.src)
    step = 2 * a.r + a.gap
    for c in a.chars:
        g = to_shape(glyph_path(f, c))
        room = g.buffer(-(a.r + a.margin))
        if room.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        holes = []
        for j in range(int((y1 - y0) / (step * math.sqrt(3) / 2)) + 2):        # staggered rows, like Ecofont
            y = y0 + j * step * math.sqrt(3) / 2
            for i in range(int((x1 - x0) / step) + 2):
                p = Point(x0 + i * step + (step / 2 if j % 2 else 0), y)
                if room.contains(p):
                    holes.append(p.buffer(a.r, quad_segs=8))
        res = g
        for h in holes:
            res = res.difference(h)
        write(f, c, to_path(res))
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
