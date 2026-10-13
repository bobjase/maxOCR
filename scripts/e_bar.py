"""e with a thicker crossbar (Courier Prime analysis, 2026-10-13: at half resolution our e's 50-unit bar vanishes and
the e is read as c). The bar is thickened downward (the eye keeps its size), its right end kept where it is.
    python scripts/e_bar.py SRC.ttf DST.ttf --add 25
"""
import argparse
import os
import sys

import pathops
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import clip, glyph_path, rect, write

BIG = 3000


def thicker_bar(p: pathops.Path, add: float) -> pathops.Path:
    """The bar is where the e's centre column has ink between heights 200 and 400; it is thickened downward."""
    x0, _, x1, _ = p.bounds
    xm = (x0 + x1) / 2
    _, y0, _, y1 = clip(p, (xm - 1, 200, xm + 1, 400)).bounds          # the bar's bottom and top at the centre
    a, _, b, _ = clip(p, (-BIG, y0 + 3, BIG, y0 + 5)).bounds              # its left and right ends near the bottom
    return pathops.op(p, rect(a + 10, y0 - add, b, y0 + 4), pathops.PathOp.UNION), (round(y0), round(y1), round(a), round(b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--add", type=float, default=25)
    a = ap.parse_args()
    f = TTFont(a.src)
    p, info = thicker_bar(glyph_path(f, "e"), a.add)
    write(f, "e", p)
    f.save(a.dst)
    print(a.dst, "bar bottom, left, right:", info)


if __name__ == "__main__":
    main()
