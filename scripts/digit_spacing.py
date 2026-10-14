"""Extra space between neighbouring digits (James, 2026-10-14: "give pure number sequences a bit of additional
width-spacing"): a kerning pair for every digit followed by a digit, so numbers spread out while letters, words and
letter-digit spacing are unchanged.

    python scripts/digit_spacing.py SRC.ttf DST.ttf --units 40
"""
import argparse
import string

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--units", type=int, default=40)
    a = ap.parse_args()
    f = TTFont(a.src)
    cm = f.getBestCmap()
    dg = " ".join(cm[ord(c)] for c in string.digits)
    addOpenTypeFeaturesFromString(f, f"@DIGITS = [{dg}];\nfeature kern {{ pos @DIGITS @DIGITS {a.units}; }} kern;\n")
    f.save(a.dst)
    print(a.dst, f"+{a.units} between digits")


if __name__ == "__main__":
    main()
