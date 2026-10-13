"""Tighten the punctuation's spacing (James, 2026-10-12: marks borrowed from monospaced faces keep wide cells, so
"$8.49." and "1,305" look gappy). Each punctuation mark's left and right sidebearings are capped at --cap font units
(smaller ones are left alone, so nothing gets wider); the outline is shifted and the advance shrunk to match. Letters,
digits and space are untouched.

    python scripts/punct_spacing.py SRC.ttf DST.ttf --cap 80
"""
import argparse
import string

from fontTools.ttLib import TTFont


def tighten(src: str, dst: str, cap: int, marks: str = string.punctuation) -> None:
    f = TTFont(src)
    cm, glyf, hmtx = f.getBestCmap(), f["glyf"], f["hmtx"]
    for c in marks:
        name = cm.get(ord(c))
        if name is None:
            continue
        g = glyf[name]
        if g.numberOfContours <= 0:          # empty or composite: leave alone
            continue
        g.recalcBounds(glyf)
        adv, _ = hmtx[name]
        lsb, rsb = g.xMin, adv - g.xMax
        new_lsb, new_rsb = min(lsb, cap), min(rsb, cap)
        dx = new_lsb - lsb
        if dx:
            g.coordinates.translate((dx, 0))
            g.recalcBounds(glyf)
        hmtx[name] = (int(round(g.xMax + new_rsb)), g.xMin)
    f.save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--cap", type=int, required=True, help="largest sidebearing a punctuation mark keeps (font units)")
    a = ap.parse_args()
    tighten(a.src, a.dst, a.cap)
    print(a.dst, "cap", a.cap)


if __name__ == "__main__":
    main()
