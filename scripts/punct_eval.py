"""Punctuation inside given fonts (MaxOCR candidates, references): the punctuation survey's bank (400 random lines over
0-9A-Za-z + punctuation, marks x6, s=0.5, suite (a)) at equal capital height (maxocr.fonts.matched_size, 8 pt);
PaddleOCR and EasyOCR on the general alphabet, Tesseract with that whitelist, case-sensitive. Per font: share of
marks read right, letter/digit error, overall error; per mark: correct-read rate and top misreadings.

    python scripts/punct_eval.py --fonts-json f.json [--out punct_eval.csv]
Writes out/report/<out> (per font) and <out>_marks.csv (per font x mark).
"""
import argparse
import json
import string
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402
from punct_survey import bank  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PUNCT = string.punctuation
ENGINES = ("paddle", "tesseract", "easyocr")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--out", default="punct_eval.csv")
    a = ap.parse_args()
    fonts = json.loads(Path(a.fonts_json).read_text())
    from maxocr.engines.easyocr_rec import EasyOCRRec
    paddle = rung0.PaddleRec(alphabet=GENERAL_ALPHABET, casefold=False)
    easy = EasyOCRRec(alphabet=GENERAL_ALPHABET, casefold=False)
    b = bank()
    jobs = [Job(p, p, rung0.SEVERITY, "a", c, size_pt=matched_size(p, 8.0)) for p in fonts.values() for c in chunk(b, 50)]
    ch, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_whitelist=GENERAL_ALPHABET)
    rows, marks = [], []
    for name, p in fonts.items():
        g = ch[ch.font == p]
        acc = {}
        for c in PUNCT:
            h = g[g.truth == c]
            acc[c] = float(np.mean([(h[h.engine == e].pred == c).mean() for e in ENGINES]))
            miss = h[h.pred != c].pred.value_counts()
            marks.append({"font": name, "mark": c, "acc": round(100 * acc[c], 1),
                          "read_as": " ".join(f"{k}:{v}" for k, v in miss.head(3).items())})
        an = g[~g.truth.isin(list(PUNCT))]
        rows.append({"font": name, "punct_acc": round(100 * float(np.mean(list(acc.values()))), 1),
                     "alnum_err": round(100 * float((an.pred != an.truth).mean()), 2),
                     "char_err": round(100 * float((g.pred != g.truth).mean()), 2)})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / a.out, index=False)
    m = pd.DataFrame(marks)
    m.to_csv(ROOT / "out" / "report" / a.out.replace(".csv", "_marks.csv"), index=False)
    with pd.option_context("display.width", 250):
        print(df.to_string(index=False))
        print(m.pivot(index="font", columns="mark", values="acc").round(0).to_string())


if __name__ == "__main__":
    main()
