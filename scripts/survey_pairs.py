"""Per-pair view of the Windows font survey: for every confusable pair, which fonts do the engines
keep apart, and what do those glyphs look like?

Pairs are the union of objective (PaddleOCR) and gate (Tesseract) cluster pairs. For each pair a/b
and face: pair confusion = mean of P(a->b) and P(b->a), averaged over both engines and both
conditions (clean, operating point), suite (a), uncropped. Faces with fewer than MIN_N occurrences
of either character are left out of that pair's ranking.

    python scripts/survey_pairs.py
Writes out/report/survey_pairs.csv (per pair x face), survey_pair_features.csv (generic shape
features vs confusion, Spearman per pair), and contact sheets out/report/survey_sheets/<pair>.png
(best 8 and worst 8 faces). Sheets are local working images of installed fonts, not committed.
"""
import glob
import json
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.ndimage import label
from scipy.stats import spearmanr

from maxocr.render import render

ROOT = Path(__file__).resolve().parents[1]
SURVEY = ROOT / "out" / "survey"
OUT = ROOT / "out" / "report"
SHEETS = OUT / "survey_sheets"
MIN_N = 15
MAX_CHAR_ERROR = 0.15  # readable faces only: unreadable faces look "good" on every pair
SHEET_DPI = 1200   # ~80 px cap height at the survey's matched sizes


def pair_list() -> list[tuple[str, str]]:
    c = json.loads((OUT / "clusters.json").read_text())
    pairs = {tuple(sorted(p)) for g in c["objective"] + c["gate"] for p in combinations(g, 2)}
    return sorted(pairs)


def mask(font: str, ch: str, size_pt: float) -> np.ndarray:
    return render(font, ch, size_pt, SHEET_DPI) < 128


def pair_features(font: str, a: str, b: str, size_pt: float) -> dict:
    ma, mb = mask(font, a, size_pt), mask(font, b, size_pt)

    def box(m):
        ys, xs = np.nonzero(m)
        return ys.min(), ys.max(), xs.min(), xs.max()

    def holes(m):
        bg, n = label(~m)
        border = set(np.unique(np.concatenate([bg[0], bg[-1], bg[:, 0], bg[:, -1]])))
        return len([k for k in range(1, n + 1) if k not in border])

    (a0, a1, a2, a3), (b0, b1, b2, b3) = box(ma), box(mb)
    wa, wb, ha, hb = a3 - a2 + 1, b3 - b2 + 1, a1 - a0 + 1, b1 - b0 + 1
    h, w = max(ma.shape[0], mb.shape[0]), max(ma.shape[1], mb.shape[1])
    pa, pb = np.zeros((h, w), bool), np.zeros((h, w), bool)
    pa[:ma.shape[0], :ma.shape[1]] = ma
    pb[:mb.shape[0], :mb.shape[1]] = mb
    return {"width_ratio": max(wa, wb) / min(wa, wb), "height_ratio": max(ha, hb) / min(ha, hb),
            "iou": (pa & pb).sum() / max((pa | pb).sum(), 1),
            "ink_ratio": max(ma.sum(), mb.sum()) / max(min(ma.sum(), mb.sum()), 1),
            "holes_differ": int(holes(ma) != holes(mb)),
            "pieces_differ": int(label(ma)[1] != label(mb)[1])}


def sheet(pair: tuple[str, str], best: pd.DataFrame, worst: pd.DataFrame, sizes: dict) -> np.ndarray:
    def tile(row, tag):
        img = render(row.font, f"{pair[0]} {pair[1]}", sizes[row.font], SHEET_DPI)
        img = cv2.copyMakeBorder(img, 4, 30, 10, 10, cv2.BORDER_CONSTANT, value=255)
        label_txt = f"{tag} {row.face[:28]}  {100 * row.pair_confusion:.0f}%"
        cv2.putText(img, label_txt, (6, img.shape[0] - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 80, 1, cv2.LINE_AA)
        return img

    tiles = [tile(r, "best") for r in best.itertuples()] + [tile(r, "worst") for r in worst.itertuples()]
    W = max(t.shape[1] for t in tiles)
    H = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, W - t.shape[1], cv2.BORDER_CONSTANT, value=255) for t in tiles]
    rows = [np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]
    sep = np.full((6, rows[0].shape[1]), 160, np.uint8)
    half = len(rows) // 2
    return np.vstack(rows[:half] + [sep] + rows[half:])


