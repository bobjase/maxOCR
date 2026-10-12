"""Letter-spacing variant: scale the gap between letters (both sidebearings of every glyph) by a factor,
glyph shapes unchanged. Negative sidebearings (overhangs such as v, w, y, f) are left as they are: scaling them
would push neighbours further into each other (MaxOCR Small read "vv" as "w" 37% of the time, 2026-10-12).

    python scripts/letter_spacing.py SRC.ttf DST.ttf FACTOR
"""
import sys

from fontTools.ttLib import TTFont


def respace(src: str, dst: str, k: float) -> str:
    f = TTFont(src)
    glyf, hmtx = f["glyf"], f["hmtx"]
    for name in f.getGlyphOrder():
        g = glyf[name]
        adv, lsb = hmtx[name]
        if g.numberOfContours == 0:
            hmtx[name] = (round(adv * k), lsb)
            continue
        g.recalcBounds(glyf)
        rsb = adv - g.xMax
        new_lsb, new_rsb = (round(b * k) if b > 0 else b for b in (lsb, rsb))
        dx = new_lsb - g.xMin
        coords, _, _ = g.getCoordinates(glyf)
        coords.translate((dx, 0))
        g.coordinates = coords
        g.recalcBounds(glyf)
        hmtx[name] = (g.xMax - g.xMin + new_lsb + new_rsb, new_lsb)
    f.save(dst)
    return dst


if __name__ == "__main__":
    print(respace(sys.argv[1], sys.argv[2], float(sys.argv[3])))
