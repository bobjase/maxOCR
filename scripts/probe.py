"""R40b: probe-classifier error per cluster for one font at one severity.

    python scripts/probe.py --font "Source Code Pro" --severity 0.5
    python scripts/probe.py --font "Source Code Pro" --clean
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from maxocr.corpus import PRIMARY_ALPHABET
from maxocr.fonts import BASELINES
from maxocr.probe import best_of_seeds, make_dataset

CLUSTERS = [["1", "6", "G", "I", "L"], ["0", "D", "O"], ["2", "Z"], ["5", "S"], ["8", "B"]]
OUT = Path(__file__).resolve().parents[1] / "out" / "probe"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default="Source Code Pro")
    ap.add_argument("--severity", type=float, default=0.5)
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--n-train", type=int, default=54_000)
    ap.add_argument("--n-test", type=int, default=10_800)
    a = ap.parse_args()
    sev = None if a.clean else a.severity
    # Accept names with or without spaces (spaces get lost passing through wsl/bash -lc).
    a.font = {k.replace(" ", ""): k for k in BASELINES}.get(a.font.replace(" ", ""), a.font)
    font = str(BASELINES[a.font])

    t = time.perf_counter()
    xtr, ytr = make_dataset(font, sev, a.n_train, seed=303)
    xte, yte = make_dataset(font, sev, a.n_test, seed=404)
    t_data = time.perf_counter() - t
    pred, seed_runs = best_of_seeds(xtr, ytr, xte, yte)
    t_all = time.perf_counter() - t

    A = PRIMARY_ALPHABET
    err = float((pred != yte).mean())
    member = {A.index(c): k for k, g in enumerate(CLUSTERS) for c in g}
    per_cluster = {}
    for k, g in enumerate(CLUSTERS):
        m = np.isin(yte, [A.index(c) for c in g])
        within = (pred[m] != yte[m]) & np.array([member.get(p, -1) == k for p in pred[m]])
        per_cluster["".join(g)] = round(100 * float(within.mean()), 3)
    zo = {f"{A[t]}->{A[p]}": int(((yte == A.index(A[t])) & (pred == p)).sum())
          for t in (A.index("0"), A.index("O")) for p in (A.index("0"), A.index("O"))}
    within_all = np.isin(yte, list(member)) & (pred != yte) & np.array(
        [member.get(p, -1) == member.get(t, -2) for p, t in zip(pred, yte)])
    agg = 100 * within_all.sum() / np.isin(yte, list(member)).sum()

    tag = f"{a.font.replace(' ', '')}_{'clean' if a.clean else f'sev_{a.severity:.2f}'}"
    result = {"font": a.font, "condition": "clean" if a.clean else a.severity, "test_error_pct": round(100 * err, 3),
              "within_cluster_pct": round(float(agg), 3), "per_cluster_within_pct": per_cluster,
              "zero_O_counts": zo, "seed_runs": seed_runs, "n_train": a.n_train, "n_test": a.n_test,
              "seconds": {"data": round(t_data, 1), "total": round(t_all, 1)}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{tag}.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
