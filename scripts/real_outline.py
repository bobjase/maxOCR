"""Put the donor's real vector outline back in place of a traced copy (2026-10-13: the C, O, g, t and J adopted in
v0.95/v0.96 came through the screening tool, which traces a bitmap, so they are polygons of 200-600 corner points
that look jagged when enlarged). The donor's own outline is stretched onto the current glyph's ink box exactly, so
size, position, advance and side bearings stay as they are; only the edges become real curves.

    python scripts/real_outline.py SRC.ttf DST.ttf C=vendor/ofl/ebgaramond/EBGaramond[wght].ttf O=...
"""
import argparse

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


def replace(f: TTFont, ch: str, donor: str) -> tuple:
    d = TTFont(donor)
    dgs, src = d.getGlyphSet(), d.getBestCmap()[ord(ch)]
    rec = DecomposingRecordingPen(dgs)
    dgs[src].draw(rec)
    bp = BoundsPen(None)
    rec.replay(bp)
    dx0, dy0, dx1, dy1 = bp.bounds
    name = f.getBestCmap()[ord(ch)]
    g = f["glyf"][name]
    g.recalcBounds(f["glyf"])
    x0, y0, x1, y1 = g.xMin, g.yMin, g.xMax, g.yMax
    sx, sy = (x1 - x0) / (dx1 - dx0), (y1 - y0) / (dy1 - dy0)
    tt = TTGlyphPen(None)
    rec.replay(TransformPen(Cu2QuPen(tt, max_err=0.5, reverse_direction="CFF " in d),
                            (sx, 0, 0, sy, x0 - dx0 * sx, y0 - dy0 * sy)))
    new = tt.glyph()
    new.recalcBounds(f["glyf"])
    before = g.getCoordinates(f["glyf"])[0]
    f["glyf"][name] = new
    f["hmtx"][name] = (f["hmtx"][name][0], new.xMin)
    return len(before), len(new.getCoordinates(f["glyf"])[0]), round(sx / sy, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("pairs", nargs="+", help="CHAR=DONOR.ttf")
    a = ap.parse_args()
    f = TTFont(a.src)
    for pair in a.pairs:
        ch, donor = pair.split("=", 1)
        print(ch, "points before, after, width/height stretch:", replace(f, ch, donor))
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
