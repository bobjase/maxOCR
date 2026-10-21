"""TrOCR (microsoft/trocr-base-printed) on the README benchmark (2026-10-21): every font, kind of text and condition
(the nine README conditions plus thermal, letter-quality dot-matrix and phone photo), 300 lines each. TrOCR's printed
model writes only capitals (it was fine-tuned on receipts), so its readings are scored ignoring case.

    python scripts/trocr_bench.py [--n 300] [--fonts ...]   -> out/report/trocr_bench.csv (resumable)
"""
import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from readme_bench import CONDITIONS, FONTS, image, texts  # noqa: E402
from text_eval import char_err  # noqa: E402

CONDS = list(CONDITIONS) + ["thermal", "dot-matrix lq", "phone photo"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--fonts")
    ap.add_argument("--out", default="out/report/trocr_bench.csv")
    a = ap.parse_args()
    from maxocr.engines.trocr import TrOCR
    from maxocr.fonts import matched_size
    m = TrOCR()
    sets = texts(a.n)
    rows = pd.read_csv(a.out).to_dict("records") if os.path.exists(a.out) else []
    done = {(r["font"], r["text"], r["condition"]) for r in rows}
    fonts = {k: v for k, v in FONTS.items() if not a.fonts or k in a.fonts.split(",")}
    for name, path in fonts.items():
        size = matched_size(path, 8.0)
        for cond in CONDS:
            for kind, lines in sets.items():
                if (name, kind, cond) in done:
                    continue
                reads = m.read([image(path, t, size, cond, k) for k, t in enumerate(lines)])
                err = round(char_err([t.upper() for t in lines], [r.upper() for r in reads]), 2)
                rows.append({"font": name, "text": kind, "condition": cond, "trocr": err})
                print(json.dumps(rows[-1]), flush=True)
                pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
