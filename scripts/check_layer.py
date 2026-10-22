"""MaxOCR Check: every digit carries a faint grey underline in a colour-font layer (COLR v0 + CPAL), so a checker can
tell digits from the letters OCR mistakes them for (0/O, 5/S, 1/l, 2/Z ...) on a clean scan (James, 2026-10-21: "Only
use two kinds of marking - full line under char vs none", "lets try the colour layer"; tested at image level in
scripts/char_marks.py: on codes, 349 of 3,670 misread lines caught with 1 false alarm in 7,130).

Each digit (and its .code copy) becomes a colour glyph of two layers: the digit itself in the text colour (palette
index 0xFFFF), and an underline glyph in black at 15% opacity. Apps without colour-font support draw only the plain
digit, so the mark disappears rather than turning black.

    python scripts/check_layer.py fonts/MaxOCR.ttf out/fonts/MaxOCR-Check.ttf [--opacity 0.15]
"""
import argparse

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

GAP, THICK = 60, 30          # font units below the digit's own bottom; 30 units = 1 px at 8 pt and 300 dpi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--opacity", type=float, default=0.15)
    a = ap.parse_args()
    f = TTFont(a.src)
    gs = f.getGlyphSet(); cm = f.getBestCmap()
    digits = [cm[ord(d)] for d in "0123456789"]
    names = digits + [n + ".code" for n in digits if n + ".code" in f["glyf"]]
    order = list(f.getGlyphOrder())
    layers = {}
    for n in names:
        b = BoundsPen(gs); gs[n].draw(b); x0, y0, x1, y1 = b.bounds
        pen = TTGlyphPen(None)
        top = y0 - GAP
        pen.moveTo((x0, top)); pen.lineTo((x1, top)); pen.lineTo((x1, top - THICK)); pen.lineTo((x0, top - THICK)); pen.closePath()
        m = n + ".mark"
        order.append(m)
        f["glyf"][m] = pen.glyph()
        f["hmtx"][m] = (f["hmtx"][n][0], int(x0))
        layers[n] = [(n, 0xFFFF), (m, 0)]
    f.setGlyphOrder(order)
    f["glyf"].glyphOrder = order
    if "post" in f:
        f["post"].formatType = 2.0
    f["COLR"] = buildCOLR(layers)
    f["CPAL"] = buildCPAL([[(0.0, 0.0, 0.0, a.opacity)]])
    name = f["name"]
    for nid, val in ((1, "MaxOCR Check"), (4, "MaxOCR Check Regular"), (6, "MaxOCR-Check-Regular")):
        for rec in list(name.names):
            if rec.nameID == nid:
                name.setName(val, nid, rec.platformID, rec.platEncID, rec.langID)
    f.save(a.dst)
    print(a.dst, len(names), "colour digits, opacity", a.opacity)


if __name__ == "__main__":
    main()
