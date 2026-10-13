"""Thicken one stroke of a letter evenly, the way a type designer would (James, 2026-10-13: the automatic thickening
"looks TERRIBLE": uneven arms, scribbled W and X, flattened S). A copy of the letter is moved sideways (or up/down)
by a fixed amount, cut to a chosen region, and joined to the letter. Inside the region the stroke gains exactly
that amount on one side along its whole length: a straight edge stays straight and parallel, curves keep their
shape (they are the letter's own curves, moved), serif tips and brackets come along unchanged. The region's
borders are placed inside other strokes' ink, where the moved copy is hidden, so no cut shows.

Spec (JSON): {"V": [{"dx": -30, "dy": 0, "region": [[x, y], ...]}, ...], ...}: per character, one or more moves,
each with the polygon (font units) it applies to.

    python scripts/shift_union.py SRC.ttf DST.ttf SPEC.json [--chars VY]
"""
import argparse
import json
import os
import sys

import pathops
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, transformed, write  # noqa: E402


def polygon(pts) -> pathops.Path:
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo(tuple(pts[0]))
    for q in pts[1:]:
        pen.lineTo(tuple(q))
    pen.closePath()
    return p


def shift_union(p: pathops.Path, moves) -> pathops.Path:
    out = p
    for m in moves:
        moved = transformed(p, (1, 0, 0, 1, m.get("dx", 0), m.get("dy", 0)))
        piece = pathops.op(moved, polygon(m["region"]), pathops.PathOp.INTERSECTION)
        out = pathops.op(out, piece, pathops.PathOp.UNION)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("spec")
    ap.add_argument("--chars")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    f = TTFont(a.src)
    for c, moves in spec.items():
        if a.chars and c not in a.chars:
            continue
        write(f, c, shift_union(glyph_path(f, c), moves))
    f.save(a.dst)
    print(a.dst, "".join(c for c in spec if not a.chars or c in a.chars))


if __name__ == "__main__":
    main()
