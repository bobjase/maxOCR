"""Thinner strokes (James, 2026-10-14: a crisper shape for small print): every outline moved inward by --d units,
which thins each stroke by 2*d and opens the holes in 6 8 9 0 by the same amount; the glyph keeps its place and
width. Corners are kept round.

    python scripts/thin_glyphs.py SRC.ttf DST.ttf --chars 0123456789 --d 6
"""
import argparse
import os
import sys

from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, write  # noqa: E402
from inline_lines import to_path, to_shape  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--chars", default="0123456789")
    ap.add_argument("--d", type=float, default=6)
    a = ap.parse_args()
    f = TTFont(a.src)
    for c in a.chars:
        g = to_shape(glyph_path(f, c))
        write(f, c, to_path(g.buffer(-a.d, quad_segs=16).simplify(0.5)))
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