def main():
    faces = pd.DataFrame(json.loads((SURVEY / "faces.json").read_text()))
    sizes = dict(zip(faces.font, faces.size_pt))
    chars = pd.concat(pd.read_parquet(p, columns=["font", "face", "engine", "severity", "suite", "truth", "pred", "cropped"])
                      for p in sorted(glob.glob(str(SURVEY / "batch_*_chars.parquet"))))
    chars = chars[(chars.suite == "a") & ~chars.cropped]
    n = chars.groupby(["font", "engine", "severity", "truth"]).size()
    k = chars[chars.pred != chars.truth].groupby(["font", "engine", "severity", "truth", "pred"]).size()

    rows = []
    for a, b in pair_list():
        for font in faces.font:
            rates, ns = [], []
            for e in ("paddle", "tesseract"):
                for s in (-1.0, 0.5):
                    na, nb = n.get((font, e, s, a), 0), n.get((font, e, s, b), 0)
                    ns.append(min(na, nb))
                    if na and nb:
                        rates.append((k.get((font, e, s, a, b), 0) / na + k.get((font, e, s, b, a), 0) / nb) / 2)
            if rates and min(ns) >= MIN_N:
                rows.append({"pair": f"{a}/{b}", "font": font, "pair_confusion": float(np.mean(rates)),
                             "min_n": int(min(ns))})
    err = pd.read_csv(OUT / "survey_faces.csv").groupby("font").char_error.mean()
    readable = set(err[err < MAX_CHAR_ERROR].index)
    print(f"readable faces: {len(readable)} of {len(faces)}")
    per = pd.DataFrame(rows).merge(faces, on="font")
    per = per[per.font.isin(readable)]
    per.to_csv(OUT / "survey_pairs.csv", index=False)

    SHEETS.mkdir(parents=True, exist_ok=True)
    summary, corr_rows = [], []
    for pair, g in per.groupby("pair"):
        g = g.sort_values("pair_confusion")
        a, b = pair.split("/")
        summary.append({"pair": pair, "faces": len(g), "median_pct": 100 * g.pair_confusion.median(),
                        "best_pct": 100 * g.pair_confusion.iloc[0], "best_face": g.face.iloc[0],
                        "share_under_1pct": float((g.pair_confusion < 0.01).mean())})
        cv2.imwrite(str(SHEETS / f"{a}_{b}.png"), sheet((a, b), g.head(8), g.tail(8), sizes))
        feats = []
        for r in g.itertuples():
            try:
                feats.append({"font": r.font, "pair_confusion": r.pair_confusion, **pair_features(r.font, a, b, r.size_pt)})
            except Exception:
                continue
        f = pd.DataFrame(feats)
        if len(f) > 20:
            corr_rows.append({"pair": pair, **{c: spearmanr(f[c], f.pair_confusion).statistic
                                               for c in ["width_ratio", "height_ratio", "iou", "ink_ratio",
                                                         "holes_differ", "pieces_differ"]}})
    s = pd.DataFrame(summary).sort_values("median_pct", ascending=False)
    pd.DataFrame(corr_rows).to_csv(OUT / "survey_pair_features.csv", index=False)
    print("Per pair: median confusion across faces, the best face, share of faces under 1% (%):")
    print(s.round(2).to_string(index=False))
    print("\nSpearman of generic shape features with pair confusion (negative = more of it helps):")
    print(pd.DataFrame(corr_rows).set_index("pair").round(2).to_string())


if __name__ == "__main__":
    main()
