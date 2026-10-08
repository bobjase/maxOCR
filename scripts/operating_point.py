"""Section 7 operating point, relative rule (v0.4; see DECISIONS.md).

The PRD's 2% absolute target is unreachable (every font exceeds it at s=0), so it is replaced by a
relative rule, keeping the PRD order "severity locked first, font chosen second":
1. Provisional clusters: PaddleOCR, sweep bank, s=0, suite (a), uncropped, R22b + floors.
2. Anchor font: lowest within-cluster rate at s=0, averaged over the two engines.
3. Lock severity: first swept s where the anchor's PaddleOCR (objective engine) within-cluster
   rate reaches 1.5x its s=0 rate.
4. The best baseline is chosen afterwards AT the locked severity, on the validation bank with the
   final clusters (scripts/m1a_validation.py), never here.

Why not the median font, as PRD step 2 has it: Tesseract's within-cluster rate barely grows below
s=0.5 and then falls as errors leave the clusters, so a two-engine median never reaches 1.5x, and a
PaddleOCR-only median only gets there near s=1.0, where the metric has stopped measuring confusability.

Writes out/report/operating_point.json.
"""
import json
from pathlib import Path

import pandas as pd

from maxocr.analysis import MIN_RATE, MIN_SHARE, components, significant_edges, substitution_counts, within_cluster_rate

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "out" / "sweep"
OUT = ROOT / "out" / "report"
RATIO = 1.5


def load(s: float) -> pd.DataFrame:
    c = pd.read_parquet(SWEEP / f"sev_{s:.2f}_chars.parquet",
                        columns=["engine", "suite", "font", "truth", "pred", "cropped"])
    return c[(c.suite == "a") & ~c.cropped]


def main():
    sevs = sorted(float(p.name[4:8]) for p in SWEEP.glob("sev_*_chars.parquet"))
    base = load(0.0)
    clusters = components(significant_edges(substitution_counts(base[base.engine == "paddle"]),
                                            min_share=MIN_SHARE, min_rate=MIN_RATE))
    rates = {}
    for s in sevs:
        for (e, f), g in load(s).groupby(["engine", "font"]):
            rates[(s, e, f)] = 100 * within_cluster_rate(g, clusters)
    fonts = sorted({f for _, _, f in rates})

    clean_agg = {f: (rates[(0.0, "paddle", f)] + rates[(0.0, "tesseract", f)]) / 2 for f in fonts}
    anchor = min(fonts, key=clean_agg.get)
    clean = rates[(0.0, "paddle", anchor)]
    op = next(s for s in sevs if rates[(s, "paddle", anchor)] >= RATIO * clean)

    result = {"provisional_clusters": clusters, "min_share": MIN_SHARE, "min_rate": MIN_RATE, "ratio": RATIO,
              "anchor_font": anchor, "clean_aggregate_pct": {f: round(v, 3) for f, v in sorted(clean_agg.items(), key=lambda x: x[1])},
              "anchor_paddle_by_severity_pct": {f"{s:.2f}": round(rates[(s, "paddle", anchor)], 3) for s in sevs},
              "severity": op}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "operating_point.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
