"""Merge/split check: does VV read as W, or W as VV? Random 6-character codes with VV or W inserted,
s=0.5, suite (a), equal capital height; PaddleOCR, EasyOCR, PARSeq (general alphabet, case folded) and
Tesseract (whole-line text, whitelist 0-9A-Za-z). A read counts as a merge if it equals the code with
VV replaced by W, as a split if it equals the code with W replaced by VV.

    python scripts/merge_split_eval.py --fonts-json f.json [--n 300]
Writes out/report/merge_split.csv.
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


def bank(n: int, seed: int = 4747):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(2 * n):
        s = list(rng.choice(list(FILL), 5))
        tgt = "VV" if k < n else "W"
        pos = int(rng.integers(0, 6))
        out.append("".join(s[:pos]) + tgt + "".join(s[pos:]))
    return [make_instance(i, t, seed) for i, t in enumerate(out)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    os.environ["MAXOCR_CALT"] = "1"
    from PIL import Image
    from tesserocr import OEM, PSM, PyTessBaseAPI
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.paddle import PaddleRec
    from maxocr.engines.parseq import Parseq
    from maxocr.engines.tesseract import TESSDATA_BEST
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=True)
    paddle, easy, pq = PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    api = PyTessBaseAPI(path=str(TESSDATA_BEST) + "/", lang="eng", oem=OEM.LSTM_ONLY, psm=PSM.SINGLE_LINE,
                        variables={"load_system_dawg": "0", "load_freq_dawg": "0"})
    api.SetVariable("tessedit_char_whitelist", "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")

    def tess(im):
        api.SetImage(Image.fromarray(im))
        return "".join(api.GetUTF8Text().split()).upper()

    fonts = json.loads(Path(a.fonts_json).read_text())
    insts = [i for i in bank(a.n) if not i.cropped]
    rows = []
    for name, path in fonts.items():
        sz = matched_size(path, 8.0)
        imgs = [degrade(path, i, rung0.SEVERITY, sz) for i in insts]
        reads = {"paddle": [paddle.text(im) for im in imgs], "easyocr": easy.texts(imgs), "parseq": pq.read(imgs),
                 "tesseract": [tess(im) for im in imgs]}
        row = {"font": name}
        for e, preds in reads.items():
            vv = [(i, p) for i, p in zip(insts, preds) if "VV" in i.text]
            w = [(i, p) for i, p in zip(insts, preds) if "W" in i.text]
            row[f"{e}_VV_as_W"] = round(100 * np.mean([p == i.text.replace("VV", "W") for i, p in vv]), 1)
            row[f"{e}_W_as_VV"] = round(100 * np.mean([p == i.text.replace("W", "VV") for i, p in w]), 1)
            row[f"{e}_exact"] = round(100 * np.mean([p == i.text for i, p in zip(insts, preds)]), 1)
        rows.append(row)
        print(json.dumps(row), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / "merge_split.csv", index=False)


if __name__ == "__main__":
    main()
