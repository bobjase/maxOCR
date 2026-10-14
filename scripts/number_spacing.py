"""Extra space between digits in pure numbers only (James, 2026-10-14). Space between every pair of digits helped
numbers (heavy damage 20.0 -> 18.3) but hurt codes, which also contain digit pairs (clean codes 3.35 -> 4.33).

Digits inside a code (a run that also has letters) are switched to identical copies (<digit>.code) by contextual
alternates, spreading from any touching letter through the digits in both directions; the extra space is then
applied only between plain digits, i.e. in pure numbers. The letter-digit spacing of MaxOCR (kern, 50 units) is
extended to the copies so codes keep it. Run after code_letters.py.

    python scripts/number_spacing.py SRC.ttf DST.ttf --units 40 [--letter-digit 50]
"""
import argparse
import copy
import string

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--units", type=int, default=40)
    ap.add_argument("--letter-digit", type=int, default=50)
    a = ap.parse_args()
    f = TTFont(a.src)
    glyf, hmtx, cm = f["glyf"], f["hmtx"], f.getBestCmap()
    dg = [cm[ord(c)] for c in string.digits]
    dgc = [n + ".code" for n in dg]
    originals = {n: copy.deepcopy(glyf[n]) for n in dg}
    order = list(f.getGlyphOrder()) + dgc
    f.setGlyphOrder(order)
    glyf.glyphOrder = order
    for n, m in zip(dg, dgc):
        glyf[m] = originals[n]
        hmtx[m] = hmtx[n]
    lc = [cm[ord(c)] for c in string.ascii_lowercase]
    letters = [cm[ord(c)] for c in string.ascii_uppercase] + lc + [n + ".code" for n in lc if n + ".code" in glyf]
    ld = a.letter_digit
    fea = f"""
@LET = [{' '.join(letters)}];
@DG = [{' '.join(dg)}];
@DGC = [{' '.join(dgc)}];
lookup CodeDigitsRight {{
  sub @LET @DG' by @DGC;
  sub @DGC @DG' by @DGC;
}} CodeDigitsRight;
lookup CodeDigitsLeft {{
  rsub @DG' @LET by @DGC;
  rsub @DG' @DGC by @DGC;
}} CodeDigitsLeft;
feature calt {{
  lookup CodeDigitsRight;
  lookup CodeDigitsLeft;
}} calt;
feature kern {{
  pos @DG @DG {a.units};
  pos @LET @DGC {ld};
  pos @DGC @LET {ld};
}} kern;
"""
    addOpenTypeFeaturesFromString(f, fea)
    f.save(a.dst)
    print(a.dst, f"+{a.units} between digits of pure numbers")


if __name__ == "__main__":
    main()
