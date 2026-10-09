"""Amalgam rung 2: CMA-ES over per-glyph blend weights and geometry for one objective cluster.

Start (P0): the serif top-3 amalgam. Per optimized character: softmax weights over its K best serif
ingredients, width scale, height scale, baseline shift, and stroke-weight offset (9 numbers).
Every other character keeps its P0 recipe. CMA-ES minimizes -objective (rung-0 objective: hinged
PaddleOCR in-cluster margin) on the optimization bank, common random numbers for the population.

The elite changes only when a generation's best (1) beats the elite on the same lines (paired
one-sided t-test, p < 0.05), (2) is not significantly worse on Tesseract within-gate substitution
on suites (a) and (b), and (3) has no character significantly worse than P0 on the clean bank
(both engines, both suites, Fisher exact p < 0.01).

    python scripts/amalgam_opt.py [--cluster 08BDEOQ] [--generations 25] [--popsize 16]
Writes out/amalgam_opt/<cluster>/log.jsonl, elite.json and fonts to ~/maxocr-work/amalgam_opt/.
"""
import argparse
import json
import sys
import time
from multiprocessing import get_context
from pathlib import Path

import cma
import numpy as np
from scipy.stats import fisher_exact, ttest_rel

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from amalgam import SERIF, char_errors  # noqa: E402
from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font  # noqa: E402
from maxocr.build import WORK  # noqa: E402
from maxocr.corpus import PRIMARY_ALPHABET  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
K = 5
EPS = 0.005
N_PER_CHAR = K + 4
BOUNDS = {"logw": (-0.25, 0.25), "logh": (-0.30, 0.10), "shift": (-0.30, 0.05), "bold": (-4.0, 4.0)}


def ingredients(err, path_of) -> dict[str, list[tuple[str, float]]]:
    e = err.loc[[f for f in err.index if f in SERIF]]
    return {c: [(path_of[f], float(v)) for f, v in e[c].sort_values().head(K).items()] for c in PRIMARY_ALPHABET}


def base_recipe(ing) -> dict[str, CharRecipe]:
    return {c: CharRecipe([Ingredient(p, 1 / (v + EPS)) for p, v in ing[c][:3]]) for c in PRIMARY_ALPHABET}


def x0_for(block, ing) -> np.ndarray:
    x = []
    for c in block:
        w = [1 / (v + EPS) for _, v in ing[c][:3]] + [0.0] * (K - 3)
        w = np.array(w) / sum(w)
        x += list(np.log(np.maximum(w, 0.02))) + [0.0, 0.0, 0.0, 0.0]
    return np.array(x)


def stds_for(block) -> list[float]:
    """Per-coordinate step scales: blend logits, log width, log height, baseline shift, boldness."""
    return ([1.0] * K + [0.08, 0.08, 0.05, 1.0]) * len(block)


def decode(x, block, ing, base) -> dict[str, CharRecipe]:
    rec = dict(base)
    for j, c in enumerate(block):
        v = x[j * N_PER_CHAR:(j + 1) * N_PER_CHAR]
        w = np.exp(v[:K] - v[:K].max())
        w = w / w.sum()
        rec[c] = CharRecipe([Ingredient(p, float(wi)) for (p, _), wi in zip(ing[c], w) if wi > 0.01],
                            width_scale=float(np.exp(np.clip(v[K], *BOUNDS["logw"]))),
                            height_scale=float(np.exp(np.clip(v[K + 1], *BOUNDS["logh"]))),
                            bottom_shift=float(np.clip(v[K + 2], *BOUNDS["shift"])),
                            boldness=float(np.clip(v[K + 3], *BOUNDS["bold"])))
    return rec


def describe(rec: CharRecipe) -> dict:
    return {"ingredients": {Path(i.font).parent.name: round(i.weight, 3) for i in rec.ingredients},
            "width": round(rec.width_scale, 3), "height": round(rec.height_scale, 3),
            "shift": round(rec.bottom_shift, 3), "bold": round(rec.boldness, 2)}


def _build(args):
    rec, path = args
    build_font(Recipe(rec, name="MaxOCR amalgam candidate"), path)
    return path


def score(fonts: dict[str, str], bank, suite, paddle) -> dict[str, dict]:
    jobs = [Job(n, p, rung0.SEVERITY, suite, c) for n, p in fonts.items() for c in chunk(bank, 50)]
    chars, _, classes = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False)
    out = {}
    for n, g in chars.groupby("font"):
        # Margin against the strongest rival of ANY class (closes R27's cluster-only loophole).
        m = rung0.metrics(g, classes, any_class=True)
        m["per_line"] = json.loads(m["per_line"])
        out[n] = m
    return out


def clean_acc(fonts: dict[str, str], bank, paddle) -> dict[str, dict]:
    jobs = [Job(n, p, -1.0, s, c, clean=True) for n, p in fonts.items() for s in "ab" for c in chunk(bank, 50)]
    chars, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False)
    return {n: {k: (int((x.pred == x.truth).sum()), len(x)) for k, x in g.groupby(["engine", "suite", "truth"])}
            for n, g in chars.groupby("font")}


