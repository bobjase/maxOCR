"""Capital S candidates inside MaxOCR: the S of each donor face (open licence), rebuilt at the MaxOCR cap height
(maxocr/blend.py, single-ingredient recipe), put into the base font and set on [0, cap height]
(exact_heights.py). Scored like text_opt_lc.py: 400 random 0-9A-Za-z lines oversampling S, s, 5, 8, s=0.5,
PaddleOCR, Tesseract, EasyOCR case-sensitive; per candidate the correct-read rate of S, s, 5, 8 and overall error.

    python scripts/s_candidates.py BASE.ttf --donors tinos,lora,publicsans [--refs name=path,...] [--bold 0,2]
        [--widths 0.8,1,1.2] [--out s_candidates.csv]
Writes out/report/s_candidates.csv; fonts in ~/maxocr-work/s_cand/.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from add_lowercase import add_glyphs  # noqa: E402
from exact_heights import exact  # noqa: E402
from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font  # noqa: E402
from maxocr.build import WORK  # noqa: E402
from maxocr.corpus import ALNUM_ALPHABET  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from text_opt_lc import bank  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ("paddle", "tesseract", "easyocr")
FOCUS = "Ss58"


def enlarge_s(path: str, h: float, below: float) -> None:
    """Scale the S uniformly to h x cap height; the extra height goes `below` (share) under the baseline."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont
    f = TTFont(path)
    name = f.getBestCmap()[ord("S")]
    g = f["glyf"][name]
    g.recalcBounds(f["glyf"])
    cap = g.yMax - g.yMin
    x0, x1 = g.xMin, g.xMax
    dy = g.yMin * (1 - h) - below * (h - 1) * cap
    rec = DecomposingRecordingPen(f.getGlyphSet())
    f.getGlyphSet()[name].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (h, 0, 0, h, x0 - h * x0, dy)))
    f["glyf"][name] = pen.glyph()
    f["glyf"][name].recalcBounds(f["glyf"])
    adv, lsb = f["hmtx"][name]
    f["hmtx"][name] = (int(round(adv + (h - 1) * (x1 - x0))), lsb)
    f.save(path)


def build(base: str, family: str, path_of: dict, out: Path, bold: float = 0.0, width: float = 1.0,
          height: float = 1.0, below: float = 0.13) -> str:
    """bold: SDF threshold shift (a single-font S needs >= 2 to change); width: horizontal scale (S vs s proportions);
    height: S size relative to the cap height (uniform, like v0.4's tall S; 1 = even capitals), `below` of the extra
    under the baseline (v0.4's S: 0.13)."""
    tag = f"S_{family}_b{bold:g}_w{width:g}_h{height:g}_d{below:g}"
    tmp = str(out / f"{tag}_blend.ttf")
    build_font(Recipe({"S": CharRecipe([Ingredient(path_of[family], 1.0)], boldness=bold, width_scale=width)},
                      name="S donor"), tmp)
    dst = str(out / f"{tag}.ttf")
    add_glyphs(base, tmp, "S", dst)
    exact(dst, dst, caps=True, uniform_caps=True)
    if height != 1.0:
        enlarge_s(dst, height, below)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--donors", required=True)
    ap.add_argument("--refs", default="", help="name=path,... scored as they are")
    ap.add_argument("--bold", default="0", help="boldness values to try per donor (blend.py units)")
    ap.add_argument("--widths", default="1", help="width scales to try per donor")
    ap.add_argument("--heights", default="1", help="S size vs cap height to try (uniform scale)")
    ap.add_argument("--below", default="0.13", help="shares of the extra height below the baseline to try")
    ap.add_argument("--out", default="s_candidates.csv")
    a = ap.parse_args()
    out = WORK / "s_cand"
    out.mkdir(parents=True, exist_ok=True)
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    fonts = dict(r.split("=", 1) for r in a.refs.split(",") if r)
    for fam in a.donors.split(","):
        for b in (float(v) for v in a.bold.split(",")):
            for w in (float(v) for v in a.widths.split(",")):
                for h in (float(v) for v in a.heights.split(",")):
                    for dn in (float(v) for v in a.below.split(",")) if h != 1 else (0.0,):
                        name = (f"S from {fam}" + (f" bold {b:g}" if b else "") + (f" width {w:g}" if w != 1 else "")
                                + (f" height {h:g} below {dn:g}" if h != 1 else ""))
                        fonts[name] = build(a.base, fam, path_of, out, b, w, h, dn)
    from maxocr.engines.easyocr_rec import EasyOCRRec
    paddle, easy = rung0.PaddleRec(alphabet=ALNUM_ALPHABET), EasyOCRRec(alphabet=ALNUM_ALPHABET)
    b = bank(FOCUS)
    jobs = [Job(p, p, rung0.SEVERITY, "a", c) for p in fonts.values() for c in chunk(b, 40)]
    ch, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_whitelist=ALNUM_ALPHABET)
    rows = []
    for name, p in fonts.items():
        g = ch[ch.font == p]
        r = {"candidate": name, "char_err": round(100 * float((g.pred != g.truth).mean()), 2)}
        for c in FOCUS:
            h = g[g.truth == c]
            r[f"{c}_acc"] = round(100 * float(np.mean([(h[h.engine == e].pred == c).mean() for e in ENGINES])), 1)
        miss = g[(g.truth == "S") & (g.pred != "S")].pred.value_counts()
        r["S_read_as"] = " ".join(f"{k}:{v}" for k, v in miss.head(3).items())
        r["font"] = p
        rows.append(r)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / a.out, index=False)
    with pd.option_context("display.width", 200):
        print(df.drop(columns="font").to_string(index=False))


if __name__ == "__main__":
    main()
