"""Hebrew benchmark (2026-10-17): Hebrew lines (scripts/hebrew_text.py) in every print condition of the README
benchmark, read by Tesseract's Hebrew model (tessdata_best heb; the other three engines here read Latin only).
Same capital height for every font (measured on H, as in the README benchmark).

    python scripts/hebrew_bench.py --fonts '{"name": "path", ...}' --out out/report/hebrew_bench.csv [--n 300]
Resumable: cells already in --out are skipped.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from hebrew_text import lines as hebrew_lines  # noqa: E402
from readme_bench import CONDITIONS, image  # noqa: E402
from text_eval import char_err, read_tesseract_dict  # noqa: E402

WIN = "/mnt/c/Windows/Fonts/"
FONTS = {
    "Arial": WIN + "arial.ttf", "Times New Roman": WIN + "times.ttf", "Courier New": WIN + "cour.ttf",
    "Segoe UI": WIN + "segoeui.ttf", "Calibri": WIN + "calibri.ttf", "Tahoma": WIN + "tahoma.ttf",
    "Microsoft Sans Serif": WIN + "micross.ttf", "Lucida Sans Unicode": WIN + "l_10646.ttf", "Miriam": WIN + "mriam.ttf",
    "Arimo": "vendor/ofl/arimo/Arimo[wght].ttf", "Tinos": "vendor/ofl/tinos/Tinos-Regular.ttf",
    "Cousine": "vendor/ofl/cousine/Cousine-Regular.ttf", "Frank Ruhl Libre": "vendor/ofl/frankruhllibre/FrankRuhlLibre[wght].ttf",
    "Open Sans": "vendor/ofl/opensans/OpenSans[wdth,wght].ttf", "Cardo": "vendor/ofl/cardo/Cardo-Regular.ttf",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", help="JSON {name: path}; default: the comparison fonts")
    ap.add_argument("--out", default="out/report/hebrew_bench.csv")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--conds", default=",".join(CONDITIONS))
    a = ap.parse_args()
    from maxocr.fonts import matched_size
    fonts = json.loads(a.fonts) if a.fonts else FONTS
    ls = hebrew_lines(a.n)
    rows = pd.read_csv(a.out).to_dict("records") if os.path.exists(a.out) else []
    done = {(r["font"], r["condition"]) for r in rows}
    for name, path in fonts.items():
        path = os.path.expanduser(path)
        try:
            size = matched_size(path, 8.0)
        except Exception:
            size = 8.0
        for cond in a.conds.split(","):
            if (name, cond) in done:
                continue
            imgs = [image(path, t, size, cond, k) for k, t in enumerate(ls)]
            reads = read_tesseract_dict(imgs, fold=False, lang="heb")
            row = {"font": name, "condition": cond, "tesseract": round(char_err(ls, reads), 2)}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
