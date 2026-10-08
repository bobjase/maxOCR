"""Analyse the Windows font survey: what makes 0 and O readable for PaddleOCR and Tesseract?

Per face: 0/O pair confusion (mean of P(0->O) and P(O->0)), 0 and O accuracy, objective-cluster
within-cluster rate, for the clean condition (severity -1) and the operating point. Glyph features
of 0 and O come from the outlines, rasterized at 256 px cap height, normalized by cap height.

    python scripts/survey_analysis.py
Writes out/report/survey_faces.csv, survey_features.csv, survey_0O.png and prints a summary.
Measurement only: no outlines or font files are stored, only numbers.
"""
import glob
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.ndimage import binary_fill_holes, label  # noqa: E402
from scipy.stats import mannwhitneyu, spearmanr  # noqa: E402

from maxocr.analysis import within_cluster_rate  # noqa: E402
from maxocr.render import render  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SURVEY = ROOT / "out" / "survey"
OUT = ROOT / "out" / "report"
CAP_PX = 256
COLORS = {"proportional": "#2a78d6", "monospaced": "#eb6834"}
MARKERS = {"proportional": "o", "monospaced": "s"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3dd", "#fcfcfb"


def glyph_mask(font: str, ch: str, size_pt: float) -> np.ndarray:
    """Ink mask of one glyph at high resolution (cap height of a few hundred px); features are
    normalized by the measured cap height, so the exact scale does not matter."""
    dpi = int(round(200 * CAP_PX / 13.33))
    img = render(font, ch, size_pt, dpi)
    return img < 128


def features(font: str, size_pt: float) -> dict:
    m0, mO, mH = (glyph_mask(font, c, size_pt) for c in "0OH")

    def bbox(m):
        ys, xs = np.nonzero(m)
        return ys.min(), ys.max(), xs.min(), xs.max()

    y0, y1, _, _ = bbox(mH)
    cap = y1 - y0 + 1
    out = {}
    for name, m in (("0", m0), ("O", mO)):
        a, b, c, d = bbox(m)
        h, w = b - a + 1, d - c + 1
        crop = m[a:b + 1, c:d + 1]
        filled = binary_fill_holes(crop)
        counter = filled & ~crop
        out[f"{name}_width"] = w / cap
        out[f"{name}_height"] = h / cap
        out[f"{name}_aspect"] = w / h
        out[f"{name}_boxiness"] = filled.sum() / (h * w)          # 1 = rectangle, 0.785 = ellipse
        out[f"{name}_ink"] = crop.sum() / (h * w)
        out[f"{name}_counter"] = counter.sum() / (h * w)
        out[f"{name}_holes"] = _count_holes(crop)
        out[f"{name}_pieces"] = int(label(crop)[1])
    out["O_to_0_width"] = out["O_width"] / out["0_width"]
    # Dotted zero: an extra ink piece. Slashed zero: the slash splits the counter into two holes.
    out["zero_inner_mark"] = int(out["0_pieces"] > 1 or out["0_holes"] > 1)
    # Overlap of the two glyphs, left-aligned on the baseline at the same scale.
    h = max(m0.shape[0], mO.shape[0])
    w = max(m0.shape[1], mO.shape[1])
    a0 = np.zeros((h, w), bool)
    aO = np.zeros((h, w), bool)
    a0[:m0.shape[0], :m0.shape[1]] = m0
    aO[:mO.shape[0], :mO.shape[1]] = mO
    out["0O_iou"] = (a0 & aO).sum() / max((a0 | aO).sum(), 1)
    return out


def _count_holes(mask: np.ndarray) -> int:
    background, n = label(~mask)
    # Background components not touching the border are holes.
    border = set(np.unique(np.concatenate([background[0], background[-1], background[:, 0], background[:, -1]])))
    return len([k for k in range(1, n + 1) if k not in border])


def main():
    faces = pd.DataFrame(json.loads((SURVEY / "faces.json").read_text()))
    chars = pd.concat(pd.read_parquet(p) for p in sorted(glob.glob(str(SURVEY / "batch_*_chars.parquet"))))
    chars = chars[(chars.suite == "a") & ~chars.cropped]
    objective = json.loads((OUT / "clusters.json").read_text())["objective"]

    rows = []
    for (font, engine, sev), g in chars.groupby(["font", "engine", "severity"]):
        z, o = g[g.truth == "0"], g[g.truth == "O"]
        rows.append({"font": font, "engine": engine, "condition": "clean" if sev < 0 else f"s={sev:g}",
                     "acc_0": (z.pred == "0").mean(), "acc_O": (o.pred == "O").mean(),
                     "pair_confusion": ((z.pred == "O").mean() + (o.pred == "0").mean()) / 2,
                     "within_cluster": within_cluster_rate(g, objective),
                     "char_error": (g.pred != g.truth).mean(), "n_0": len(z), "n_O": len(o)})
    per = pd.DataFrame(rows).merge(faces, on="font")
    per.to_csv(OUT / "survey_faces.csv", index=False)

    feats = []
    for f in faces.itertuples():
        try:
            feats.append({"font": f.font, **features(f.font, f.size_pt)})
        except Exception as e:  # odd fonts (no H outline etc.) are skipped, not fatal
            print(f"features skipped for {f.face}: {e}")
    feats = pd.DataFrame(feats).merge(faces, on="font")
    feats.to_csv(OUT / "survey_features.csv", index=False)

    d = per.merge(feats.drop(columns=["face", "monospaced", "size_pt"]), on="font")
    feature_cols = ["O_to_0_width", "0_width", "O_width", "0_aspect", "O_aspect", "0_boxiness", "O_boxiness",
                    "zero_inner_mark", "0O_iou", "0_ink", "O_ink", "monospaced"]
    print(f"{faces.shape[0]} faces surveyed ({int(faces.monospaced.sum())} monospaced), "
          f"{feats.shape[0]} with features\n")
    print("Spearman correlation of glyph features with 0/O pair confusion (negative = feature helps):")
    corr = {}
    for (engine, cond), g in d.groupby(["engine", "condition"]):
        corr[f"{engine} {cond}"] = {c: spearmanr(g[c].astype(float), g.pair_confusion).statistic for c in feature_cols}
    print(pd.DataFrame(corr).round(2).to_string())

    print("\nMonospaced vs proportional, median 0/O pair confusion %:")
    for (engine, cond), g in d.groupby(["engine", "condition"]):
        m, p = g[g.monospaced].pair_confusion, g[~g.monospaced].pair_confusion
        pval = mannwhitneyu(m, p).pvalue if len(m) and len(p) else float("nan")
        print(f"  {engine:9} {cond:6}  mono {100 * m.median():5.1f} (n={len(m)})   "
              f"proportional {100 * p.median():5.1f} (n={len(p)})   Mann-Whitney p={pval:.3g}")

    # Ranking: mean pair confusion over both engines and both conditions.
    rank = d.groupby(["face", "font", "monospaced"]).agg(pair_confusion=("pair_confusion", "mean"),
                                                         within_cluster=("within_cluster", "mean"),
                                                         char_error=("char_error", "mean")).reset_index()
    rank = rank.sort_values("pair_confusion")
    rank.to_csv(OUT / "survey_ranking.csv", index=False)
    print("\nTop 25 faces by 0/O pair confusion (mean over engines and conditions, %):")
    print(rank.head(25)[["face", "monospaced", "pair_confusion", "within_cluster", "char_error"]]
          .assign(pair_confusion=lambda x: (100 * x.pair_confusion).round(1),
                  within_cluster=lambda x: (100 * x.within_cluster).round(1),
                  char_error=lambda x: (100 * x.char_error).round(1)).to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, facecolor=SURFACE)
    for ax, engine, title in zip(axes, ("paddle", "tesseract"), ("PaddleOCR", "Tesseract")):
        ax.set_facecolor(SURFACE)
        g = d[(d.engine == engine) & (d.condition == "clean")]
        for kind, sub in (("proportional", g[~g.monospaced]), ("monospaced", g[g.monospaced])):
            ax.scatter(sub.O_to_0_width, 100 * sub.pair_confusion, color=COLORS[kind], marker=MARKERS[kind],
                       s=26, edgecolors=SURFACE, linewidths=1, label=f"{kind} (n={len(sub)})", zorder=3)
        ax.set_title(f"{title}, clean: 0/O confusion vs O-to-0 width ratio", color=INK, fontsize=11, loc="left")
        ax.set_xlabel("width of O / width of 0", color=INK2)
        ax.grid(color=GRID, lw=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK2)
    axes[0].set_ylabel("0/O pair confusion %", color=INK2)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "survey_0O.png", dpi=130, facecolor=SURFACE)


if __name__ == "__main__":
    main()
