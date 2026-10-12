"""Consistent digit heights (James: "should we consider dropping them all?"). v0.4/v0.5 digits are uneven: 4, 5, 8
drop ~10% below the baseline, 0 stands 20% above the cap height, 2 floats. Each variant puts every digit on one
band [bottom, top] (uniform scale, proportions kept, like the capitals), e.g. lining [0, cap], all dropped by d
[-d, cap - d], or extended below [-d, cap]. Scored like cap_candidates.py on 400 random 0-9A-Za-z lines that
oversample the digits and their look-alikes (0O o 1I l 2Z 4A 5S 6G 7T 8B 9g), s=0.5, three engines,
case-sensitive: overall character error, mean correct-read rate of the digits and of the look-alike letters.

    python scripts/digit_variants.py BASE.ttf [--drops 0,0.05,0.1,0.15] [--extend 0.1] [--bands -0.15:1.05]
Writes out/report/digit_variants.csv; fonts in ~/maxocr-work/digits/.
"""
import argparse
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
from maxocr.build import WORK  # noqa: E402
from maxocr.corpus import ALNUM_ALPHABET  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from text_opt_lc import bank  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ("paddle", "tesseract", "easyocr")
DIGITS = "0123456789"
LOOKALIKES = "OoIlZASGTBg"
CAP = 700


def set_band(src: str, dst: str, bottom: float, top: float) -> None:
    """Every digit scaled uniformly (about its left ink edge) so its ink spans exactly [bottom, top]."""
    f = TTFont(src)
    cm, gs = f.getBestCmap(), f.getGlyphSet()
    for c in DIGITS:
        name = cm[ord(c)]
        g = f["glyf"][name]
        g.recalcBounds(f["glyf"])
        s = (top - bottom) / (g.yMax - g.yMin)
        x0, x1 = g.xMin, g.xMax
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(rec)
        pen = TTGlyphPen(None)
        rec.replay(TransformPen(pen, (s, 0, 0, s, x0 - s * x0, bottom - s * g.yMin)))
        f["glyf"][name] = pen.glyph()
        f["glyf"][name].recalcBounds(f["glyf"])
        adv, lsb = f["hmtx"][name]
        f["hmtx"][name] = (int(round(adv + (s - 1) * (x1 - x0))), lsb)
    f.save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--drops", default="0,0.05,0.1,0.15", help="shift of the whole band below the baseline (x cap)")
    ap.add_argument("--extend", default="0.1", help="bands [-d, cap]: digits taller, reaching d below the baseline")
    ap.add_argument("--bands", default="", help="explicit bands bottom:top in cap units, e.g. -0.15:1.05,-0.2:1")
    ap.add_argument("--out", default="digit_variants.csv")
    a = ap.parse_args()
    out = WORK / "digits"
    out.mkdir(parents=True, exist_ok=True)
    fonts = {"current (uneven)": a.base}
    for d in (float(v) for v in a.drops.split(",") if v):
        name = "even, on the baseline" if d == 0 else f"all dropped {d:.0%}"
        fonts[name] = str(out / f"drop{d:g}.ttf")
        set_band(a.base, fonts[name], -d * CAP, CAP - d * CAP)
    for d in (float(v) for v in a.extend.split(",") if v):
        name = f"all extended {d:.0%} below"
        fonts[name] = str(out / f"extend{d:g}.ttf")
        set_band(a.base, fonts[name], -d * CAP, CAP)
    for band in (v for v in a.bands.split(",") if v):
        lo, hi = (float(x) for x in band.split(":"))
        name = f"band {lo:g} to {hi:g} x cap"
        fonts[name] = str(out / f"band{lo:g}_{hi:g}.ttf")
        set_band(a.base, fonts[name], lo * CAP, hi * CAP)
    from maxocr.engines.easyocr_rec import EasyOCRRec
    paddle, easy = rung0.PaddleRec(alphabet=ALNUM_ALPHABET), EasyOCRRec(alphabet=ALNUM_ALPHABET)
    lines = bank(DIGITS + LOOKALIKES, seed=1010)
    jobs = [Job(p, p, rung0.SEVERITY, "a", c) for p in fonts.values() for c in chunk(lines, 40)]
    ch, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_whitelist=ALNUM_ALPHABET)
    rows = []
    for name, p in fonts.items():
        g = ch[ch.font == p]
        acc = {c: float(np.mean([(g[(g.engine == e) & (g.truth == c)].pred == c).mean() for e in ENGINES]))
               for c in DIGITS + LOOKALIKES}
        rows.append({"variant": name, "char_err": round(100 * float((g.pred != g.truth).mean()), 2),
                     "digits_acc": round(100 * np.mean([acc[c] for c in DIGITS]), 1),
                     "lookalikes_acc": round(100 * np.mean([acc[c] for c in LOOKALIKES]), 1),
                     **{f"{c}": round(100 * acc[c], 1) for c in DIGITS}, "font": p})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / a.out, index=False)
    with pd.option_context("display.width", 220):
        print(df.drop(columns="font").to_string(index=False))


if __name__ == "__main__":
    main()
