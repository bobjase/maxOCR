"""Merge/split check: is a pair of letters read as one letter (VV as W, rn as m, ...) or the reverse?
Random 6-character codes with the pair or the merged letter inserted, s=0.5, suite (a), equal capital height;
PaddleOCR, EasyOCR, PARSeq (general alphabet) and Tesseract (whole-line text, whitelist 0-9A-Za-z). A read counts
as a merge if it equals the code with the pair replaced by the merged letter, as a split if the reverse.

Capitals (default, --pairs VV:W): fillers 0-9 and capitals without U V W I O Q, case folded (as on 2026-10-11).
Lowercase (--lower): fillers lowercase and digits without any letter of the pairs or its look-alikes, read
case-sensitively.

    python scripts/merge_split_eval.py --fonts-json f.json [--n 300] [--lower --pairs vv:w,rn:m,cl:d]
Writes out/report/merge_split.csv (or --out).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.degrade import degrade, make_instance  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FILL = "0123456789ABCDEFGHJKLMNPRSTXYZ"   # no V, W, U, I, O, Q: keep the target unambiguous
FILL_LOWER = "abefghjkpqstxyz2345678"      # no v w r n m c l d i u o and no 0 1 9 (look-alikes of the pairs)


def bank(n: int, pairs: list[tuple[str, str]], fill: str, seed: int = 4747):
    rng = np.random.default_rng(seed)
    out = []
    for split, merged in pairs:
        for k in range(2 * n):
            s = list(rng.choice(list(fill), 5))
            tgt = split if k < n else merged
            pos = int(rng.integers(0, 6))
            out.append("".join(s[:pos]) + tgt + "".join(s[pos:]))
    return [make_instance(i, t, seed) for i, t in enumerate(out)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--pairs", default="VV:W", help="split:merged,... e.g. vv:w,rn:m,cl:d")
    ap.add_argument("--lower", action="store_true", help="lowercase pairs: lowercase fillers, case-sensitive reading")
    ap.add_argument("--out", default="merge_split.csv")
    a = ap.parse_args()
    pairs = [tuple(p.split(":")) for p in a.pairs.split(",")]
    os.environ["MAXOCR_CALT"] = "1"
    from PIL import Image
    from tesserocr import OEM, PSM, PyTessBaseAPI
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.paddle import PaddleRec
    from maxocr.engines.parseq import Parseq
    from maxocr.engines.tesseract import TESSDATA_BEST
    fold = not a.lower
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=fold)
    paddle, easy, pq = PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    api = PyTessBaseAPI(path=str(TESSDATA_BEST) + "/", lang="eng", oem=OEM.LSTM_ONLY, psm=PSM.SINGLE_LINE,
                        variables={"load_system_dawg": "0", "load_freq_dawg": "0"})
    api.SetVariable("tessedit_char_whitelist", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")

    def tess(im):
        api.SetImage(Image.fromarray(im))
        t = "".join(api.GetUTF8Text().split())
        return t.upper() if fold else t

    fonts = json.loads(Path(a.fonts_json).read_text())
    insts = [i for i in bank(a.n, pairs, FILL_LOWER if a.lower else FILL) if not i.cropped]
    rows = []
    for name, path in fonts.items():
        sz = matched_size(path, 8.0)
        imgs = [degrade(path, i, rung0.SEVERITY, sz) for i in insts]
        reads = {"paddle": [paddle.text(im) for im in imgs], "easyocr": easy.texts(imgs), "parseq": pq.read(imgs),
                 "tesseract": [tess(im) for im in imgs]}
        for split, merged in pairs:
            row = {"font": name, "pair": f"{split}/{merged}"}
            for e, preds in reads.items():
                sp = [(i, p) for i, p in zip(insts, preds) if split in i.text]
                mg = [(i, p) for i, p in zip(insts, preds) if merged in i.text and split not in i.text]
                row[f"{e}_merge"] = round(100 * np.mean([p == i.text.replace(split, merged) for i, p in sp]), 1)
                row[f"{e}_split"] = round(100 * np.mean([p == i.text.replace(merged, split) for i, p in mg]), 1)
                row[f"{e}_exact"] = round(100 * np.mean([p == i.text for i, p in sp + mg]), 1)
            row["merge_mean"] = round(float(np.mean([row[f"{e}_merge"] for e in reads])), 2)
            row["split_mean"] = round(float(np.mean([row[f"{e}_split"] for e in reads])), 2)
            row["exact_mean"] = round(float(np.mean([row[f"{e}_exact"] for e in reads])), 1)
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("font", "pair", "merge_mean", "split_mean", "exact_mean")}), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / a.out, index=False)
    with pd.option_context("display.width", 200):
        print(df.pivot_table(index="font", columns="pair", values="merge_mean").round(1).to_string())


if __name__ == "__main__":
    main()
