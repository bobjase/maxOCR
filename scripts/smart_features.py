"""All of MaxOCR's context features in one step (2026-10-14; adding them one tool after another replaced the earlier
ones, because feaLib rebuilds GSUB/GPOS from the text it is given):

  calt  inside a code (a run of letters and digits containing a digit), small letters switch to smaller copies
        (<glyph>.code, 74% of capital height instead of 78%: fewer capital/small confusions in codes) and digits to
        identical copies (<digit>.code), so pure numbers can be told apart from codes;
  kern  (two separate lookups: in one, the letter-digit pairs' subtable shadowed the digit pairs)
        letter-digit spacing (+50 between any letter and any digit, as MaxOCR has had since v0.3) and extra space
        between the digits of pure numbers (+40 between plain digits).

    python scripts/smart_features.py TEXT.ttf DST.ttf [--ratio 0.74] [--letter-digit 50] [--number 40]
"""
import argparse
import copy
import string

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--ratio", type=float, default=0.74)
    ap.add_argument("--letter-digit", type=int, default=50)
    ap.add_argument("--number", type=int, default=40)
    a = ap.parse_args()
    f = TTFont(a.src)
    for t in ("GSUB", "GPOS"):
        if t in f:
            raise SystemExit(f"{a.src} already has {t}: give the plain Text font")
    glyf, hmtx, cm = f["glyf"], f["hmtx"], f.getBestCmap()
    gs = f.getGlyphSet()

    def height(c):
        b = BoundsPen(gs); gs[cm[ord(c)]].draw(b); return b.bounds[3] - b.bounds[1]
    k = a.ratio / (height("x") / height("H"))
    lc = [cm[ord(c)] for c in string.ascii_lowercase]
    uc = [cm[ord(c)] for c in string.ascii_uppercase]
    dg = [cm[ord(c)] for c in string.digits]
    lcc, dgc = [n + ".code" for n in lc], [n + ".code" for n in dg]
    originals = {n: copy.deepcopy(glyf[n]) for n in lc + dg}
    order = list(f.getGlyphOrder()) + lcc + dgc
    f.setGlyphOrder(order)
    glyf.glyphOrder = order
    for n, m in zip(lc, lcc):
        g = originals[n]
        c, _, _ = g.getCoordinates(glyf)
        g.coordinates = GlyphCoordinates([(round(x * k), round(y * k)) for x, y in c])
        glyf[m] = g
        g.recalcBounds(glyf)
        hmtx[m] = (round(hmtx[n][0] * k), g.xMin)
    for n, m in zip(dg, dgc):
        glyf[m] = originals[n]
        hmtx[m] = hmtx[n]
    if "post" in f:
        f["post"].formatType = 2.0
    fea = f"""
@LC = [{' '.join(lc)}];
@LCC = [{' '.join(lcc)}];
@UC = [{' '.join(uc)}];
@DG = [{' '.join(dg)}];
@DGC = [{' '.join(dgc)}];
@MARK = [@DG @DGC @LCC];
@LET = [@UC @LC @LCC];
@ANYDG = [@DG @DGC];
lookup CodeLettersRight {{
  sub @MARK @LC' by @LCC;
  sub @MARK @UC @LC' by @LCC;
  sub @MARK @UC @UC @LC' by @LCC;
  sub @MARK @UC @UC @UC @LC' by @LCC;
}} CodeLettersRight;
lookup CodeLettersLeft {{
  rsub @LC' @MARK by @LCC;
  rsub @LC' @UC @MARK by @LCC;
  rsub @LC' @UC @UC @MARK by @LCC;
  rsub @LC' @UC @UC @UC @MARK by @LCC;
}} CodeLettersLeft;
lookup CodeDigitsRight {{
  sub @LET @DG' by @DGC;
  sub @DGC @DG' by @DGC;
}} CodeDigitsRight;
lookup CodeDigitsLeft {{
  rsub @DG' @LET by @DGC;
  rsub @DG' @DGC by @DGC;
}} CodeDigitsLeft;
feature calt {{
  lookup CodeLettersRight;
  lookup CodeLettersLeft;
  lookup CodeLettersRight;
  lookup CodeDigitsRight;
  lookup CodeDigitsLeft;
}} calt;
lookup LetterDigit {{
  pos @LET @ANYDG {a.letter_digit};
  pos @ANYDG @LET {a.letter_digit};
}} LetterDigit;
lookup NumberSpace {{
  pos @DG @DG {a.number};
}} NumberSpace;
feature kern {{
  lookup LetterDigit;
  lookup NumberSpace;
}} kern;
"""
    addOpenTypeFeaturesFromString(f, fea)
    f.save(a.dst)
    print(a.dst, f"code letters {a.ratio:.2f}, letter-digit +{a.letter_digit}, numbers +{a.number}")


if __name__ == "__main__":
    main()
