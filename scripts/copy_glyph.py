"""Copy a glyph's original vector outline (real curves) from a donor font into a MaxOCR font: scaled so the donor's
capital height becomes MaxOCR's (700 units), advance scaled the same way, then set on the exact height band
(exact_heights.py, uniform scale, so the donor's proportions are kept). No bitmap tracing involved.

    python scripts/copy_glyph.py BASE.ttf DONOR.ttf DST.ttf --chars fgj
"""
import argparse

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from exact_heights import exact

CAP = 700


def cap_height(f: TTFont) -> float:
    gs = f.getGlyphSet()
    pen = BoundsPen(gs)
    gs[f.getBestCmap()[ord("H")]].draw(pen)
    return pen.bounds[3] - pen.bounds[1]


def copy_glyphs(base: str, donor: str, chars: str, dst: str) -> str:
    f, d = TTFont(base), TTFont(donor)
    s = CAP / cap_height(d)
    dgs, dcm, fcm = d.getGlyphSet(), d.getBestCmap(), f.getBestCmap()
    for c in chars:
        src, name = dcm[ord(c)], fcm[ord(c)]
        tt = TTGlyphPen(None)
        rec = DecomposingRecordingPen(dgs)   # composite glyphs (dotless j + dot) become plain outlines
        dgs[src].draw(rec)
        rec.replay(TransformPen(Cu2QuPen(tt, max_err=1.0, reverse_direction="CFF " in d), (s, 0, 0, s, 0, 0)))
        g = tt.glyph()
        g.recalcBounds(f["glyf"])
        f["glyf"][name] = g
        f["hmtx"][name] = (int(round(d["hmtx"][src][0] * s)), g.xMin)
    f.save(dst)
    for c in chars:
        exact(dst, dst, only=c, uniform_lower=True)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("donor")
    ap.add_argument("dst")
    ap.add_argument("--chars", required=True)
    a = ap.parse_args()
    print(copy_glyphs(a.base, a.donor, a.chars, a.dst))


if __name__ == "__main__":
    main()
