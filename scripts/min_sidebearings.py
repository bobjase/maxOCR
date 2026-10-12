"""Minimum sidebearings: diagonal letters borrowed or blended from other fonts (v, w, y) have negative sidebearings,
so "vv" touches and reads as "w" (lowercase merge test, 2026-10-12: MaxOCR 15.8%, Courier New 0%). Each listed glyph
gets at least M font units of space on each side (shape unchanged; the glyph moves right and the advance grows).

    python scripts/min_sidebearings.py SRC.ttf DST.ttf --chars vwy --min 30
"""
import argparse

from fontTools.ttLib import TTFont


def min_sidebearings(src: str, dst: str, chars: str, m: int) -> dict:
    f = TTFont(src)
    glyf, hmtx, cm = f["glyf"], f["hmtx"], f.getBestCmap()
    out = {}
    for c in chars:
        name = cm[ord(c)]
        g = glyf[name]
        g.recalcBounds(glyf)
        adv, _ = hmtx[name]
        lsb, rsb = g.xMin, adv - g.xMax
        new_lsb, new_rsb = max(lsb, m), max(rsb, m)
        coords, _, _ = g.getCoordinates(glyf)
        coords.translate((new_lsb - lsb, 0))
        g.coordinates = coords
        g.recalcBounds(glyf)
        hmtx[name] = (g.xMax - g.xMin + new_lsb + new_rsb, new_lsb)
        out[c] = ((lsb, rsb), (new_lsb, new_rsb))
    f.save(dst)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--chars", default="vwy")
    ap.add_argument("--min", type=int, default=30)
    a = ap.parse_args()
    print(min_sidebearings(a.src, a.dst, a.chars, a.min))


if __name__ == "__main__":
    main()
