"""M1a analysis on the frozen validation bank at the operating point.

    python scripts/m1a_validation.py [--severity 0.5]

Writes to out/report/:
  clusters.json            R22/R22a objective (PaddleOCR) and gate (Tesseract) clusters, stability
  cluster_union.csv        R22a published union table
  best_baseline.json       Section 7 step 2: best baseline at the locked severity
  baseline_table.csv       within-cluster and all-character rates per font/engine/suite/stratum (R25, R20, R10b)
  reliability.csv/.png     R27b per-glyph realized within-cluster error vs median PaddleOCR margin
  hinge.json               R27b hinge for candidate per-cluster targets (targets are an open question)
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.optimize import isotonic_regression  # noqa: E402

from maxocr.analysis import (cluster_report, dumps, paddle_margin, significant_edges,  # noqa: E402
                             substitution_counts, union_table, within_cluster_rate, MIN_RATE, MIN_SHARE)
from maxocr.fonts import BASELINES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "out" / "validation"
OUT = ROOT / "out" / "report"
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
MARKERS = ["o", "s", "^", "D", "v", "P"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3dd", "#fcfcfb"


def strata(c: pd.DataFrame):
    yield "all_uncropped", c[~c.cropped]
    yield "len1_uncropped", c[~c.cropped & (c.length == 1)]
    yield "len8plus_uncropped", c[~c.cropped & (c.length >= 8)]
    yield "cropped", c[c.cropped]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--severity", type=float, default=0.5)
    a = ap.parse_args()
    chars = pd.read_parquet(VAL / f"sev_{a.severity:.2f}_chars.parquet")
    classes = json.loads((VAL / "classes.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)

    # R22/R22a: objective clusters from PaddleOCR, gate clusters from Tesseract, suite (a), uncropped.
    rep = {e: cluster_report(chars, e, "a") for e in ("paddle", "tesseract")}
    objective, gate = rep["paddle"]["clusters"], rep["tesseract"]["clusters"]
    (OUT / "clusters.json").write_text(dumps({"severity": a.severity, "min_share": MIN_SHARE, "min_rate": MIN_RATE,
                                              "objective": objective, "gate": gate, "reports": rep}))
    edges = {e: significant_edges(substitution_counts(chars[(chars.engine == e) & (chars.suite == "a") & ~chars.cropped]),
                                  min_share=MIN_SHARE, min_rate=MIN_RATE) for e in rep}
    union_table(edges["paddle"], edges["tesseract"]).to_csv(OUT / "cluster_union.csv", index=False)

    # Baseline table: within-cluster rate (R25 denominator: cluster-member occurrences) per stratum.
    rows = []
    for (engine, suite, font), g in chars.groupby(["engine", "suite", "font"]):
        clusters = objective if engine == "paddle" else gate
        for name, s in strata(g):
            rows.append({"engine": engine, "suite": suite, "font": font, "stratum": name, "n_chars": len(s),
                         "within_objective_pct": 100 * within_cluster_rate(s, objective),
                         "within_own_clusters_pct": 100 * within_cluster_rate(s, clusters),
                         "all_char_error_pct": 100 * float((s.pred != s.truth).mean())})
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "baseline_table.csv", index=False)

    # PRD Section 7 step 2, second half: best baseline chosen AT the locked severity. Aggregate =
    # mean of PaddleOCR (objective clusters) and Tesseract (gate clusters), suite (a), uncropped.
    main_rows = table[(table.suite == "a") & (table.stratum == "all_uncropped")]
    agg = main_rows.groupby("font").within_own_clusters_pct.mean().sort_values()
    best = {"severity": a.severity, "best_baseline": agg.index[0],
            "ranking": [(f, round(v, 3)) for f, v in agg.items()],
            "margin_to_second_pct": round(float(agg.iloc[1] - agg.iloc[0]), 3)}
    (OUT / "best_baseline.json").write_text(json.dumps(best, indent=1))

    # R27b reliability. Per instance the curve is degenerate: the margin is read at the frame of the
    # decoded run, so margin < 0 <=> error by construction. The informative version is per glyph:
    # median margin of a (font, character) over the bank vs that glyph's realized within-cluster error.
    p = chars[(chars.engine == "paddle") & (chars.suite == "a") & ~chars.cropped].copy()
    member = {c: i for i, g in enumerate(objective) for c in g}
    p = p[p.truth.isin(member)]
    p["margin"] = paddle_margin(p, classes, objective)
    p["within_err"] = (p.pred != p.truth) & (p.pred.map(member) == p.truth.map(member))
    p = p.dropna(subset=["margin"])
    rel = p.groupby(["font", "truth"]).agg(median_margin=("margin", "median"), error=("within_err", "mean"),
                                           n=("within_err", "size")).reset_index().sort_values("median_margin")
    fit = isotonic_regression(rel.error.to_numpy(), weights=rel.n.to_numpy(), increasing=False).x
    rel["fitted_error"] = fit
    rel.to_csv(OUT / "reliability.csv", index=False)
    hinges = {}
    for target in (0.005, 0.01, 0.02):
        below = rel[rel.fitted_error < target]
        hinges[f"{100 * target:g}%"] = None if below.empty else round(1.5 * float(below.median_margin.iloc[0]), 3)

    fig, ax = plt.subplots(figsize=(7.5, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    floor = 0.01  # percent; zero-error glyphs are drawn at the floor of the log axis
    for i, font in enumerate(BASELINES):
        d = rel[rel.font == font]
        ax.scatter(d.median_margin, np.maximum(100 * d.error, floor), color=COLORS[i], marker=MARKERS[i], s=30,
                   edgecolors=SURFACE, linewidths=1, label=font, zorder=3)
    ax.plot(rel.median_margin, np.maximum(100 * rel.fitted_error, floor), color=INK2, lw=1.5, zorder=2,
            label="isotonic fit (all fonts)")
    ax.set_yscale("log")
    ax.set_xlabel("median PaddleOCR log-odds margin of the glyph (truth vs strongest in-cluster rival)", color=INK2)
    ax.set_ylabel("realized within-cluster error % (log)", color=INK2)
    ax.set_title(f"R27b reliability per glyph, validation bank, s={a.severity}, suite (a)", color=INK,
                 fontsize=11, loc="left")
    ax.grid(color=GRID, lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "reliability.png", dpi=130, facecolor=SURFACE)
    (OUT / "hinge.json").write_text(json.dumps({"rule": "1.5 x smallest median margin whose fitted error < target",
                                               "hinge_by_target": hinges}, indent=1))

    print("best baseline at operating point:", best)
    print("R27b hinge by candidate target:", hinges)
    print("objective clusters:", objective)
    print("gate clusters:     ", gate)
    for e in rep:
        print(f"stability {e}:", rep[e]["stability"])
    t = table[(table.suite == "a")].pivot_table(index=["engine", "font"], columns="stratum",
                                                values="within_own_clusters_pct").round(2)
    print("\nwithin-cluster % (suite a; paddle uses objective clusters, tesseract gate clusters):")
    print(t.to_string())


if __name__ == "__main__":
    main()
