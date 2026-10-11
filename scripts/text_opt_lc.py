"""Readable-glyph search for the basic-Latin phase (case-sensitive): CMA-ES over real-font blends.

Like text_opt.py (each optimized glyph is an SDF blend of real fonts with tight size and weight bounds, so it
stays crisp and in style), but scored case-sensitively on random 0-9A-Za-z lines that oversample the pair:
PaddleOCR, EasyOCR and Tesseract restricted to 0-9A-Za-z (no case folding); PARSeq stays held out.
Fitness = mean over engines of the pair glyphs' correct-read rates - 2 x any rise in overall character
error above the base font - REGRESS x any drop of a pair glyph's accuracy below the base (per engine).

    python scripts/text_opt_lc.py --pair Il --only l --base FONT.ttf --run Il_lc [--generations 30]
--only: the glyphs that change (default: both); the other pair glyph is held fixed but still scored.
Writes out/discover/<run>/{log.jsonl,archive.json}; fonts in ~/maxocr-work/discover/<run>/.
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
import rung0  # noqa: E402
from add_lowercase import add_glyphs  # noqa: E402
from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font  # noqa: E402
from maxocr.build import WORK  # noqa: E402
from maxocr.corpus import ALNUM_ALPHABET, make_strings  # noqa: E402
from maxocr.degrade import make_instance  # noqa: E402
from maxocr.engines.easyocr_rec import EasyOCRRec  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INGREDIENTS = ("ibmplexserif", "spectral", "gelasio", "notoserif", "sourceserif4", "courierprime")
K = len(INGREDIENTS)
N_PER = K + 4
BOUNDS = {"logw": (-0.10, 0.10), "logh": (-0.06, 0.04), "shift": (-0.04, 0.02), "bold": (-1.5, 1.5)}
ENGINES = ("paddle", "tesseract", "easyocr")
REGRESS = 1.0


def decode(x, chars, paths) -> dict[str, CharRecipe]:
    rec = {}
    for j, c in enumerate(chars):
        v = x[j * N_PER:(j + 1) * N_PER]
        w = np.exp(v[:K] - v[:K].max())
        w = w / w.sum()
        rec[c] = CharRecipe([Ingredient(p, float(wi)) for p, wi in zip(paths, w) if wi > 0.01],
                            width_scale=float(np.exp(np.clip(v[K], *BOUNDS["logw"]))),
                            height_scale=float(np.exp(np.clip(v[K + 1], *BOUNDS["logh"]))),
                            bottom_shift=float(np.clip(v[K + 2], *BOUNDS["shift"])),
                            boldness=float(np.clip(v[K + 3], *BOUNDS["bold"])))
    return rec


def _build(args):
    rec, base, chars, path = args
    tmp = path.replace(".ttf", "_blend.ttf")
    build_font(Recipe(rec, name="MaxOCR lc candidate"), tmp)
    add_glyphs(base, tmp, chars, path)
    return path


def bank(pair: str, n: int = 400, seed: int = 6161):
    w = np.array([8.0 if c in pair else 1.0 for c in ALNUM_ALPHABET])
    texts = make_strings(n, seed, alphabet=ALNUM_ALPHABET, weights=w / w.sum())
    return [i for i in (make_instance(k, s, seed) for k, s in enumerate(texts)) if not i.cropped]


def score(chars, pair, base=None) -> dict:
    out = {}
    for e in ENGINES:
        g = chars[chars.engine == e]
        acc = {t: float((g[g.truth == t].pred == t).mean()) for t in pair}
        out[e] = {"acc": acc, "err": float((g.pred != g.truth).mean())}
    fit = float(np.mean([np.mean(list(out[e]["acc"].values())) for e in ENGINES]))
    if base is not None:
        fit -= 2.0 * float(np.mean([max(0.0, out[e]["err"] - base[e]["err"]) for e in ENGINES]))
        fit -= REGRESS * float(np.mean([max(0.0, base[e]["acc"][t] - out[e]["acc"][t]) for e in ENGINES for t in pair]))
    out["fitness"] = fit
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True)
    ap.add_argument("--only", help="glyphs that change (default: the whole pair)")
    ap.add_argument("--base", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--generations", type=int, default=30)
    ap.add_argument("--popsize", type=int, default=16)
    a = ap.parse_args()
    pair, chars = a.pair, a.only or a.pair
    out = ROOT / "out" / "discover" / a.run
    out.mkdir(parents=True, exist_ok=True)
    fdir = WORK / "discover" / a.run
    fdir.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.jsonl", "w")
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    paths = [path_of[f] for f in INGREDIENTS]
    paddle, easy = rung0.PaddleRec(alphabet=ALNUM_ALPHABET), EasyOCRRec(alphabet=ALNUM_ALPHABET)
    b = bank(pair)
    pool = get_context("spawn").Pool(8)
    t0 = time.time()

    def evaluate(fonts: dict[str, str], base=None) -> dict:
        jobs = [Job(p, p, rung0.SEVERITY, "a", c) for p in fonts.values() for c in chunk(b, 40)]
        ch, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_whitelist=ALNUM_ALPHABET)
        return {n: score(ch[ch.font == p], pair, base) for n, p in fonts.items()}

    base = evaluate({"base": a.base})["base"]
    everyone = []
    print(json.dumps({"event": "seeded", "base": round(base["fitness"], 4),
                      "base_acc": {e: base[e]["acc"] for e in ENGINES}}), flush=True)
    x0 = np.array(([np.log(1 / 3)] * 3 + [np.log(0.02)] * (K - 3) + [0.0, 0.0, 0.0, 0.0]) * len(chars))
    es = cma.CMAEvolutionStrategy(x0, 0.5, {"popsize": a.popsize, "seed": 13, "verbose": -9,
                                           "CMA_stds": ([1.0] * K + [0.04, 0.03, 0.02, 0.6]) * len(chars)})
    for gen in range(a.generations):
        xs = es.ask()
        recs = [decode(x, chars, paths) for x in xs]
        fps = [str(fdir / f"g{gen:02d}_{k:02d}.ttf") for k in range(len(xs))]
        pool.map(_build, [(r, a.base, chars, p) for r, p in zip(recs, fps)])
        sc = evaluate({str(k): p for k, p in enumerate(fps)}, base)
        fits = [sc[str(k)]["fitness"] for k in range(len(xs))]
        es.tell(xs, [-f for f in fits])
        for k, p in enumerate(fps):
            rec = {c: {"ingredients": {Path(i.font).parent.name: round(i.weight, 3) for i in recs[k][c].ingredients},
                       "width": round(recs[k][c].width_scale, 3), "height": round(recs[k][c].height_scale, 3),
                       "bold": round(recs[k][c].boldness, 2)} for c in chars}
            everyone.append({"font": p, "fitness": fits[k], "recipe": rec,
                             "acc": {e: sc[str(k)][e]["acc"] for e in ENGINES}})
            logf.write(json.dumps({"gen": gen, "k": k, "fitness": round(fits[k], 4), "recipe": rec}) + "\n")
        logf.flush()
        best = max(everyone, key=lambda r: r["fitness"])
        print(json.dumps({"event": "batch", "gen": gen, "best_fitness": round(best["fitness"], 4),
                          "base": round(base["fitness"], 4), "minutes": round((time.time() - t0) / 60, 1)}), flush=True)
    pool.close()
    keep = []
    for r in sorted(everyone, key=lambda r: -r["fitness"]):
        if all(abs(r["fitness"] - q["fitness"]) > 0.002 for q in keep):
            keep.append(r)
        if len(keep) == 8:
            break
    (out / "archive.json").write_text(json.dumps(keep, indent=1))
    print(json.dumps({"event": "done", "base": round(base["fitness"], 4),
                      "top": [{"fitness": round(r["fitness"], 4), "recipe": r["recipe"]} for r in keep[:3]]})[:1500], flush=True)


if __name__ == "__main__":
    main()
