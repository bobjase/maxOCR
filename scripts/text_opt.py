"""Readable-glyph search for MaxOCR Text: CMA-ES over font blends for one pair.

Each glyph of the pair is a blend of real serif fonts (maxocr/blend.py: SDF blend of K serif ingredients
plus width, height, baseline and weight adjustments), so every candidate is a crisp, typographically
plausible letter; the outline-genome search (discover_pair.py) melted serifs and corners into blobs.
Geometry and weight bounds are tight so the glyph stays in the style and weight of the base font.
The blended glyphs are transplanted into the base font; fitness is discover_pair.fitness on the
isolation bank (case-folded reading, optional guard engine and regression penalty), CMA-ES maximizes it.

    python scripts/text_opt.py --pair 4A --base FONT.ttf --run 4A_text [--generations 30] [--popsize 16]
                               [--guard] [--regress 1.0]
Writes out/discover/<run>/{log.jsonl,archive.json} (top candidates, for scratch/check_run.sh) and fonts
to ~/maxocr-work/discover/<run>/.
"""
import argparse
import json
import sys
import time
from multiprocessing import get_context
from pathlib import Path

import cma
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover_pair as dp  # noqa: E402
import rung0  # noqa: E402
from amalgam import char_errors  # noqa: E402
from amalgam_opt import ingredients  # noqa: E402
from golden_mean import transplant  # noqa: E402
from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font  # noqa: E402
from maxocr.build import WORK  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.engines.easyocr_rec import EasyOCRRec  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
K = 5
N_PER_CHAR = K + 4
# Tight: the glyph must stay in the base font's size and weight (bold, wide glyphs looked out of place).
BOUNDS = {"logw": (-0.10, 0.10), "logh": (-0.06, 0.04), "shift": (-0.04, 0.02), "bold": (-1.5, 1.5)}


def decode(x, pair, ing) -> dict[str, CharRecipe]:
    rec = {}
    for j, c in enumerate(pair):
        v = x[j * N_PER_CHAR:(j + 1) * N_PER_CHAR]
        w = np.exp(v[:K] - v[:K].max())
        w = w / w.sum()
        rec[c] = CharRecipe([Ingredient(p, float(wi)) for (p, _), wi in zip(ing[c], w) if wi > 0.01],
                            width_scale=float(np.exp(np.clip(v[K], *BOUNDS["logw"]))),
                            height_scale=float(np.exp(np.clip(v[K + 1], *BOUNDS["logh"]))),
                            bottom_shift=float(np.clip(v[K + 2], *BOUNDS["shift"])),
                            boldness=float(np.clip(v[K + 3], *BOUNDS["bold"])))
    return rec


def x0(pair, ing) -> np.ndarray:
    x = []
    for c in pair:
        w = np.array([1 / (v + 0.005) for _, v in ing[c][:3]] + [0.0] * (K - 3))
        x += list(np.log(np.maximum(w / w.sum(), 0.02))) + [0.0, 0.0, 0.0, 0.0]
    return np.array(x)


def _build(args):
    rec, base, chars, path = args
    tmp = path.replace(".ttf", "_blend.ttf")
    build_font(Recipe(rec, name="MaxOCR text candidate"), tmp)
    transplant(base, tmp, chars, path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--generations", type=int, default=30)
    ap.add_argument("--popsize", type=int, default=16)
    ap.add_argument("--guard", action="store_true")
    ap.add_argument("--regress", type=float, default=0.0)
    a = ap.parse_args()
    pair = a.pair
    out = ROOT / "out" / "discover" / a.run
    out.mkdir(parents=True, exist_ok=True)
    fdir = WORK / "discover" / a.run
    fdir.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.jsonl", "w")
    if a.guard:
        dp.ENGINES = dp.ENGINES + ("tesseract_open",)
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=True)
    paddle, easy = rung0.PaddleRec(**eng), EasyOCRRec(**eng)
    bank, info = dp.isolation_bank(pair)
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    ing = ingredients(char_errors(), path_of)
    pool = get_context("spawn").Pool(8)
    t0 = time.time()

    def score(fonts: dict[str, str], base_err=None, base_per=None) -> dict:
        jobs = [Job(p, p, rung0.SEVERITY, "a", ch) for p in fonts.values() for ch in chunk(bank, 48)]
        chars, strings, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_open=a.guard)
        return {n: dp.fitness(chars[chars.font == p], pair[0], pair[1], base_err, info, base_per, a.regress,
                              strings[strings.font == p] if a.guard else None) for n, p in fonts.items()}

    b0 = score({"base": a.base})["base"]
    base_err = {e: b0[e]["err"] for e in dp.ENGINES}
    base_per = {e: b0[e]["per"] for e in dp.ENGINES}
    b0 = score({"base": a.base}, base_err, base_per)["base"]
    everyone = [{"font": a.base, "fitness": b0["fitness"], "origin": "base", "recipe": None}]
    print(json.dumps({"event": "seeded", "best": round(b0["fitness"], 4),
                      "ingredients": {c: [Path(p).parent.name for p, _ in ing[c]] for c in pair}}), flush=True)
    es = cma.CMAEvolutionStrategy(x0(pair, ing), 0.5, {"popsize": a.popsize, "seed": 11, "verbose": -9,
                                                       "CMA_stds": ([1.0] * K + [0.04, 0.03, 0.02, 0.6]) * len(pair)})
    for gen in range(a.generations):
        xs = es.ask()
        recs = [decode(x, pair, ing) for x in xs]
        paths = [str(fdir / f"g{gen:02d}_{k:02d}.ttf") for k in range(len(xs))]
        pool.map(_build, [(r, a.base, pair, p) for r, p in zip(recs, paths)])
        sc = score({str(k): p for k, p in enumerate(paths)}, base_err, base_per)
        fits = [sc[str(k)]["fitness"] for k in range(len(xs))]
        es.tell(xs, [-f for f in fits])
        for k, p in enumerate(paths):
            rec = {c: {"ingredients": {Path(i.font).parent.name: round(i.weight, 3) for i in recs[k][c].ingredients},
                       "width": round(recs[k][c].width_scale, 3), "height": round(recs[k][c].height_scale, 3),
                       "shift": round(recs[k][c].bottom_shift, 3), "bold": round(recs[k][c].boldness, 2)} for c in pair}
            everyone.append({"font": p, "fitness": fits[k], "origin": f"gen {gen}", "recipe": rec})
            logf.write(json.dumps({"gen": gen, "k": k, "fitness": round(fits[k], 4), "recipe": rec}) + "\n")
        logf.flush()
        best = max(everyone, key=lambda r: r["fitness"])
        print(json.dumps({"event": "batch", "evals": len(everyone) - 1, "gen": gen, "best_fitness": round(best["fitness"], 4),
                          "gen_best": round(max(fits), 4), "minutes": round((time.time() - t0) / 60, 1)}), flush=True)
    pool.close()
    top = sorted(everyone[1:], key=lambda r: -r["fitness"])
    # Spread the shortlist: skip candidates nearly identical in fitness to one already kept.
    keep = []
    for r in top:
        if all(abs(r["fitness"] - q["fitness"]) > 0.002 for q in keep):
            keep.append(r)
        if len(keep) == 8:
            break
    (out / "archive.json").write_text(json.dumps(keep, indent=1))
    print(json.dumps({"event": "done", "evals": len(everyone) - 1, "base": round(b0["fitness"], 4),
                      "top": [{"fitness": round(r["fitness"], 4), "recipe": r["recipe"]} for r in keep[:3]]})[:1500],
          flush=True)


if __name__ == "__main__":
    main()
