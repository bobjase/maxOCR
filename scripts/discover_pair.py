"""Discovery for a confusable pair: MAP-Elites over constructive glyph genomes (maxocr/strokes.py).

Both glyphs of the pair (default 0 and O) evolve together; the rest of the font stays at the base
(the optimized amalgam). The archive keeps the best pair in each cell of a 2-D behaviour grid:
  d1 = ink width of the second glyph / ink width of the first (e.g. O / 0)
  d2 = overlap (IoU) of the two glyph masks, aligned at the left edge and baseline (low = more different)
so the search returns qualitatively different solutions, not one optimum.

Fitness (exploratory; uses Tesseract and EasyOCR as well as PaddleOCR, see DECISIONS open question 5):
on the isolation bank at s=0.5, suite (a) (each glyph alone, and among mixed, all-letter and all-digit
neighbours outside its clusters), the mean over the three engines of correct reads in the single,
mixed and adversarial contexts, minus a penalty for any rise in overall character error above the
base font. PARSeq is held out.

    python scripts/discover_pair.py [--pair 0O] [--evals 2000] [--batch 32] [--run NAME]
                                    [--resume out/discover/<run>/archive.pkl] [--short-zero 0.78] [--casefold]
                                    [--base FONT.ttf] [--regress 1.0] [--guard] [--clean]
Writes out/discover/<run>/archive.json, log.jsonl, gallery.png (run defaults to the pair); fonts in
~/maxocr-work/discover/<run>/. --resume adds a previous run's elites to the seeds (re-evaluated);
--short-zero adds a copy of each seed with the digit scaled to that height (old-style figure).
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
from maxocr.strokes import CLEAN_OPS, from_glyph, mutate, primitive, rasterize, with_glyphs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
D1 = np.linspace(0.85, 2.05, 9)       # width-ratio bin edges (8 bins)
D2 = np.linspace(0.10, 0.95, 9)       # IoU bin edges (8 bins)
PAIR_BANK_SEED = 4242
SERIF_SEEDS = ("gelasio", "librebaskerville", "sourceserif4", "spectral", "ptserif", "notoserif", "crimsonpro",
               "lora", "literata", "caladea", "tinos", "ibmplexserif", "merriweather", "vollkorn", "ebgaramond",
               "alegreya")


CONTEXTS = ("single", "mixed", "letters", "digits")


def isolation_bank(targets: str, n_per: int = 30, seed: int = 7373):
    """Absolute recognizability of each target glyph, without a comparison partner (James, 2026-10-08).

    Engines decide 0 vs O largely from context: among letters a 0 is read as O, alone an O is read as
    0. Each target is tested alone, and in the middle of 6 neighbours that are mixed (3 letters + 3
    digits, shuffled: no letter/digit prior, e.g. 4K?TWX7), all letters, or all digits. Neighbours
    never come from the target's own objective or gate clusters, so no comparison partner is present.
    For a digit the adversarial context is letters, for a letter it is digits.
    Returns instances and a dict index -> (target, context, target position)."""
    own = {c for g in rung0.OBJECTIVE + rung0.GATE if set(g) & set(targets) for c in g}
    letters = [c for c in PRIMARY_ALPHABET if c.isalpha() and c not in own]
    digits = [c for c in PRIMARY_ALPHABET if c.isdigit() and c not in own]
    rng = np.random.default_rng(seed)
    texts, info = [], {}
    for t in targets:
        for ctx in CONTEXTS:
            for _ in range(n_per):
                if ctx == "single":
                    s, pos = t, 0
                else:
                    if ctx == "mixed":
                        nb = list(rng.choice(letters, 3)) + list(rng.choice(digits, 3))
                        rng.shuffle(nb)
                    else:
                        nb = list(rng.choice(letters if ctx == "letters" else digits, 6))
                    s, pos = "".join(nb[:3]) + t + "".join(nb[3:]), 3
                info[len(texts)] = (t, ctx, pos)
                texts.append(s)
    return [make_instance(i, s, seed) for i, s in enumerate(texts)], info


def adversarial(t: str) -> str:
    return "letters" if t.isdigit() else "digits"


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
ENGINES = ("paddle", "tesseract", "easyocr")   # optimizing engines; PARSeq stays held out


def fitness(chars, a, b, base_err: dict | None, info: dict, base_per: dict | None = None, regress: float = 0.0,
            strings=None) -> dict:
    """Reward reading each target glyph CORRECTLY on its own (isolation bank): mean accuracy over the
    single, mixed and adversarial contexts (the context that favours the glyph is reported but not
    rewarded). An earlier version rewarded "not read as its twin" and the search turned O into C.
    Penalize any rise in overall character error (neighbours included) above the base font.
    regress > 0: also penalize every rewarded cell (engine x glyph x context) that falls below the base
    font's accuracy, so the search can't buy gains on one glyph with losses on the other (1/I run 1).
    strings (the run's string rows) given: overall error also counts insertions, so marks that an
    engine reads as extra characters cost error (aligned character rows alone never show them)."""
    out = {}
    ctx_of = {i: v[1] for i, v in info.items()}
    pos_of = {i: v[2] for i, v in info.items()}
    for e in ENGINES:
        g = chars[(chars.engine == e) & ~chars.cropped]
        tg = g[g.pos == g.inst.map(pos_of)].assign(ctx=lambda d: d.inst.map(ctx_of))
        per = {}
        for t in (a, b):
            x = tg[tg.truth == t]
            per[t] = {c: float((x[x.ctx == c].pred == t).mean()) for c in CONTEXTS}
        rewarded = [per[t][c] for t in (a, b) for c in ("single", "mixed", adversarial(t))]
        err = float((g.pred != g.truth).mean())
        if strings is not None:
            sg = strings[(strings.engine == e) & ~strings.cropped]
            err = float(((g.pred != g.truth).sum() + sg.n_ins.sum()) / max(len(g), 1))
        out[e] = {"acc": float(np.mean(rewarded)), "per": per, "err": err,
                  "pair": float(np.mean([1 - per[t]["mixed"] for t in (a, b)]))}
    penalty = 0.0 if base_err is None else np.mean([max(0.0, out[e]["err"] - base_err[e]) for e in ENGINES])
    drop = 0.0
    if regress and base_per is not None:
        drop = float(np.mean([max(0.0, base_per[e][t][c] - out[e]["per"][t][c])
                              for e in ENGINES for t in (a, b) for c in ("single", "mixed", adversarial(t))]))
    out["regress"] = drop
    out["fitness"] = float(np.mean([out[e]["acc"] for e in ENGINES]) - ERR_PENALTY * penalty - regress * drop)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="0O")
    ap.add_argument("--evals", type=int, default=2000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--run", help="output name under out/discover and ~/maxocr-work/discover (default: the pair)")
    ap.add_argument("--resume", help="archive.pkl of a previous run: its elites join the seeds")
    ap.add_argument("--short-zero", type=float, help="also seed each pair with the digit at this height")
    ap.add_argument("--clean", action="store_true",
                    help="readable-glyph search: only whole-glyph typographic mutations (strokes.CLEAN_OPS: "
                         "scale, weight, contrast, stress, smoothing) and clean seeds from 16 OFL serif faces")
    ap.add_argument("--guard", action="store_true",
                    help="guard against marks read as extra characters: add Tesseract without a whitelist "
                         "(tesseract_open) as an optimizing engine and count insertions as error")
    ap.add_argument("--regress", type=float, default=0.0,
                    help="weight of the penalty for cells that fall below the base font's accuracy (0 = off)")
    ap.add_argument("--base", help="font the pair is evolved in (default: the optimized amalgam); use the current "
                                   "best font so gains on earlier pairs carry forward")
    ap.add_argument("--casefold", action="store_true",
                    help="engines read the general alphabet (lowercase, punctuation) and fold case; Tesseract keeps its whitelist")
    args = ap.parse_args()
    global ENGINES
    if args.guard:
        ENGINES = ENGINES + ("tesseract_open",)
    from maxocr.corpus import GENERAL_ALPHABET
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=True) if args.casefold else {}
    a, b = args.pair[0], args.pair[1]
    out = ROOT / "out" / "discover" / (args.run or args.pair)
    out.mkdir(parents=True, exist_ok=True)
    fdir = WORK / "discover" / (args.run or args.pair)
    fdir.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.jsonl", "a")
    rng = np.random.default_rng(args.seed)
    base = args.base or json.loads((ROOT / "out" / "amalgam_opt" / "08BDEOQ" / "elite.json").read_text())["font"]
    ofl = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}

    # Seeds: the base font's own pair, pairs from several OFL serif faces, and primitive shapes.
    seeds = [("base", from_glyph(base, a), from_glyph(base, b))]
    fams = SERIF_SEEDS if args.clean else ("gelasio", "librebaskerville", "spectral", "sourceserif4",
                                           "atkinsonhyperlegible", "tinos", "bodonimoda", "playfairdisplay",
                                           "librebodoni")
    for fam in fams:
        if fam in ofl:
            seeds.append((fam, from_glyph(ofl[fam], a), from_glyph(ofl[fam], b)))
    if (a, b) == ("0", "O") and not args.clean:
        seeds.append(("primitives capsule/ellipse", primitive("capsule"), primitive("ellipse")))
        seeds.append(("primitives diamond/ellipse", primitive("diamond"), primitive("ellipse")))
    if args.resume:
        with open(args.resume, "rb") as f:
            prev = pickle.load(f)
        seeds += [(f"{c['origin']} (resumed)", c["ga"], c["gb"]) for c in prev.values()]
    if args.short_zero:
        from feature_transplant import oldstyle
        h = args.short_zero
        digit = 0 if a.isdigit() else 1
        short = []
        for name, ga, gb in seeds:
            g = [ga, gb]
            g[digit] = oldstyle(g[digit], h, 1 - 0.27 * (1 - h))
            short.append((f"{name} short{h:.2f}", *g))
        seeds += short

    bank, info = isolation_bank(a + b)
    paddle = rung0.PaddleRec(**eng)
    from maxocr.engines.easyocr_rec import EasyOCRRec
    easy = EasyOCRRec(**eng) if "easyocr" in ENGINES else None
    archive: dict[tuple[int, int], dict] = {}
    n_eval, k_font, t0 = 0, 0, time.time()
    base_err, base_per = None, None

    def evaluate(cands):
        nonlocal n_eval, k_font
        fonts = {}
        for c in cands:
            p = str(fdir / f"c{k_font:05d}.ttf")
            k_font += 1
            with_glyphs(base, {a: c["ga"], b: c["gb"]}, p)
            c["font"] = p
            fonts[p] = c
        jobs = [Job(p, p, rung0.SEVERITY, "a", ch) for p in fonts for ch in chunk(bank, 48)]
        chars, strings, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy,
                                tess_open=args.guard)
        for p, g in chars.groupby("font"):
            c = fonts[p]
            c["score"] = fitness(g, a, b, base_err, info, base_per, args.regress,
                                 strings[strings.font == p] if args.guard else None)
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
                                   "easy_acc": round(c["score"].get("easyocr", {}).get("acc", float("nan")), 4),
                                   "regress": round(c["score"].get("regress", 0.0), 4),
                                   "topen_acc": round(c["score"].get("tesseract_open", {}).get("acc", float("nan")), 4),
                                   "ratio": round(ratio, 3), "iou": round(iou, 3), "ops": c.get("ops", []),
                                   "origin": c.get("origin"), "new_elite": bool(improved)}) + "\n")
        logf.flush()

    # The base alone first: its overall error is the reference for the error penalty.
    evaluate([{"ga": seeds[0][1], "gb": seeds[0][2], "origin": "base", "ops": []}])
    b0 = next(iter(archive.values()))["score"]
    base_err = {e: b0[e]["err"] for e in ENGINES}
    base_per = {e: b0[e]["per"] for e in ENGINES}
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
                ga, o = mutate(ga, rng, ops=CLEAN_OPS if args.clean else None)
                ops += [f"{a}:{x}" for x in o]
            if which in ("b", "both"):
                gb, o = mutate(gb, rng, ops=CLEAN_OPS if args.clean else None)
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
                          "best_easy_acc": round(best["score"].get("easyocr", {}).get("acc", float("nan")), 4),
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
    for r in [{"font": base, "fitness": None, "origin": "base", "ratio": 0, "iou": 0}] + rows:
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
