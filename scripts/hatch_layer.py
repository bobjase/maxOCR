"""MaxOCR Hatch: the same digit underline as MaxOCR Check, but grey made the toner-saver way (James, 2026-10-21: "Can
we make it gray using the toner saver font style?"): an ordinary outline, no colour layer, filled with fine diagonal
hatch lines so it prints as a light grey band in any app. The band has to be taller than Check's hairline to hold the
hatching (about 3 px at 8 pt and 300 dpi); hatch lines about one 600-dpi printer dot wide at 8 pt, about 20% coverage.

    python scripts/hatch_layer.py fonts/MaxOCR.ttf out/fonts/MaxOCR-Hatch.ttf
"""
import os
import sys

import pathops
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, rect, write  # noqa: E402

GAP, BAND, LINE, PITCH = 60, 90, 15, 75     # font units


def hatch(x0, x1, top):
    """Diagonal hatch lines clipped to the band [x0, x1] x [top - BAND, top]."""
    lines = pathops.Path()
    pen = lines.getPen()
    y0 = top - BAND
    x = x0 - BAND
    while x < x1:
        pen.moveTo((x, y0)); pen.lineTo((x + LINE, y0)); pen.lineTo((x + LINE + BAND, top)); pen.lineTo((x + BAND, top))
        pen.closePath()
        x += PITCH
    return pathops.op(lines, rect(x0, y0, x1, top), pathops.PathOp.INTERSECTION)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    f = TTFont(src)
    gs = f.getGlyphSet(); cm = f.getBestCmap()
    digits = [cm[ord(d)] for d in "0123456789"]
    rev = {v: k for k, v in cm.items()}
    for n in digits + [d + ".code" for d in digits if d + ".code" in f["glyf"]]:
        b = BoundsPen(gs); gs[n].draw(b); x0, y0, x1, y1 = b.bounds
        base = n.replace(".code", "")
        p = glyph_path(f, chr(rev[base])) if n == base else None
        if p is None:                    # .code copies: draw their own outline
            p = pathops.Path(); gs[n].draw(p.getPen())
        p = pathops.op(p, hatch(x0, x1, y0 - GAP), pathops.PathOp.UNION)
        if n == base:
            write(f, chr(rev[base]), p)
        else:
            from fontTools.pens.cu2quPen import Cu2QuPen
            from fontTools.pens.ttGlyphPen import TTGlyphPen
            tt = TTGlyphPen(None); p.draw(Cu2QuPen(tt, max_err=0.5, reverse_direction=True))
            g = tt.glyph(); g.recalcBounds(f["glyf"]); f["glyf"][n] = g
            f["hmtx"][n] = (f["hmtx"][n][0], g.xMin)
    for nid, val in ((1, "MaxOCR Hatch"), (4, "MaxOCR Hatch Regular"), (6, "MaxOCR-Hatch-Regular")):
        for r in list(f["name"].names):
            if r.nameID == nid:
                f["name"].setName(val, nid, r.platformID, r.platEncID, r.langID)
    f.save(dst)
    print(dst)


if __name__ == "__main__":
    main()
