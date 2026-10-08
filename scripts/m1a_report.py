"""M1a plot 1: within-cluster substitution vs severity, per baseline font, per engine (suite a).

Clusters are the final objective clusters from out/report/clusters.json (validation bank at the
operating point; run scripts/m1a_validation.py first).
Writes out/report/plot1_severity.png and plot1_severity.csv.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import json  # noqa: E402

from maxocr.analysis import within_cluster_rate  # noqa: E402
from maxocr.fonts import BASELINES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "out" / "sweep"
OUT = ROOT / "out" / "report"

# Validated categorical palette (light), fixed order by font; markers are secondary encoding.
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
MARKERS = ["o", "s", "^", "D", "v", "P"]
# Above ~1.0 errors leave the clusters (misreads to unrelated classes, deletions), so the
# within-cluster rate falls and stops measuring confusability. The CSV keeps every level.
PLOT_MAX = 1.0
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3dd", "#fcfcfb"


def load(sev: str) -> pd.DataFrame:
    c = pd.read_parquet(SWEEP / f"sev_{sev}_chars.parquet")
    return c[(c.suite == "a") & ~c.cropped]


def main():
    sevs = sorted(p.name[4:8] for p in SWEEP.glob("sev_*_chars.parquet"))
    clusters = json.loads((OUT / "clusters.json").read_text())["objective"]

    rows = []
    for s in sevs:
        c = load(s)
        for (engine, font), g in c.groupby(["engine", "font"]):
            rows.append({"severity": float(s), "engine": engine, "font": font,
                         "within_cluster_pct": 100 * within_cluster_rate(g, clusters),
                         "all_char_error_pct": 100 * (g.pred != g.truth).mean()})
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "plot1_severity.csv", index=False)

    fonts = list(BASELINES)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True, facecolor=SURFACE)
    for ax, engine, title in zip(axes, ("paddle", "tesseract"), ("PaddleOCR (objective)", "Tesseract (gate)")):
        ax.set_facecolor(SURFACE)
        for i, font in enumerate(fonts):
            d = df[(df.engine == engine) & (df.font == font) & (df.severity <= PLOT_MAX)].sort_values("severity")
            ax.plot(d.severity, d.within_cluster_pct, color=COLORS[i], lw=2, marker=MARKERS[i], ms=6,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, label=font)
        ax.axhline(2, color=INK2, lw=1, ls="--")
        ax.text(0, 2, " PRD 2% target", va="bottom", fontsize=8, color=INK2)
        ax.set_title(title, color=INK, fontsize=11, loc="left")
        ax.set_xlabel("severity", color=INK2)
        ax.grid(color=GRID, lw=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK2)
    axes[0].set_ylabel("within-cluster substitution %", color=INK2)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.suptitle(f"Baseline fonts, suite (a), uncropped. Clusters: {clusters}", fontsize=9, color=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "plot1_severity.png", dpi=130, facecolor=SURFACE)
    print(f"clusters: {clusters}")
    print(df.pivot_table(index=["engine", "font"], columns="severity", values="within_cluster_pct").round(1).to_string())


if __name__ == "__main__":
    main()
