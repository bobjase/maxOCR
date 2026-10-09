"""Golden mean: fonts between the original amalgam and the current (OCR-optimized) font.

For every glyph the pair discovery changed, a slider from the original glyph (w=0) to the current one
(w=1): signed-distance-field blend of the two shapes plus blended geometry (maxocr/blend.py). Thin
additions present in only one font (spurs, flicks, small blobs) fade out quickly as w drops, so the
slider also cleans. Unchanged glyphs are copied untouched from the original.

    python scripts/golden_mean.py [--levels 0.25,0.5,0.75]
    python scripts/golden_mean.py --mix "02BOSTZ:1,45678AG:0.25,1I:0.25,J:0" --tag mixA
      (per-glyph levels: 1 = current glyph, 0 = original glyph, otherwise a blend)
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


def mix(current: str, spec: str, tag: str) -> str:
    """One font with a level per glyph; glyphs not named keep their current form."""
    WORK.mkdir(parents=True, exist_ok=True)
    levels = {ch: float(w) for part in spec.split(",") for chars, w in [part.split(":")] for ch in chars}
    path = str(WORK / f"{tag}.ttf")
    f = TTFont(current)
    f.save(path)
    orig_chars = "".join(ch for ch, w in levels.items() if w == 0)
    if orig_chars:
        transplant(path, ORIGINAL, orig_chars, path)
    for w in sorted({w for w in levels.values() if 0 < w < 1}):
        chars = "".join(ch for ch, x in levels.items() if x == w)
        recipe = Recipe({ch: CharRecipe([Ingredient(ORIGINAL, 1 - w), Ingredient(current, w)]) for ch in chars},
                        name=f"MaxOCR golden {tag}")
        tmp = build_font(recipe, str(WORK / f"{tag}_w{int(w * 100)}_blend.ttf"))
        transplant(path, tmp, chars, path)
    export(path, str(ROOT / "out" / "fonts" / f"MaxOCR-Text-{tag}.ttf"), f"MaxOCR Text {tag}")
    print(f"{tag}: {path}  ({spec})")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", default=open(Path.home() / "maxocr-work/keep/CURRENT").read().strip())
    ap.add_argument("--levels", default="0.25,0.5,0.75")
    ap.add_argument("--mix", help="per-glyph levels, e.g. '02BOSTZ:1,45678AG:0.25,1IJ:0'")
    ap.add_argument("--tag", default="mix")
    a = ap.parse_args()
    if a.mix:
        return mix(a.current, a.mix, a.tag)
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
