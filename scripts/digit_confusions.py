"""Which digits the engines confuse in MaxOCR (James, 2026-10-21: "What are the most common scan errors? 8->0? 6<->9?
... add disambiguation indicators"): numbers and codes in every condition, four engines, aligned character by
character; counts of truth digit -> read character (substitutions only) and of digits dropped.

    python scripts/digit_confusions.py [--font MaxOCR] [--n 300]   -> out/report/digit_confusions.csv
"""
import argparse
import os
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import readme_bench as rb  # noqa: E402
from text_eval import read_tesseract_dict  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from maxocr.align import align  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default="MaxOCR")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--all", action="store_true", help="every letter and digit, in paragraphs too (-> char_confusions.csv)")
    a = ap.parse_args()
    import rung0
    from maxocr.corpus import GENERAL_ALPHABET
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    from maxocr.fonts import matched_size
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**{**eng, "alphabet": GENERAL_ALPHABET + " "}), Parseq(**eng)
    P = rb.FONTS[a.font]; size = matched_size(P, 8.0); sets = rb.texts(a.n)
    conds = list(rb.CONDITIONS) + ["thermal", "dot-matrix lq", "phone photo"]
    subs, drops, seen = Counter(), Counter(), Counter()
    for kind in (("numbers", "codes", "paragraphs") if a.all else ("numbers", "codes")):
        lines = sets[kind]
        for cond in conds:
            imgs = [rb.image(P, t, size, cond, k) for k, t in enumerate(lines)]
            preds = [[paddle.text(im) for im in imgs], rb.in_batches(easy.texts, imgs), rb.read_by_words(pq, imgs),
                     read_tesseract_dict(imgs, fold=False)]
            for ps in preds:
                for t, p in zip(lines, ps):
                    t, p = t.replace(" ", ""), p.replace(" ", "")
                    _, m, _ = align(t, p)
                    for i, j in enumerate(m):
                        if not (t[i].isalnum() if a.all else t[i].isdigit()):
                            continue
                        seen[t[i]] += 1
                        if j is None:
                            drops[t[i]] += 1
                        elif p[j] != t[i]:
                            subs[(t[i], p[j])] += 1
            print(kind, cond, sum(subs.values()), flush=True)
    rows = [{"truth": t, "read": r, "count": c} for (t, r), c in subs.most_common()]
    rows += [{"truth": t, "read": "(dropped)", "count": c} for t, c in drops.most_common()]
    pd.DataFrame(rows).to_csv("out/report/char_confusions.csv" if a.all else "out/report/digit_confusions.csv", index=False)
    print("digits read:", sum(seen.values()))


if __name__ == "__main__":
    main()