def paired_p(a: dict, b: dict) -> float:
    keys = sorted(set(a) & set(b))
    x, y = np.array([a[k] for k in keys]), np.array([b[k] for k in keys])
    return 1.0 if np.allclose(x, y) else float(ttest_rel(x, y, alternative="greater").pvalue)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster", default=None, help="objective cluster (members concatenated); default the one with 0")
    ap.add_argument("--generations", type=int, default=25)
    ap.add_argument("--popsize", type=int, default=16)
    a = ap.parse_args()
    objective = rung0.OBJECTIVE
    block = next(g for g in objective if (a.cluster and "".join(g) == a.cluster) or (not a.cluster and "0" in g))
    name = "".join(block)
    out = ROOT / "out" / "amalgam_opt" / name
    out.mkdir(parents=True, exist_ok=True)
    fdir = WORK / "amalgam_opt" / name
    fdir.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.jsonl", "a")

    def log(event, **kw):
        line = json.dumps({"t": round(time.time()), "event": event, **kw})
        logf.write(line + "\n")
        logf.flush()
        print(line[:400], flush=True)

    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    ing = ingredients(char_errors(), path_of)
    base = base_recipe(ing)
    paddle = rung0.PaddleRec()
    opt_bank, clean_bank = rung0.bank("opt"), rung0.bank("clean")
    pool = get_context("spawn").Pool(8)

    p0 = str(fdir / "P0.ttf")
    build_font(Recipe(base, name="MaxOCR P0"), p0)
    elite_x, elite_path = x0_for(block, ing), p0
    s0 = score({"P0": p0}, opt_bank, "a", paddle)["P0"]
    elite_score = s0
    elite_tess = {"a": (s0["tess_k"], s0["tess_n"]), "b": None}
    p0_clean = clean_acc({"P0": p0}, clean_bank, paddle)["P0"]
    log("start", cluster=name, ingredients={c: [Path(p).parent.name for p, _ in ing[c]] for c in block},
        objective=round(s0["objective"], 4), within_obj=round(s0["within_obj"], 4),
        tess_gate=round(s0["tess_k"] / s0["tess_n"], 4))

    es = cma.CMAEvolutionStrategy(elite_x, 0.5, {"popsize": a.popsize, "CMA_stds": stds_for(block),
                                                "seed": 7, "verbose": -9})
    for gen in range(a.generations):
        xs = es.ask()
        recs = [decode(x, block, ing, base) for x in xs]
        paths = [str(fdir / f"g{gen:02d}_{k:02d}.ttf") for k in range(len(xs))]
        pool.map(_build, list(zip(recs, paths)))
        sc = score({str(k): p for k, p in enumerate(paths)}, opt_bank, "a", paddle)
        objs = [sc[str(k)]["objective"] for k in range(len(xs))]
        es.tell(xs, [-o for o in objs])
        best = int(np.argmax(objs))
        b = sc[str(best)]
        p = paired_p(b["per_line"], elite_score["per_line"])
        entry = {"gen": gen, "best_objective": round(objs[best], 4), "mean_objective": round(float(np.mean(objs)), 4),
                 "elite_objective": round(elite_score["objective"], 4), "p_improve": round(p, 4), "sigma": round(es.sigma, 4)}
        accepted = False
        if p < rung0.ACCEPT_P:
            cand, eli = paths[best], elite_path
            sb = score({"cand": cand, "elite": eli}, opt_bank, "b", paddle)
            gate = {}
            ok = True
            for suite, (c, e) in (("a", (b, elite_score)), ("b", (sb["cand"], sb["elite"]))):
                pw = rung0.worse_rate(c["tess_k"], c["tess_n"], e["tess_k"], e["tess_n"])
                gate[suite] = {"cand": round(c["tess_k"] / c["tess_n"], 4), "elite": round(e["tess_k"] / e["tess_n"], 4),
                               "p": round(pw, 4)}
                ok &= pw >= rung0.GATE_P
            fails = []
            if ok:
                ca = clean_acc({"cand": cand}, clean_bank, paddle)["cand"]
                for key, (k1, n1) in ca.items():
                    k0, n0 = p0_clean.get(key, (0, 0))
                    if n0 and fisher_exact([[k1, n1 - k1], [k0, n0 - k0]], alternative="less").pvalue < rung0.CLEAN_P:
                        fails.append({"engine": key[0], "suite": key[1], "char": key[2],
                                      "cand": round(k1 / n1, 3), "P0": round(k0 / n0, 3)})
                ok = not fails
            entry |= {"gate": gate, "clean_failures": fails[:5], "passed": ok}
            if ok:
                accepted = True
                elite_x, elite_path, elite_score = xs[best], cand, b
                (out / "elite.json").write_text(json.dumps({"gen": gen, "font": cand, "objective": b["objective"],
                                                            "recipe": {c: describe(recs[best][c]) for c in block}}, indent=1))
        log("generation", accepted=accepted, **entry)

    # Validation of the elite against P0 (same bank and metrics as the baseline table).
    v = score({"P0": p0, "elite": elite_path}, rung0.bank("val"), "a", paddle)
    log("validation", P0={"objective": round(v["P0"]["objective"], 4), "within_obj": round(v["P0"]["within_obj"], 4),
                          "tess_gate": round(v["P0"]["tess_k"] / v["P0"]["tess_n"], 4)},
        elite={"objective": round(v["elite"]["objective"], 4), "within_obj": round(v["elite"]["within_obj"], 4),
               "tess_gate": round(v["elite"]["tess_k"] / v["elite"]["tess_n"], 4), "font": elite_path})
    pool.close()


if __name__ == "__main__":
    main()
