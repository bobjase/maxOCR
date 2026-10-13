"""Edit a glyph by moving its own outline points (TrueType point numbers, as scratch/dump_pts.py prints them), so its
curves stay the letter's own curves (James, 2026-10-13: W and U thickened by other means looked bad at the joins).

Spec (JSON): {"U": [{"move": [17, 23], "scale_x": [237, 0.918]}, {"move": [24, 36], "dx": -30},
                    {"set": 117, "to": [515, 494]}, {"delete": [118, 119]}], ...}
  move [a, b]  points a..b (inclusive): shifted by dx, dy, and/or squeezed horizontally about x0 by k (scale_x)
  set i        point i placed at "to" ("on"/"off": true makes it an on-/off-curve point)
  advance      added to the glyph's advance width
  delete [..]  points removed (applied last)

    python scripts/point_edit.py SRC.ttf DST.ttf SPEC.json
"""
import argparse
import json

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates


def edit(f: TTFont, ch: str, ops) -> None:
    glyf = f["glyf"]
    name = f.getBestCmap()[ord(ch)]
    g = glyf[name]
    coords, ends, flags = g.getCoordinates(glyf)
    pts = [list(p) for p in coords]
    flags = list(flags)
    gone = set()
    for op in ops:
        if "move" in op:
            a, b = op["move"]
            for i in range(a, b + 1):
                x, y = pts[i]
                if "scale_x" in op:
                    x0, k = op["scale_x"]
                    x = x0 + (x - x0) * k
                pts[i] = [x + op.get("dx", 0), y + op.get("dy", 0)]
        elif "set" in op:
            pts[op["set"]] = list(op["to"])
            if op.get("on"):
                flags[op["set"]] |= 1
            if op.get("off"):
                flags[op["set"]] &= ~1
        elif "delete" in op:
            gone |= set(op["delete"])
    keep = [i for i in range(len(pts)) if i not in gone]
    new_ends, start = [], 0
    for e in ends:
        n = sum(1 for i in keep if start <= i <= e)
        new_ends.append((new_ends[-1] if new_ends else -1) + n)
        start = e + 1
    g.coordinates = GlyphCoordinates([(int(round(pts[i][0])), int(round(pts[i][1]))) for i in keep])
    g.flags = bytearray(flags[i] for i in keep)
    g.endPtsOfContours = new_ends
    g.numberOfContours = len(new_ends)
    g.recalcBounds(glyf)
    f["hmtx"][name] = (f["hmtx"][name][0] + sum(op.get("advance", 0) for op in ops), g.xMin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("spec")
    a = ap.parse_args()
    f = TTFont(a.src)
    for ch, ops in json.load(open(a.spec)).items():
        edit(f, ch, ops)
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
