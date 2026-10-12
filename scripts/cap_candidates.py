"""Capital-letter candidates inside MaxOCR (first used for the S; was s_candidates.py): the letter of each donor
face (open licence), rebuilt at the MaxOCR cap height (maxocr/blend.py, single-ingredient recipe), or the base
font's own glyph ("self"), at a width scale, put into the base font and set on [0, cap height] (exact_heights.py;
only that letter), optionally enlarged (--heights). Scored like text_opt_lc.py: 400 random 0-9A-Za-z lines
oversampling the focus characters, s=0.5, PaddleOCR, Tesseract, EasyOCR case-sensitive; per candidate the
correct-read rate of each focus character and overall error.

    python scripts/cap_candidates.py BASE.ttf --letter S --focus Ss58 --donors tinos,lora,self [--refs name=path,...]
        [--bold 0,2] [--widths 0.8,1,1.2] [--heights 1,1.1] [--below 0.13] [--out s_candidates.csv]
--donors all: every face in out/ofl_faces.json plus self. --band lo,hi places donor glyphs on a band (digits). Writes out/report/<out>; fonts in ~/maxocr-work/s_cand/.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

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


def transform_glyph(path: str, letter: str, sx: float, sy: float, below: float = 0.0) -> None:
    """Scale the letter by (sx, sy) about its left ink edge; with sy > 1 the extra height goes `below` (share) under
    the baseline, the rest above. The advance follows the ink width."""
    f = TTFont(path)
    name = f.getBestCmap()[ord(letter)]
    g = f["glyf"][name]
    g.recalcBounds(f["glyf"])
    cap = g.yMax - g.yMin
    x0, x1 = g.xMin, g.xMax
    dy = g.yMin * (1 - sy) - below * (sy - 1) * cap
    rec = DecomposingRecordingPen(f.getGlyphSet())
    f.getGlyphSet()[name].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (sx, 0, 0, sy, x0 - sx * x0, dy)))
    f["glyf"][name] = pen.glyph()
    f["glyf"][name].recalcBounds(f["glyf"])
    adv, lsb = f["hmtx"][name]
    f["hmtx"][name] = (int(round(adv + (sx - 1) * (x1 - x0))), lsb)
    f.save(path)


def to_band(path: str, letter: str, lo: float, hi: float) -> None:
    """Scale the glyph uniformly (about its left ink edge) so its ink spans exactly [lo, hi] (font units)."""
    f = TTFont(path)
    g = f["glyf"][f.getBestCmap()[ord(letter)]]
    g.recalcBounds(f["glyf"])
    s = (hi - lo) / (g.yMax - g.yMin)
    transform_glyph(path, letter, s, s, 0.0)
    f = TTFont(path)
    g = f["glyf"][f.getBestCmap()[ord(letter)]]
    g.recalcBounds(f["glyf"])
    shift_glyph(path, letter, lo - g.yMin)


def shift_glyph(path: str, letter: str, dy: float) -> None:
    f = TTFont(path)
    name = f.getBestCmap()[ord(letter)]
    rec = DecomposingRecordingPen(f.getGlyphSet())
    f.getGlyphSet()[name].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (1, 0, 0, 1, 0, dy)))
    f["glyf"][name] = pen.glyph()
    f["glyf"][name].recalcBounds(f["glyf"])
    f.save(path)


def build(base: str, family: str, path_of: dict, out: Path, bold: float = 0.0, width: float = 1.0,
          height: float = 1.0, below: float = 0.13, letter: str = "S", band: tuple | None = None) -> str:
    """bold: SDF threshold shift (a single-font glyph needs >= 2 to change); width: horizontal scale (capital vs
    lowercase proportions); height: size relative to the cap height (uniform, like v0.4's tall S; 1 = even
    capitals), `below` of the extra under the baseline (v0.4's S: 0.13)."""
    tag = f"{letter}_{family}_b{bold:g}_w{width:g}_h{height:g}_d{below:g}"
    dst = str(out / f"{tag}.ttf")
    if family == "self":
        shutil.copy(base, dst)
        if width != 1.0:
            transform_glyph(dst, letter, width, 1.0)
    else:
        tmp = str(out / f"{tag}_blend.ttf")
        build_font(Recipe({letter: CharRecipe([Ingredient(path_of[family], 1.0)], boldness=bold, width_scale=width)},
                          name="donor"), tmp)
        add_glyphs(base, tmp, letter, dst)
    exact(dst, dst, caps=True, uniform_caps=True, only=letter)
    if band is not None and family != "self":
        to_band(dst, letter, *band)
    if height != 1.0:
        transform_glyph(dst, letter, height, height, below)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--letter", default="S")
    ap.add_argument("--focus", default="Ss58", help="characters oversampled and scored (the letter first)")
    ap.add_argument("--donors", required=True, help="OFL families, 'self' (the base's own glyph), or 'all'")
    ap.add_argument("--refs", default="", help="name=path,... scored as they are")
    ap.add_argument("--bold", default="0", help="boldness values to try per donor (blend.py units)")
    ap.add_argument("--widths", default="1", help="width scales to try per donor")
    ap.add_argument("--heights", default="1", help="size vs cap height to try (uniform scale)")
    ap.add_argument("--below", default="0.13", help="shares of the extra height below the baseline to try")
    ap.add_argument("--band", help="lo,hi font units: put donor glyphs on this band (digits: -105,700)")
    ap.add_argument("--out", default="s_candidates.csv")
    a = ap.parse_args()
    L = a.letter
    out = WORK / "s_cand"
    out.mkdir(parents=True, exist_ok=True)
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    fonts = dict(r.split("=", 1) for r in a.refs.split(",") if r)
    donors = (sorted(path_of) + ["self"]) if a.donors == "all" else a.donors.split(",")
    for fam in donors:
        for bo in (float(v) for v in a.bold.split(",")):
            if fam == "self" and bo:
                continue
            for w in (float(v) for v in a.widths.split(",")):
                for h in (float(v) for v in a.heights.split(",")):
                    for dn in (float(v) for v in a.below.split(",")) if h != 1 else (0.0,):
                        name = (f"{L} from {fam}" + (f" bold {bo:g}" if bo else "") + (f" width {w:g}" if w != 1 else "")
                                + (f" height {h:g} below {dn:g}" if h != 1 else ""))
                        try:
                            band = tuple(float(v) for v in a.band.split(",")) if a.band else None
                            fonts[name] = build(a.base, fam, path_of, out, bo, w, h, dn, L, band)
                        except Exception as e:   # a donor without the letter, or a degenerate blend
                            print(f"skip {name}: {e}", flush=True)
    from maxocr.engines.easyocr_rec import EasyOCRRec
    paddle, easy = rung0.PaddleRec(alphabet=ALNUM_ALPHABET), EasyOCRRec(alphabet=ALNUM_ALPHABET)
    lines = bank(a.focus)
    jobs = [Job(p, p, rung0.SEVERITY, "a", c) for p in fonts.values() for c in chunk(lines, 40)]
    ch, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_whitelist=ALNUM_ALPHABET)
    rows = []
    for name, p in fonts.items():
        g = ch[ch.font == p]
        r = {"candidate": name, "char_err": round(100 * float((g.pred != g.truth).mean()), 2)}
        for c in a.focus:
            h = g[g.truth == c]
            r[f"{c}_acc"] = round(100 * float(np.mean([(h[h.engine == e].pred == c).mean() for e in ENGINES])), 1)
        miss = g[(g.truth == L) & (g.pred != L)].pred.value_counts()
        r[f"{L}_read_as"] = " ".join(f"{k}:{v}" for k, v in miss.head(3).items())
        r["font"] = p
        rows.append(r)
    df = pd.DataFrame(rows).sort_values(f"{L}_acc", ascending=False)
    df.to_csv(ROOT / "out" / "report" / a.out, index=False)
    with pd.option_context("display.width", 200):
        print(df.drop(columns="font").to_string(index=False))


if __name__ == "__main__":
    main()
