"""Confirmation of the Windows font survey on a fresh 1,000-line bank (seed 707), equal capital
height, baselines included. 0/O pair confusion with Wilson 95% intervals, per engine and condition.

    python scripts/survey_confirm_report.py
Writes out/report/survey_confirm.csv.
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from maxocr.analysis import within_cluster_rate

ROOT = Path(__file__).resolve().parents[1]
CONF = ROOT / "out" / "survey_confirm"
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
    chars = pd.concat(pd.read_parquet(p) for p in sorted(glob.glob(str(CONF / "batch_*_chars.parquet"))))
    chars = chars[(chars.suite == "a") & ~chars.cropped]
    objective = json.loads((OUT / "clusters.json").read_text())["objective"]
    rows = []
    for (face, engine, sev), g in chars.groupby(["face", "engine", "severity"]):
        z, o = g[g.truth == "0"], g[g.truth == "O"]
        # Pair confusion pooled over both directions: (0->O + O->0) / (n_0 + n_O).
        k = int((z.pred == "O").sum() + (o.pred == "0").sum())
        n = len(z) + len(o)
        lo, hi = wilson(k, n)
        rows.append({"face": face, "engine": engine, "condition": "clean" if sev < 0 else f"s={sev:g}",
                     "pair_pct": 100 * k / n, "ci_lo": 100 * lo, "ci_hi": 100 * hi, "n": n,
                     "within_cluster_pct": 100 * within_cluster_rate(g, objective),
                     "char_error_pct": 100 * (g.pred != g.truth).mean()})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "survey_confirm.csv", index=False)
    for engine in ("paddle", "tesseract"):
        for cond in ("clean", "s=0.5"):
            d = df[(df.engine == engine) & (df.condition == cond)].sort_values("pair_pct")
            print(f"\n{engine}, {cond}: 0/O pair confusion % [95% CI], within-cluster %, char error %")
            for r in d.itertuples():
                print(f"  {r.face:32} {r.pair_pct:5.1f} [{r.ci_lo:4.1f}-{r.ci_hi:4.1f}]  "
                      f"wc {r.within_cluster_pct:5.1f}  err {r.char_error_pct:5.1f}")


if __name__ == "__main__":
    main()
