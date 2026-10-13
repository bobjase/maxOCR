"""Candidates for a cleaner 6 and 8, from our own shapes (James, 2026-10-12: "6/8 better. Both still have room for
improvement").
  6_rot9  : our 9 turned half a turn (6 and 9 as rotations of each other, as many faces draw them), same box
  8_ovals : two stacked clean rings centred on one axis, the size of our 8: lower ring 70..572 x -105..355,
            upper ring 128..514 x 290..700, sides ~95 and tops/bottoms ~55 thick like our 0 and 3
    python scripts/digits_68.py BASE.ttf OUTDIR
"""
import os
import sys

import pathops
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, transformed, write

base, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)


def oval(x0, y0, x1, y1, k=0.58) -> pathops.Path:
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    p = pathops.Path(); pen = p.getPen()
    pen.moveTo((x0, cy))
    pen.curveTo((x0, cy + k * ry), (cx - k * rx, y1), (cx, y1))
    pen.curveTo((cx + k * rx, y1), (x1, cy + k * ry), (x1, cy))
    pen.curveTo((x1, cy - k * ry), (cx + k * rx, y0), (cx, y0))
    pen.curveTo((cx - k * rx, y0), (x0, cy - k * ry), (x0, cy))
    pen.closePath()
    return p


def ring(outer, inner) -> pathops.Path:
    return pathops.op(oval(*outer), oval(*inner), pathops.PathOp.DIFFERENCE)


def save(name, ch, path, lsb=None, rsb=None):
    f = TTFont(base)
    write(f, ch, path)
    gn = f.getBestCmap()[ord(ch)]
    g = f["glyf"][gn]; g.recalcBounds(f["glyf"])
    adv = f["hmtx"][gn][0]
    if lsb is not None:
        g.coordinates.translate((lsb - g.xMin, 0)); g.recalcBounds(f["glyf"])
        adv = g.xMax + rsb
    f["hmtx"][gn] = (int(round(adv)), g.xMin)
    f.save(f"{outdir}/{name}.ttf")
    print(name, "ink", g.xMin, g.xMax, g.yMin, g.yMax, "adv", adv)


f0 = TTFont(base)
cm = f0.getBestCmap()
g9 = f0["glyf"][cm[ord("9")]]; g9.recalcBounds(f0["glyf"])
adv9 = f0["hmtx"][cm[ord("9")]][0]
cx, cy = (g9.xMin + g9.xMax) / 2, (g9.yMin + g9.yMax) / 2
six = transformed(glyph_path(f0, "9"), (-1, 0, 0, -1, 2 * cx, 2 * cy))   # half a turn about the 9's centre
save("6_rot9", "6", six, lsb=adv9 - g9.xMax, rsb=g9.xMin)

lower = ring((70, -105, 572, 355), (165, -48, 477, 292))
upper = ring((128, 290, 514, 700), (218, 350, 424, 648))
eight = pathops.op(lower, upper, pathops.PathOp.UNION)
g8 = f0["glyf"][cm[ord("8")]]; g8.recalcBounds(f0["glyf"])
save("8_ovals", "8", eight, lsb=g8.xMin, rsb=f0["hmtx"][cm[ord("8")]][0] - g8.xMax)
