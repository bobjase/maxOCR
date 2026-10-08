"""Confirmation of the Windows font survey on a fresh 1,000-line bank, equal capital height,
baselines included. Pair confusion (pooled over both directions) with Wilson 95% intervals, per
engine and condition.

    python scripts/survey_confirm_report.py                                   # 0/O, seed-707 run
    python scripts/survey_confirm_report.py --dir out/survey_confirm_pairs --pairs 5/S 1/I 8/B
Writes out/report/<dir name>.csv and prints, per pair, engine and condition, the best three faces
next to the best and worst baseline.
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from maxocr.analysis import within_cluster_rate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "report"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "out" / "survey_confirm")
    ap.add_argument("--pairs", nargs="+", default=["0/O"])
    a = ap.parse_args()
    chars = pd.concat(pd.read_parquet(p) for p in sorted(glob.glob(str(a.dir / "batch_*_chars.parquet"))))
    chars = chars[(chars.suite == "a") & ~chars.cropped]
    objective = json.loads((OUT / "clusters.json").read_text())["objective"]

    rows = []
    for (face, engine, sev), g in chars.groupby(["face", "engine", "severity"]):
        for pair in a.pairs:
            x, y = pair.split("/")
            gx, gy = g[g.truth == x], g[g.truth == y]
            k = int((gx.pred == y).sum() + (gy.pred == x).sum())
            n = len(gx) + len(gy)
            lo, hi = wilson(k, n)
            rows.append({"pair": pair, "face": face, "engine": engine,
                         "condition": "clean" if sev < 0 else f"s={sev:g}",
                         "pair_pct": 100 * k / n, "ci_lo": 100 * lo, "ci_hi": 100 * hi, "n": n,
                         "within_cluster_pct": 100 * within_cluster_rate(g, objective),
                         "char_error_pct": 100 * (g.pred != g.truth).mean()})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"{a.dir.name}.csv", index=False)

    def fmt(r):
        return f"{r.face.replace('[baseline] ', '')[:24]} {r.pair_pct:.1f} [{r.ci_lo:.1f}-{r.ci_hi:.1f}]"

    for (pair, engine, cond), d in df.groupby(["pair", "engine", "condition"]):
        d = d.sort_values("pair_pct")
        base = d[d.face.str.startswith("[baseline]")]
        fonts = d[~d.face.str.startswith("[baseline]")]
        print(f"{pair:4} {engine:9} {cond:6} | best: " + "; ".join(fmt(r) for r in fonts.head(3).itertuples())
              + f" | best baseline: {fmt(next(base.itertuples()))} | worst baseline: {fmt(list(base.itertuples())[-1])}")


if __name__ == "__main__":
    main()
