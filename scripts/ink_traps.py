"""Ink traps (James, 2026-10-14: "I want ink traps"): small rounded notches cut into the inside corners of a glyph,
where two strokes meet. When ink spreads, it fills the notch instead of closing the corner, so the shape survives
ink bleed (the type designer's answer for small print on soft paper).

An inside corner is an on-curve point where the outline turns sharply the "wrong" way for ink (a concave turn:
TrueType puts ink on the right of travel, so a left turn of more than --min-turn degrees). At each one a disc of
radius r, centred a little into the ink along the corner's bisector, is cut away.

    python scripts/ink_traps.py SRC.ttf DST.ttf --chars 0123456789 --r 18 [--report]
"""
import argparse
import math
import os
import sys

import pathops
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, write  # noqa: E402


def disc(cx, cy, r, n=24) -> pathops.Path:
    p = pathops.Path()
    pen = p.getPen()
    pts = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    pen.moveTo(pts[0])
    for q in pts[1:]:
        pen.lineTo(q)
    pen.closePath()
    return p


def inside_corners(f: TTFont, ch: str, min_turn: float) -> list[tuple[float, float, float, float]]:
    """(x, y, bisector x, bisector y into the ink) of every concave corner."""
    g = f["glyf"][f.getBestCmap()[ord(ch)]]
    coords, ends, flags = g.getCoordinates(f["glyf"])
    out, start = [], 0
    for end in ends:
        idx = list(range(start, end + 1))
        n = len(idx)
        for k in range(n):
            i, a, b = idx[k], idx[k - 1], idx[(k + 1) % n]
            if not flags[i] & 1:
                continue
            (x, y), (xa, ya), (xb, yb) = coords[i], coords[a], coords[b]
            u = (x - xa, y - ya); v = (xb - x, yb - y)
            lu, lv = math.hypot(*u), math.hypot(*v)
            if lu < 1 or lv < 1:
                continue
            u = (u[0] / lu, u[1] / lu); v = (v[0] / lv, v[1] / lv)
            cross = u[0] * v[1] - u[1] * v[0]
            turn = math.degrees(math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1]))))
            if cross > 0 and turn >= min_turn:          # left turn: an inside corner
                # into the ink = right of travel, averaged over both edges
                rx, ry = (u[1] + v[1]), -(u[0] + v[0])
                lr = math.hypot(rx, ry) or 1
                out.append((x, y, rx / lr, ry / lr))
        start = end + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--chars", default="0123456789")
    ap.add_argument("--r", type=float, default=18)
    ap.add_argument("--depth", type=float, default=0.5, help="disc centre this many radii into the ink")
    ap.add_argument("--min-turn", type=float, default=35)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    f = TTFont(a.src)
    for c in a.chars:
        corners = inside_corners(f, c, a.min_turn)
        if a.report:
            print(c, [(round(x), round(y)) for x, y, _, _ in corners])
            continue
        p = glyph_path(f, c)
        for x, y, bx, by in corners:
            p = pathops.op(p, disc(x + bx * a.r * a.depth, y + by * a.r * a.depth, a.r), pathops.PathOp.DIFFERENCE)
        write(f, c, p)
    if not a.report:
        f.save(a.dst)
        print(a.dst)


if __name__ == "__main__":
    main()
