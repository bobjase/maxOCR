"""Validate discovered pair designs: all three engines (PARSeq held out), R40c pixel distance, clean floor.

For the top-K archive entries and the base font: validation bank (5,000 lines, s=0.5, suite a,
uncropped) pair confusion and within-objective-cluster rate on PaddleOCR, Tesseract and PARSeq;
R40c: RMS pixel distance between the two glyphs under the same degradation (higher = more
different shapes, i.e. real separation rather than engine-specific cues); clean accuracy of the pair
characters on both engines vs the base.

    python scripts/discover_validate.py [--pair 0O] [--top 8]
Writes out/discover/<pair>/validation.csv.
"""
import argparse
import dataclasses
import json
import sys
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.analysis import within_cluster_rate  # noqa: E402
from maxocr.degrade import degrade, make_instance, params  # noqa: E402
from maxocr.engines.parseq import Parseq  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def pair_rate(d: pd.DataFrame, a: str, b: str) -> float:
    x, y = d[d.truth == a], d[d.truth == b]
    return float(((x.pred == b).sum() + (y.pred == a).sum()) / max(len(x) + len(y), 1))


def _imgs(args):
    font, insts = args
    import cv2
    cv2.setNumThreads(1)
    return [degrade(font, i, rung0.SEVERITY) for i in insts]


def pixel_distance(font: str, a: str, b: str, n: int = 120) -> float:
    vals, i = [], 0
    while len(vals) < n:
        inst = make_instance(i, a, 515)
        i += 1
        if params(inst, rung0.SEVERITY)["crop"]:
            continue
        x = 1 - degrade(font, inst, rung0.SEVERITY, binarize=False).astype(float) / 255
        y = 1 - degrade(font, dataclasses.replace(inst, text=b), rung0.SEVERITY, binarize=False).astype(float) / 255
        if x.shape != y.shape:
            w = min(x.shape[1], y.shape[1])
            x, y = x[:, :w], y[:, :w]
        vals.append(np.sqrt(np.mean((x - y) ** 2)))
    return float(np.mean(vals))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="0O")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()
    a, b = args.pair[0], args.pair[1]
    d = ROOT / "out" / "discover" / args.pair
    archive = json.loads((d / "archive.json").read_text())
    base = json.loads((ROOT / "out" / "amalgam_opt" / "08BDEOQ" / "elite.json").read_text())["font"]
    fonts = {"base (optimized amalgam)": base}
    for k, r in enumerate(archive[:args.top]):
        fonts[f"#{k + 1} cell {r['cell']} w{r['ratio']:.2f} iou{r['iou']:.2f}"] = r["font"]

    val = rung0.bank("val")
    paddle = rung0.PaddleRec()
    jobs = [Job(n, p, rung0.SEVERITY, "a", c) for n, p in fonts.items() for c in chunk(val, 50)]
    chars, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False)
    clean_jobs = [Job(n, p, -1.0, "a", c, clean=True) for n, p in fonts.items() for c in chunk(rung0.bank("clean"), 50)]
    clean, _, _ = run(clean_jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False)

    model = Parseq()
    rows = []
    with get_context("spawn").Pool(16) as pool:
        for n, p in fonts.items():
            imgs = [im for part in pool.map(_imgs, [(p, val[i:i + 250]) for i in range(0, len(val), 250)]) for im in part]
            recs = []
            for inst, pred in zip(val, model.read(imgs)):
                if inst.cropped:
                    continue
                _, mapping, _ = align(inst.text, pred)
                recs += [{"truth": inst.text[i], "pred": pred[j] if j is not None else ""} for i, j in enumerate(mapping)]
            pq = pd.DataFrame(recs)
            g = chars[(chars.font == n) & ~chars.cropped]
            c = clean[clean.font == n]
            row = {"font": n, "pixel_dist_R40c": round(pixel_distance(p, a, b), 4)}
            for e, dd in (("paddle", g[g.engine == "paddle"]), ("tesseract", g[g.engine == "tesseract"]), ("parseq", pq)):
                # Correct reads of each pair glyph: a pair rate alone misses glyphs read as a third character.
                row[f"{e}_acc_{a}_pct"] = round(100 * float((dd[dd.truth == a].pred == a).mean()), 2)
                row[f"{e}_acc_{b}_pct"] = round(100 * float((dd[dd.truth == b].pred == b).mean()), 2)
                row[f"{e}_char_err_pct"] = round(100 * float((dd.pred != dd.truth).mean()), 2)
                row[f"{e}_pair_pct"] = round(100 * pair_rate(dd, a, b), 2)
                row[f"{e}_within_pct"] = round(100 * within_cluster_rate(dd, rung0.OBJECTIVE), 2)
            for e in ("paddle", "tesseract"):
                cc = c[(c.engine == e) & c.truth.isin([a, b])]
                row[f"{e}_clean_acc_pair_pct"] = round(100 * float((cc.pred == cc.truth).mean()), 2)
            rows.append(row)
            print(json.dumps(row), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(d / "validation.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
