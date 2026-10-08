"""R40 pixel-distance covariate (and the R40c measurement, reused later for candidates).

For each font, each pair of characters inside an objective cluster, and each severity, both
characters are rendered as single-glyph lines with the SAME degradation instance (same pen
origin, jitter and noise; no re-centring) and compared on grayscale (suite b) rasters:
  L2  = RMS difference of ink coverage in [0, 1]   (higher = more different)
  NCC = normalized cross-correlation               (higher = more alike)
Averaged over N uncropped instances. Joined to the realized pair substitution rate
(mean of a->b and b->a, suite a, uncropped) from the sweep at the same severity.

    python scripts/r40.py [--n 150] [--severities 0 0.5 1.0]
Writes out/report/r40_pixel_distance.csv and .png.
"""
import argparse
import dataclasses
import json
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from maxocr.degrade import degrade, make_instance, params  # noqa: E402
from maxocr.fonts import BASELINES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "report"
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
MARKERS = ["o", "s", "^", "D", "v", "P"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3dd", "#fcfcfb"
R40_SEED = 505


def pair_distance(font: str, a: str, b: str, s: float, n: int) -> tuple[float, float]:
    l2s, nccs = [], []
    i = 0
    while len(l2s) < n:
        inst = make_instance(i, a, R40_SEED)
        i += 1
        if params(inst, s)["crop"]:
            continue
        # Same draws for both characters: only the glyph differs.
        x = 1 - degrade(font, inst, s, binarize=False).astype(np.float64) / 255
        y = 1 - degrade(font, dataclasses.replace(inst, text=b), s, binarize=False).astype(np.float64) / 255
        if x.shape != y.shape:
            continue
        l2s.append(np.sqrt(np.mean((x - y) ** 2)))
        xc, yc = x - x.mean(), y - y.mean()
        nccs.append(float((xc * yc).sum() / np.sqrt((xc ** 2).sum() * (yc ** 2).sum() + 1e-12)))
    return float(np.mean(l2s)), float(np.mean(nccs))


def realized_pair_rates(sev: float) -> pd.DataFrame:
    f = ROOT / "out" / "sweep" / f"sev_{sev:.2f}_chars.parquet"
    c = pd.read_parquet(f, columns=["engine", "suite", "font", "truth", "pred", "cropped"])
    c = c[(c.suite == "a") & ~c.cropped]
    n = c.groupby(["engine", "font", "truth"]).size().rename("n")
    k = c[c.pred != c.truth].groupby(["engine", "font", "truth", "pred"]).size().rename("k").reset_index()
    k = k.join(n, on=["engine", "font", "truth"])
    k["rate"] = k.k / k.n
    return k.set_index(["engine", "font", "truth", "pred"]).rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--severities", type=float, nargs="+", default=[0.0, 0.5, 1.0])
    a = ap.parse_args()
    objective = json.loads((OUT / "clusters.json").read_text())["objective"]
    pairs = [p for g in objective for p in combinations(g, 2)]

    rows = []
    for s in a.severities:
        rates = realized_pair_rates(s)
        for font, path in BASELINES.items():
            for x, y in pairs:
                l2, ncc = pair_distance(str(path), x, y, s, a.n)
                row = {"severity": s, "font": font, "pair": f"{x}/{y}", "l2": l2, "ncc": ncc}
                for e in ("paddle", "tesseract"):
                    r = [rates.get((e, font, x, y), 0.0), rates.get((e, font, y, x), 0.0)]
                    row[f"{e}_pair_rate_pct"] = 100 * float(np.mean(r))
                rows.append(row)
        print(f"severity {s}: done", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "r40_pixel_distance.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, facecolor=SURFACE)
    for ax, e, title in zip(axes, ("paddle", "tesseract"), ("PaddleOCR", "Tesseract")):
        ax.set_facecolor(SURFACE)
        for i, font in enumerate(BASELINES):
            d = df[df.font == font]
            ax.scatter(d.l2, d[f"{e}_pair_rate_pct"], color=COLORS[i], marker=MARKERS[i], s=28,
                       edgecolors=SURFACE, linewidths=1, label=font)
        ax.set_title(f"{title}: pair substitution vs pixel distance", color=INK, fontsize=11, loc="left")
        ax.set_xlabel("RMS pixel difference of the pair (same degradation instance)", color=INK2)
        ax.grid(color=GRID, lw=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK2)
    axes[0].set_ylabel("pair substitution rate %", color=INK2)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.suptitle(f"R40 covariate, severities {a.severities}, objective-cluster pairs", fontsize=9, color=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "r40_pixel_distance.png", dpi=130, facecolor=SURFACE)
    print(df.groupby(["severity"])[["l2", "ncc", "paddle_pair_rate_pct", "tesseract_pair_rate_pct"]]
          .corr(method="spearman").round(2).to_string())


if __name__ == "__main__":
    main()
