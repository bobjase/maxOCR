"""Add the Russian Cyrillic alphabet (А-я, Ё ё) to MaxOCR (2026-10-17, glyph sweep: "If you manage to finish
Hebrew, move on to Cyrillic").

Letters that are the same shape as Latin ones (А В Е К М Н О Р С Т Х, а е о р с у х) reuse MaxOCR's own Latin
glyphs, so the two alphabets match; the rest come from an OFL donor, sized and weighted as in hebrew_build.py.
With --from FONT:CHARS, those letters come from other donors (the letter-by-letter sweep).

    python scripts/cyrillic_build.py SRC.ttf DST.ttf --donor vendor/ofl/ptserif/PT_Serif-Web-Regular.ttf
"""
import argparse
import copy
import os
import sys

from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path  # noqa: E402
from hebrew_build import add, stroke  # noqa: E402
from inline_lines import to_shape  # noqa: E402

CYRILLIC = [chr(c) for c in range(0x410, 0x450)] + ["Ё", "ё"]
SAME = dict(zip("АВЕКМНОРСТХаеорсух", "ABEKMHOPCTXaeopcyx"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--donor", required=True)
    ap.add_argument("--from", dest="extra", action="append", default=[], help="FONT:CHARS from another donor")
    a = ap.parse_args()
    f = TTFont(a.src)
    target = stroke(to_shape(glyph_path(f, "n")))
    donor = TTFont(a.donor)
    cm = f.getBestCmap()
    for ch in CYRILLIC:
        if ch in SAME:
            name = "uni%04X" % ord(ch)
            order = f.getGlyphOrder() + [name]
            f.setGlyphOrder(order)
            f["glyf"].glyphOrder = order
            src = cm[ord(SAME[ch])]
            f["glyf"][name] = copy.deepcopy(f["glyf"][src])
            f["hmtx"][name] = f["hmtx"][src]
            for t in f["cmap"].tables:
                if t.isUnicode():
                    t.cmap[ord(ch)] = name
        else:
            add(f, donor, ch, target)
    for spec in a.extra:
        path, chars = spec.rsplit(":", 1)
        other = TTFont(path)
        for ch in chars:
            add(f, other, ch, target)
    if "post" in f:
        f["post"].formatType = 2.0
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
