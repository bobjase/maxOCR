"""Character error that counts spaces: codes contain no spaces, so a space the engine inserts (letter-digit
gaps read as word breaks) is an error. Levenshtein distance between the code and the upper-cased reading
(spaces kept), over the code's length. PaddleOCR, EasyOCR and Tesseract read the general alphabet plus
space (case folded); PARSeq has no space and is left out. Uncropped validation lines, s=0.5, suite (a),
contextual features on.

    python scripts/space_aware_eval.py --fonts-json f.json [--lines 1000] [--sizes 8,12] [--dpi 200]
Writes out/report/space_aware.csv.
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
from maxocr.degrade import degrade  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--lines", type=int, default=1000)
    ap.add_argument("--sizes", default="8,12")
    ap.add_argument("--dpi", type=int, default=200)
    a = ap.parse_args()
    os.environ["MAXOCR_CALT"] = "1"
    import easyocr
    from maxocr.engines.paddle import PaddleRec
    from PIL import Image
    from tesserocr import OEM, PSM, PyTessBaseAPI
    from maxocr.engines.tesseract import TESSDATA_BEST
    fonts = json.loads(Path(a.fonts_json).read_text())
    val = [i for i in rung0.bank("val") if not i.cropped][:a.lines]
    alpha = GENERAL_ALPHABET + " "
    paddle = PaddleRec(alphabet=alpha, casefold=True)
    reader = easyocr.Reader(["en"], gpu=True, detector=False, recognizer=True, verbose=False)
    # Whole-line text (GetUTF8Text) keeps Tesseract's word spaces; symbol iteration would drop them.
    api = PyTessBaseAPI(path=str(TESSDATA_BEST) + "/", lang="eng", oem=OEM.LSTM_ONLY, psm=PSM.SINGLE_LINE,
                        variables={"load_system_dawg": "0", "load_freq_dawg": "0"})
    api.SetVariable("tessedit_char_whitelist", alpha)

    def tess_text(im):
        api.SetImage(Image.fromarray(im))
        return api.GetUTF8Text()
    rows = []
    for size in [float(x) for x in a.sizes.split(",")]:
        for name, path in fonts.items():
            sz = matched_size(path, size)
            imgs = [degrade(path, i, rung0.SEVERITY, sz, a.dpi) for i in val]
            reads = {"paddle": [paddle.text(im).strip() for im in imgs],
                     "easyocr": [" ".join(reader.recognize(im, horizontal_list=[[0, im.shape[1], 0, im.shape[0]]],
                                                           free_list=[], detail=0, allowlist=alpha, decoder="greedy",
                                                           paragraph=False)).strip().upper() for im in imgs],
                     "tesseract": [tess_text(im).strip().upper() for im in imgs]}
            row = {"font": name, "size_pt": size, "dpi": a.dpi}
            n = sum(len(i.text) for i in val)
            for e, preds in reads.items():
                row[e] = round(100 * sum(lev(i.text, p) for i, p in zip(val, preds)) / n, 2)
                row[f"{e}_space_lines"] = round(100 * float(np.mean([" " in p for p in preds])), 1)
            row["mean"] = round((row["paddle"] + row["easyocr"] + row["tesseract"]) / 3, 2)
            rows.append(row)
            print(json.dumps(row), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / "space_aware.csv", index=False)
    with pd.option_context("display.width", 220):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
