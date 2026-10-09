"""Golden mean: fonts between the original amalgam and the current (OCR-optimized) font.

For every glyph the pair discovery changed, a slider from the original glyph (w=0) to the current one
(w=1): signed-distance-field blend of the two shapes plus blended geometry (maxocr/blend.py). Thin
additions present in only one font (spurs, flicks, small blobs) fade out quickly as w drops, so the
slider also cleans. Unchanged glyphs are copied untouched from the original.

    python scripts/golden_mean.py [--levels 0.25,0.5,0.75]
Writes ~/maxocr-work/golden/w<NN>.ttf, out/fonts/MaxOCR-Text-w<NN>.ttf (named for Windows),
out/golden/fonts.json and out/golden/sheet.png.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_font import export  # noqa: E402
from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font  # noqa: E402
from maxocr.corpus import PRIMARY_ALPHABET  # noqa: E402
from maxocr.render import render  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = Path.home() / "maxocr-work" / "golden"
ORIGINAL = str(Path.home() / "maxocr-work/amalgam_opt/08BDEOQ/g06_09.ttf")


def changed_chars(a: str, b: str) -> str:
    fa, fb = TTFont(a), TTFont(b)
    ca, cb = fa.getBestCmap(), fb.getBestCmap()
    out = []
    for ch in PRIMARY_ALPHABET:
        ga, gb = fa["glyf"][ca[ord(ch)]], fb["glyf"][cb[ord(ch)]]
        same = (ga.numberOfContours == gb.numberOfContours and
                (ga.numberOfContours == 0 or
                 np.array_equal(np.array(ga.getCoordinates(fa["glyf"])[0]), np.array(gb.getCoordinates(fb["glyf"])[0]))))
        if not same or fa["hmtx"][ca[ord(ch)]] != fb["hmtx"][cb[ord(ch)]]:
            out.append(ch)
    return "".join(out)


def transplant(base: str, donor: str, chars: str, path: str) -> str:
    """Copy of `base` with `chars` taken from `donor` (both built at UPEM 1000, cap 700)."""
    f, d = TTFont(base), TTFont(donor)
    cf, cd = f.getBestCmap(), d.getBestCmap()
    for ch in chars:
        f["glyf"][cf[ord(ch)]] = d["glyf"][cd[ord(ch)]]
        f["hmtx"][cf[ord(ch)]] = d["hmtx"][cd[ord(ch)]]
    f.save(path)
    return path


def sheet(fonts: dict[str, str], path: Path, lines=("0123456789", "ABCDEFGHIJKLM", "NOPQRSTUVWXYZ",
                                                   "1I1I ILL1 71I0", "BO0K 4KOTWX7 5S2Z")):
    rows = [(n, render(p, t, size_pt=22, dpi=200)) for t in lines for n, p in fonts.items()]
    W = max(im.shape[1] for _, im in rows) + 200
    H = sum(im.shape[0] + 8 for _, im in rows) + 20 * len(lines)
    c = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(c)
    y = 0
    for k, (n, im) in enumerate(rows):
        if k and k % len(fonts) == 0:
            y += 20
        d.text((6, y + im.shape[0] // 2 - 6), n, fill=0)
        c.paste(Image.fromarray(im), (190, y))
        y += im.shape[0] + 8
    c.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", default=open(Path.home() / "maxocr-work/keep/CURRENT").read().strip())
    ap.add_argument("--levels", default="0.25,0.5,0.75")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    out = ROOT / "out" / "golden"
    out.mkdir(parents=True, exist_ok=True)
    chars = changed_chars(ORIGINAL, a.current)
    print("changed glyphs:", chars)
    fonts = {"original (w=0)": ORIGINAL}
    for w in [float(x) for x in a.levels.split(",")]:
        tag = f"w{int(round(w * 100)):02d}"
        recipe = Recipe({ch: CharRecipe([Ingredient(ORIGINAL, 1 - w), Ingredient(a.current, w)]) for ch in chars},
                        name=f"MaxOCR golden {tag}")
        tmp = build_font(recipe, str(WORK / f"{tag}_blend.ttf"))
        path = transplant(ORIGINAL, tmp, chars, str(WORK / f"{tag}.ttf"))
        export(path, str(ROOT / "out" / "fonts" / f"MaxOCR-Text-{tag}.ttf"), f"MaxOCR Text {tag}")
        fonts[f"slider {tag}"] = path
    fonts["current (w=1)"] = a.current
    (out / "fonts.json").write_text(json.dumps(fonts, indent=1))
    sheet(fonts, out / "sheet.png")
    print(json.dumps(fonts, indent=1))


if __name__ == "__main__":
    main()
