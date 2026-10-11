"""MaxOCR Smart: readable glyphs in words and numbers, OCR glyphs and extra space where letters meet digits.

Engines read all-letter words and all-digit numbers well; they fail where a letter touches a digit
(codes such as 4KOT or B0K). Starting from MaxOCR Text:
  --alternates  adds the MaxOCR Machine form of every glyph that differs (named <glyph>.ocr) and an
                OpenType contextual-alternates (calt) feature that swaps it in when the glyph's
                immediate neighbour is of the other kind (a digit next to a letter, a letter next to a digit);
  --kern N      adds N font units of space at every letter-digit and digit-letter boundary (kern feature).
Words and numbers are unchanged. Applications that ignore calt (Word by default) show the readable forms.

    python scripts/smart_font.py TEXT.ttf MACHINE.ttf DST.ttf [--alternates] [--kern 100] [--family NAME]
"""
import argparse
import copy

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"


def same_glyph(fa, fb, na, nb) -> bool:
    ga, gb = fa["glyf"][na], fb["glyf"][nb]
    if ga.numberOfContours != gb.numberOfContours or fa["hmtx"][na] != fb["hmtx"][nb]:
        return False
    if ga.numberOfContours == 0:
        return True
    return list(ga.getCoordinates(fa["glyf"])[0]) == list(gb.getCoordinates(fb["glyf"])[0])


def build(text: str, machine: str, dst: str, alternates: bool, kern: int, family: str | None) -> str:
    f, m = TTFont(text), TTFont(machine)
    cf, cm = f.getBestCmap(), m.getBestCmap()
    name = {c: cf[ord(c)] for c in LETTERS + DIGITS}
    alt = {}
    if alternates:
        order = f.getGlyphOrder()
        for c in LETTERS + DIGITS:
            if not same_glyph(f, m, name[c], cm[ord(c)]):
                a = name[c] + ".ocr"
                f["glyf"].glyphs[a] = copy.deepcopy(m["glyf"][cm[ord(c)]])
                f["hmtx"].metrics[a] = m["hmtx"][cm[ord(c)]]
                order.append(a)
                alt[c] = a
        f.setGlyphOrder(order)
        f["glyf"].setGlyphOrder(order)
    cls = lambda chars, alts=True: "[" + " ".join([name[c] for c in chars] + ([alt[c] for c in chars if c in alt] if alts else [])) + "]"  # noqa: E731
    fea = [f"@LET = {cls(LETTERS)};", f"@DIG = {cls(DIGITS)};"]
    if alt:
        ls = [c for c in LETTERS if c in alt]
        ds = [c for c in DIGITS if c in alt]
        fea += [f"@LSRC = [{' '.join(name[c] for c in ls)}];", f"@LALT = [{' '.join(alt[c] for c in ls)}];",
                f"@DSRC = [{' '.join(name[c] for c in ds)}];", f"@DALT = [{' '.join(alt[c] for c in ds)}];",
                "lookup OCR_L { sub @LSRC by @LALT; } OCR_L;",
                "lookup OCR_D { sub @DSRC by @DALT; } OCR_D;",
                "feature calt {",
                "  sub @DSRC' lookup OCR_D @LET;",
                "  sub @LET @DSRC' lookup OCR_D;",
                "  sub @LSRC' lookup OCR_L @DIG;",
                "  sub @DIG @LSRC' lookup OCR_L;",
                "} calt;"]
    if kern:
        fea += ["feature kern {", f"  pos @LET @DIG {kern};", f"  pos @DIG @LET {kern};", "} kern;"]
    addOpenTypeFeaturesFromString(f, "\n".join(fea))
    f.save(dst)
    if family:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from export_font import export
        export(dst, dst, family)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("machine")
    ap.add_argument("dst")
    ap.add_argument("--alternates", action="store_true")
    ap.add_argument("--kern", type=int, default=0)
    ap.add_argument("--family")
    a = ap.parse_args()
    print(build(a.text, a.machine, a.dst, a.alternates, a.kern, a.family))


if __name__ == "__main__":
    main()
