"""Add a-z to a MaxOCR font: each letter an equal SDF blend of the three serif faces that dominate the
capitals' recipes (IBM Plex Serif, Spectral, Gelasio), built at the MaxOCR cap height (maxocr/blend.py) and
merged into the target as new glyphs (cmap, glyf, hmtx).

    python scripts/add_lowercase.py SRC.ttf DST.ttf [--chars abc...]
"""
import argparse
import copy
import json
from pathlib import Path

from fontTools.ttLib import TTFont

from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font

ROOT = Path(__file__).resolve().parents[1]
FACES = ("ibmplexserif", "spectral", "gelasio")
LOWER = "abcdefghijklmnopqrstuvwxyz"


def add_glyphs(base: str, donor: str, chars: str, path: str) -> str:
    """Copy of `base` with `chars` taken from `donor`: replaced if present, otherwise added (cmap too)."""
    f, d = TTFont(base), TTFont(donor)
    cf, cd = f.getBestCmap(), d.getBestCmap()
    order = f.getGlyphOrder()
    for ch in chars:
        src = cd[ord(ch)]
        name = cf.get(ord(ch), f"uni{ord(ch):04X}")
        f["glyf"].glyphs[name] = copy.deepcopy(d["glyf"][src])
        f["hmtx"].metrics[name] = d["hmtx"][src]
        if name not in order:
            order.append(name)
        for t in f["cmap"].tables:
            if t.isUnicode():
                t.cmap[ord(ch)] = name
    f.setGlyphOrder(order)
    f["glyf"].setGlyphOrder(order)
    f.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--chars", default=LOWER)
    a = ap.parse_args()
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    recipe = Recipe({c: CharRecipe([Ingredient(path_of[f], 1.0) for f in FACES]) for c in a.chars}, name="MaxOCR lowercase")
    tmp = a.dst.replace(".ttf", "_lc_blend.ttf")
    build_font(recipe, tmp)
    print(add_glyphs(a.src, tmp, a.chars, a.dst))


if __name__ == "__main__":
    main()
