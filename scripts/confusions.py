"""Rank confusable character pairs for one font: validation bank (5,000 lines), s=0.5, suite (a),
uncropped, all four engines reading the general alphabet with case folded (Tesseract keeps its
whitelist). For each unordered pair {a, b}: (a read as b + b read as a) / (occurrences of a and b).
Picks the next pairs for discovery.

    python scripts/confusions.py FONT.ttf [--name NAME] [--top 15]
Writes out/report/confusions_<name>.csv.
"""
import argparse
import sys
from collections import Counter
from multiprocessing import get_context
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from discover_validate import _imgs  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.engines.easyocr_rec import EasyOCRRec  # noqa: E402
from maxocr.engines.parseq import Parseq  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font")
    ap.add_argument("--name", default="font")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=True)
    val = rung0.bank("val")
    jobs = [Job(a.name, a.font, rung0.SEVERITY, "a", c) for c in chunk(val, 50)]
    chars, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=rung0.PaddleRec(**eng), progress=False, easy=EasyOCRRec(**eng))
    chars = chars[~chars.cropped][["engine", "truth", "pred"]]
    model = Parseq(**eng)
    with get_context("spawn").Pool(16) as pool:
        imgs = [im for part in pool.map(_imgs, [(a.font, val[i:i + 250]) for i in range(0, len(val), 250)]) for im in part]
    recs = []
    for inst, pred in zip(val, model.read(imgs)):
        if inst.cropped:
            continue
        _, mapping, _ = align(inst.text, pred)
        recs += [{"engine": "parseq", "truth": inst.text[i], "pred": pred[j] if j is not None else ""}
                 for i, j in enumerate(mapping)]
    chars = pd.concat([chars, pd.DataFrame(recs)], ignore_index=True)

    rows = []
    for e, g in chars.groupby("engine"):
        n = Counter(g.truth)
        sub = Counter(zip(g.truth, g.pred))
        pairs = {tuple(sorted((t, p))) for (t, p) in sub if t != p and p in n}
        for x, y in pairs:
            k = sub[(x, y)] + sub[(y, x)]
            rows.append({"engine": e, "pair": x + y, "rate_pct": 100 * k / (n[x] + n[y]),
                         "a_as_b": sub[(x, y)], "b_as_a": sub[(y, x)]})
    df = pd.DataFrame(rows)
    wide = df.pivot_table(index="pair", columns="engine", values="rate_pct", fill_value=0.0)
    wide["mean"] = wide.mean(1)
    wide = wide.sort_values("mean", ascending=False)
    wide.round(2).to_csv(ROOT / "out" / "report" / f"confusions_{a.name}.csv")
    with pd.option_context("display.width", 200):
        print(wide.head(a.top).round(2).to_string())


if __name__ == "__main__":
    main()
