"""MaxOCR Hatch: the same digit underline as MaxOCR Check, but grey made the toner-saver way (James, 2026-10-21: "Can
we make it gray using the toner saver font style?"): an ordinary outline, no colour layer, filled with fine diagonal
hatch lines so it prints as a light grey band in any app. The band has to be taller than Check's hairline to hold the
hatching (about 3 px at 8 pt and 300 dpi); hatch lines about one 600-dpi printer dot wide at 8 pt, about 20% coverage.

    python scripts/hatch_layer.py fonts/MaxOCR.ttf out/fonts/MaxOCR-Hatch.ttf [--line 15 --pitch 75 --name "MaxOCR Hatch"]

Lighter options (James, 2026-10-22: on the scan the hatching left specks after black-and-white conversion and Tesseract
dropped 10-pt number lines; "make 3 options for lighter hatches"): thinner lines (--line), sparser lines (--pitch).
"""
import argparse
import os
import sys

import pathops
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, rect, write  # noqa: E402

GAP, BAND, LINE, PITCH = 60, 90, 10, 75     # font units (line 10: option C from the 2026-10-23 scan; 15 was option B)


def hatch(x0, x1, top, LINE=LINE, PITCH=PITCH):
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
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--line", type=float, default=LINE); ap.add_argument("--pitch", type=float, default=PITCH)
    ap.add_argument("--name", default="MaxOCR Hatch")
    a = ap.parse_args()
    f = TTFont(a.src)
    gs = f.getGlyphSet(); cm = f.getBestCmap()
    digits = [cm[ord(d)] for d in "0123456789"]
    rev = {v: k for k, v in cm.items()}
    for n in digits + [d + ".code" for d in digits if d + ".code" in f["glyf"]]:
        b = BoundsPen(gs); gs[n].draw(b); x0, y0, x1, y1 = b.bounds
        base = n.replace(".code", "")
        p = glyph_path(f, chr(rev[base])) if n == base else None
        if p is None:                    # .code copies: draw their own outline
            p = pathops.Path(); gs[n].draw(p.getPen())
        p = pathops.op(p, hatch(x0, x1, y0 - GAP, a.line, a.pitch), pathops.PathOp.UNION)
        if n == base:
            write(f, chr(rev[base]), p)
        else:
            from fontTools.pens.cu2quPen import Cu2QuPen
            from fontTools.pens.ttGlyphPen import TTGlyphPen
            tt = TTGlyphPen(None); p.draw(Cu2QuPen(tt, max_err=0.5, reverse_direction=True))
            g = tt.glyph(); g.recalcBounds(f["glyf"]); f["glyf"][n] = g
            f["hmtx"][n] = (f["hmtx"][n][0], g.xMin)
    for nid, val in ((1, a.name), (4, a.name + " Regular"), (6, a.name.replace(" ", "-") + "-Regular")):
        for r in list(f["name"].names):
            if r.nameID == nid:
                f["name"].setName(val, nid, r.platformID, r.platEncID, r.langID)
    ps = a.name.replace(" ", "-") + "-Regular"
    for r in list(f["name"].names):          # unique ID: otherwise Windows treats it as the same font as MaxOCR
        if r.nameID == 3:
            f["name"].setName(str(r).rsplit(";", 1)[0] + ";" + ps, 3, r.platformID, r.platEncID, r.langID)
    f.save(a.dst)
    print(a.dst, "line", a.line, "pitch", a.pitch)


if __name__ == "__main__":
    main()
