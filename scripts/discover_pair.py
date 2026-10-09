"""Discovery for a confusable pair: MAP-Elites over constructive glyph genomes (maxocr/strokes.py).

Both glyphs of the pair (default 0 and O) evolve together; the rest of the font stays at the base
(the optimized amalgam). The archive keeps the best pair in each cell of a 2-D behaviour grid:
  d1 = ink width of the second glyph / ink width of the first (e.g. O / 0)
  d2 = overlap (IoU) of the two glyph masks, aligned at the left edge and baseline (low = more different)
so the search returns qualitatively different solutions, not one optimum.

Fitness (exploratory; uses Tesseract as well as PaddleOCR, see DECISIONS open question 5): on a
pair-weighted bank at s=0.5, suite (a), the mean over the two engines of the accuracy of reading
each pair glyph correctly, minus a penalty for any rise in overall character error above the base
font. PARSeq is held out.

    python scripts/discover_pair.py [--pair 0O] [--evals 2000] [--batch 32]
Writes out/discover/<pair>/archive.json, log.jsonl, gallery.png; fonts in ~/maxocr-work/discover/.
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.build import WORK  # noqa: E402
from maxocr.corpus import PRIMARY_ALPHABET, make_strings  # noqa: E402
from maxocr.degrade import make_instance  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from maxocr.strokes import from_glyph, mutate, primitive, rasterize, with_glyphs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
D1 = np.linspace(0.85, 2.05, 9)       # width-ratio bin edges (8 bins)
D2 = np.linspace(0.10, 0.95, 9)       # IoU bin edges (8 bins)
PAIR_BANK_SEED = 4242


def pair_bank(a: str, b: str, n: int = 240):
    members = {c for g in rung0.OBJECTIVE for c in g}
    w = np.array([8.0 if c in (a, b) else 2.0 if c in members else 1.0 for c in PRIMARY_ALPHABET])
    return [make_instance(i, s, PAIR_BANK_SEED) for i, s in enumerate(make_strings(n, PAIR_BANK_SEED, weights=w / w.sum()))]


def descriptors(ga, gb) -> tuple[float, float, float]:
    ma, _ = rasterize(ga)
    mb, _ = rasterize(gb)

    def ink(m):
        ys, xs = np.nonzero(m)
        return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    ia, ib = ink(ma), ink(mb)
    ratio = ib.shape[1] / ia.shape[1]
    H, W = max(ia.shape[0], ib.shape[0]), max(ia.shape[1], ib.shape[1])
    pa, pb = np.zeros((H, W), bool), np.zeros((H, W), bool)
    pa[H - ia.shape[0]:, :ia.shape[1]] = ia
    pb[H - ib.shape[0]:, :ib.shape[1]] = ib
    iou = (pa & pb).sum() / max((pa | pb).sum(), 1)
    return ratio, iou, float(np.mean(ia)) / max(float(np.mean(ib)), 1e-6)


def cell(ratio, iou):
    i = int(np.clip(np.searchsorted(D1, ratio) - 1, 0, len(D1) - 2))
    j = int(np.clip(np.searchsorted(D2, iou) - 1, 0, len(D2) - 2))
    return i, j


ERR_PENALTY = 2.0   # per unit of overall character error above the base font's


def fitness(chars, a, b, base_err: dict | None) -> dict:
    """Reward reading each glyph CORRECTLY (not merely "not as its twin": an earlier version only
    penalized a<->b swaps, and the search made O read as C and 0 as nothing). Penalize any rise in
    overall character error above the base font, so no glyph can win by turning into a third one."""
    out = {}
    for e in ("paddle", "tesseract"):
        g = chars[(chars.engine == e) & ~chars.cropped]
        x, y = g[g.truth == a], g[g.truth == b]
        acc = (float((x.pred == a).mean()) + float((y.pred == b).mean())) / 2
        pair = ((x.pred == b).sum() + (y.pred == a).sum()) / max(len(x) + len(y), 1)
        err = float((g.pred != g.truth).mean())
        out[e] = {"acc": acc, "pair": float(pair), "err": err}
    penalty = 0.0 if base_err is None else np.mean([max(0.0, out[e]["err"] - base_err[e]) for e in ("paddle", "tesseract")])
    out["fitness"] = float(np.mean([out[e]["acc"] for e in ("paddle", "tesseract")]) - ERR_PENALTY * penalty)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="0O")
    ap.add_argument("--evals", type=int, default=2000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    a, b = args.pair[0], args.pair[1]
    out = ROOT / "out" / "discover" / args.pair
    out.mkdir(parents=True, exist_ok=True)
    fdir = WORK / "discover" / args.pair
    fdir.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.jsonl", "a")
    rng = np.random.default_rng(args.seed)
    base = json.loads((ROOT / "out" / "amalgam_opt" / "08BDEOQ" / "elite.json").read_text())["font"]
    ofl = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}

    # Seeds: the base font's own pair, pairs from several OFL serif faces, and primitive shapes.
    seeds = [("base", from_glyph(base, a), from_glyph(base, b))]
    for fam in ("gelasio", "librebaskerville", "spectral", "sourceserif4", "atkinsonhyperlegible", "tinos"):
        seeds.append((fam, from_glyph(ofl[fam], a), from_glyph(ofl[fam], b)))
    if (a, b) == ("0", "O"):
        seeds.append(("primitives capsule/ellipse", primitive("capsule"), primitive("ellipse")))
        seeds.append(("primitives diamond/ellipse", primitive("diamond"), primitive("ellipse")))

    bank = pair_bank(a, b)
    paddle = rung0.PaddleRec()
    archive: dict[tuple[int, int], dict] = {}
    n_eval, k_font, t0 = 0, 0, time.time()
    base_err = None

    def evaluate(cands):
        nonlocal n_eval, k_font
        fonts = {}
        for c in cands:
            p = str(fdir / f"c{k_font:05d}.ttf")
            k_font += 1
            with_glyphs(base, {a: c["ga"], b: c["gb"]}, p)
            c["font"] = p
            fonts[p] = c
        jobs = [Job(p, p, rung0.SEVERITY, "a", ch) for p in fonts for ch in chunk(bank, 60)]
        chars, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False)
        for p, g in chars.groupby("font"):
            c = fonts[p]
            c["score"] = fitness(g, a, b, base_err)
            ratio, iou, ink_ratio = descriptors(c["ga"], c["gb"])
            c["ratio"], c["iou"] = ratio, iou
            key = cell(ratio, iou)
            prev = archive.get(key)
            improved = prev is None or c["score"]["fitness"] > prev["score"]["fitness"]
            if improved:
                archive[key] = c
            n_eval += 1
            logf.write(json.dumps({"n": n_eval, "cell": key, "fitness": round(c["score"]["fitness"], 4),
                                   "paddle_acc": round(c["score"]["paddle"]["acc"], 4),
                                   "tess_acc": round(c["score"]["tesseract"]["acc"], 4),
                                   "paddle_err": round(c["score"]["paddle"]["err"], 4),
                                   "tess_err": round(c["score"]["tesseract"]["err"], 4),
                                   "ratio": round(ratio, 3), "iou": round(iou, 3), "ops": c.get("ops", []),
                                   "origin": c.get("origin"), "new_elite": bool(improved)}) + "\n")
        logf.flush()

    # The base alone first: its overall error is the reference for the error penalty.
    evaluate([{"ga": seeds[0][1], "gb": seeds[0][2], "origin": "base", "ops": []}])
    b0 = next(iter(archive.values()))["score"]
    base_err = {e: b0[e]["err"] for e in ("paddle", "tesseract")}
    archive.clear()
    evaluate([{"ga": ga, "gb": gb, "origin": name, "ops": []} for name, ga, gb in seeds])
    best0 = max(archive.values(), key=lambda c: c["score"]["fitness"])
    print(json.dumps({"event": "seeded", "cells": len(archive), "best": round(best0["score"]["fitness"], 4),
                      "best_origin": best0["origin"]}), flush=True)
    while n_eval < args.evals:
        elites = list(archive.values())
        cands = []
        for _ in range(args.batch):
            parent = elites[int(rng.integers(len(elites)))]
            ga, gb, ops = parent["ga"], parent["gb"], []
            which = rng.choice(["a", "b", "both"], p=[0.4, 0.4, 0.2])
            if which in ("a", "both"):
                ga, o = mutate(ga, rng)
                ops += [f"{a}:{x}" for x in o]
            if which in ("b", "both"):
                gb, o = mutate(gb, rng)
                ops += [f"{b}:{x}" for x in o]
            cands.append({"ga": ga, "gb": gb, "origin": parent["origin"], "ops": parent.get("ops", [])[-12:] + ops})
        evaluate(cands)
        best = max(archive.values(), key=lambda c: c["score"]["fitness"])
        print(json.dumps({"event": "batch", "evals": n_eval, "cells": len(archive),
                          "best_fitness": round(best["score"]["fitness"], 4),
                          "best_paddle_acc": round(best["score"]["paddle"]["acc"], 4),
                          "best_tess_acc": round(best["score"]["tesseract"]["acc"], 4),
                          "best_paddle_err": round(best["score"]["paddle"]["err"], 4),
                          "best_tess_err": round(best["score"]["tesseract"]["err"], 4),
                          "minutes": round((time.time() - t0) / 60, 1)}), flush=True)
        with open(out / "archive.pkl", "wb") as f:
            pickle.dump(archive, f)

    summary = sorted(({"cell": list(k), "fitness": round(c["score"]["fitness"], 4), "ratio": round(c["ratio"], 3),
                       "iou": round(c["iou"], 3), "paddle": c["score"]["paddle"], "tesseract": c["score"]["tesseract"],
                       "origin": c["origin"], "ops": c.get("ops", []), "font": c["font"]}
                      for k, c in archive.items()), key=lambda r: -r["fitness"])
    (out / "archive.json").write_text(json.dumps(summary, indent=1))
    gallery(summary[:24], a, b, out / "gallery.png", base)
    print(json.dumps({"event": "done", "evals": n_eval, "cells": len(archive), "top": summary[:3]})[:1500], flush=True)


def gallery(rows, a, b, path, base):
    from maxocr.render import render
    tiles = []
    for r in [{"font": base, "fitness": None, "origin": "base (amalgam)", "ratio": 0, "iou": 0}] + rows:
        img = render(r["font"], f"{a}{b} {b}{a}8{a}D{b}Q", 9.0, 360)
        img = cv2.copyMakeBorder(img, 4, 34, 8, 8, cv2.BORDER_CONSTANT, value=255)
        label = r["origin"][:22] if r["fitness"] is None else \
            f"F={r['fitness']:.3f} accP={r['paddle']['acc']:.2f} accT={r['tesseract']['acc']:.2f}"
        cv2.putText(img, label, (6, img.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, 50, 1, cv2.LINE_AA)
        if r["fitness"] is not None:
            cv2.putText(img, f"w-ratio {r['ratio']:.2f} IoU {r['iou']:.2f} {r['origin'][:14]}", (6, img.shape[0] - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, 90, 1, cv2.LINE_AA)
        tiles.append(img)
    W = max(t.shape[1] for t in tiles)
    H = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, W - t.shape[1], cv2.BORDER_CONSTANT, value=255) for t in tiles]
    while len(tiles) % 5:
        tiles.append(np.full((H, W), 255, np.uint8))
    cv2.imwrite(str(path), np.vstack([np.hstack(tiles[i:i + 5]) for i in range(0, len(tiles), 5)]))


if __name__ == "__main__":
    main()
