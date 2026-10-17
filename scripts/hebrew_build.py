"""Add the Hebrew alphabet (22 letters and 5 final forms, U+05D0-U+05EA) to MaxOCR from an OFL font that has it
(2026-10-17, glyph sweep: "If you manage to finish latin ... proceed with Hebrew letters").

Each letter keeps the donor's shape and its size relative to the donor's Latin capitals: it is scaled by
(MaxOCR H height / donor H height), so Hebrew sits next to MaxOCR's Latin as it does in the donor. Strokes are then
grown or shrunk to MaxOCR's stroke weight (measured on n: twice area over outline length). Width = donor width,
scaled. With --from FONT:CHARS, those letters come from other donors (the letter-by-letter sweep).

    python scripts/hebrew_build.py SRC.ttf DST.ttf --donor vendor/ofl/arimo/Arimo[wght].ttf [--from tinos.ttf:אב]
"""
import argparse
import os
import sys

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph
from shapely import affinity

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, write  # noqa: E402
from inline_lines import to_path, to_shape  # noqa: E402

HEBREW = [chr(c) for c in range(0x5D0, 0x5EB)]


def cap(f: TTFont) -> float:
    gs = f.getGlyphSet()
    b = BoundsPen(gs)
    gs[f.getBestCmap()[ord("H")]].draw(b)
    return b.bounds[3] - b.bounds[1]


def stroke(shape) -> float:
    return 2 * shape.area / shape.length


def add(f: TTFont, donor: TTFont, ch: str, target_stroke: float):
    k = cap(f) / cap(donor)
    dn = donor.getBestCmap()[ord(ch)]
    s = affinity.scale(to_shape(glyph_path(donor, ch)), k, k, origin=(0, 0))
    d_stroke = stroke(affinity.scale(to_shape(glyph_path(donor, "n")), k, k, origin=(0, 0)))
    s = s.buffer((target_stroke - d_stroke) / 2, quad_segs=16).simplify(0.5)
    name = "uni%04X" % ord(ch)
    if name not in f["glyf"]:
        order = f.getGlyphOrder() + [name]
        f.setGlyphOrder(order)
        f["glyf"].glyphOrder = order
        f["glyf"][name] = Glyph()
        for t in f["cmap"].tables:
            if t.isUnicode():
                t.cmap[ord(ch)] = name
    f["hmtx"][name] = (round(donor["hmtx"][dn][0] * k), 0)
    write(f, ch, to_path(s))


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
    for ch in HEBREW:
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
