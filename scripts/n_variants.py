"""n variants against the smudge (smudged paragraphs: our n read as m 14 times; the heavier strokes leave a ghost stem).
  narrow: the n's right half moved left by --shift units (stem widths kept, the counter narrower)
    python scripts/n_variants.py SRC.ttf DST.ttf narrow --shift 50
"""
import argparse
import os
import sys

import pathops
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import clip, glyph_path, transformed, write

BIG = 3000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("op", choices=["narrow"])
    ap.add_argument("--shift", type=float, default=50)
    a = ap.parse_args()
    f = TTFont(a.src)
    p = glyph_path(f, "n")
    x0, _, x1, _ = p.bounds
    xc = (x0 + x1) / 2
    left = clip(p, (-BIG, -BIG, xc + 2, BIG))
    right = transformed(clip(p, (xc - 2, -BIG, BIG, BIG)), (1, 0, 0, 1, -a.shift, 0))
    write(f, "n", pathops.op(left, right, pathops.PathOp.UNION))
    name = f.getBestCmap()[ord("n")]
    adv, lsb = f["hmtx"][name]
    f["hmtx"][name] = (int(round(adv - a.shift)), lsb)
    f.save(a.dst)
    print(a.dst, "n narrower by", a.shift)


if __name__ == "__main__":
    main()
