"""M2 rung 0 (R32, R35): search Iosevka's built-in variants for the objective-cluster characters.

Per objective cluster: exhaustive over the members' variant combinations when there are at most
EXHAUSTIVE_MAX, otherwise coordinate ascent one character at a time. Greedy across clusters, sweeps
repeated until a full sweep changes nothing (fixed point) or MAX_SWEEPS. Then a joint step sweeps
the weight axis, subject to R2c.

Every candidate:  build -> R2c invariants vs the frozen rung parent (R30a) -> PaddleOCR objective on
the optimization bank (R27: hinged in-cluster log-odds margin, R27b hinge).
A change is accepted when (1) the objective improves over the current elite on the same lines
(paired one-sided t-test over lines, p < ACCEPT_P) and (2) it passes the gate: Tesseract
within-gate-cluster substitution not significantly worse than the elite's on suites (a) and (b)
(R28), and no primary character significantly worse than the parent on the clean bank on either
engine or suite (R29, Fisher exact, p < CLEAN_P).

State lives in out/rung0/run.db (SQLite), so the search resumes where it stopped.

    python scripts/rung0.py [--clusters 1I 5S] [--max-sweeps 5]
"""
import argparse
import itertools
import json
import re
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, norm, ttest_rel

from maxocr.analysis import paddle_margin, within_cluster_rate
from maxocr.build import WORK, BuildPool, cand_id
from maxocr.corpus import PRIMARY_ALPHABET, make_strings
from maxocr.degrade import make_instance
from maxocr.engines.paddle import PaddleRec
from maxocr.evaluate import Job, chunk, run
from maxocr.invariants import check, tolerance

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "rung0"
REPORT = ROOT / "out" / "report"
SEVERITY = 0.5
EXHAUSTIVE_MAX = 200
MAX_COORD_ROUNDS = 3
ACCEPT_P = 0.05
GATE_P = 0.05
CLEAN_P = 0.01
BUILD_WORKERS = 8      # R37b
EVAL_WORKERS = 12      # R37b
WEIGHTS = [360, 380, 400, 420, 440, 460]
BANKS = {"opt": (909, 500, True), "clean": (303, 2000, False), "val": (202, 5000, False)}

CLUSTERS = json.loads((REPORT / "clusters.json").read_text())
OBJECTIVE, GATE = CLUSTERS["objective"], CLUSTERS["gate"]
HINGE = json.loads((REPORT / "hinge.json").read_text())["hinge_by_target"]["1%"]
CHAR_KEY = {"0": "zero", "8": "eight", "B": "capital-b", "D": "capital-d", "E": "capital-e", "Q": "capital-q",
            "6": "six", "G": "capital-g", "L": "capital-l", "H": "capital-h", "M": "capital-m", "N": "capital-n",
            "1": "one", "I": "capital-i", "2": "two", "Z": "capital-z", "5": "five", "S": "capital-s",
            "9": "nine", "A": "capital-a", "U": "capital-u", "W": "capital-w"}


def variant_names() -> dict[str, list[str]]:
    doc = (WORK / "iosevka" / "doc" / "custom-build.md").read_text()
    names: dict[str, list[str]] = {}
    for k, v in re.findall(r"<code>([a-z0-9-]+) = '([a-z0-9-]+)'</code>", doc):
        names.setdefault(k, [])
        if v not in names[k]:
            names[k].append(v)
    return names


VARIANTS = variant_names()


# ---------------------------------------------------------------- state
def db() -> sqlite3.Connection:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(OUT / "run.db")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS cand (id TEXT PRIMARY KEY, overrides TEXT, weight INT, font TEXT,
                                     build_error TEXT, r2c TEXT);
    CREATE TABLE IF NOT EXISTS score (id TEXT, bank TEXT, suite TEXT, objective REAL, within_obj REAL,
                                      n_obj INT, tess_k INT, tess_n INT, per_line TEXT,
                                      PRIMARY KEY (id, bank, suite));
    CREATE TABLE IF NOT EXISTS clean (id TEXT, engine TEXT, suite TEXT, ch TEXT, correct INT, n INT,
                                      PRIMARY KEY (id, engine, suite, ch));
    CREATE TABLE IF NOT EXISTS log (ts REAL, sweep INT, cluster TEXT, event TEXT, detail TEXT);
    CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
    """)
    return con


def log(con, sweep, cluster, event, detail):
    con.execute("INSERT INTO log VALUES (?,?,?,?,?)", (time.time(), sweep, cluster, event, json.dumps(detail)))
    con.commit()
    print(f"[sweep {sweep} {cluster}] {event}: {json.dumps(detail)[:300]}", flush=True)


def get_state(con, key, default):
    r = con.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return json.loads(r[0]) if r else default


def set_state(con, key, value):
    con.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, json.dumps(value)))
    con.commit()


# ---------------------------------------------------------------- banks
def bank(name: str):
    seed, n, weighted = BANKS[name]
    w = None
    if weighted:
        members = {c for g in OBJECTIVE for c in g}
        w = np.array([3.0 if c in members else 1.0 for c in PRIMARY_ALPHABET])
        w = w / w.sum()
    return [make_instance(i, s, seed) for i, s in enumerate(make_strings(n, seed, weights=w))]


# ---------------------------------------------------------------- builds and invariants
def ensure_built(con, pool: BuildPool, specs: list[tuple[dict, int]], parent: str | None, tol) -> list[str]:
    """Build, run R2c, record. Returns ids that built and passed."""
    todo = [(o, w) for o, w in specs
            if con.execute("SELECT 1 FROM cand WHERE id=?", (cand_id(o, w),)).fetchone() is None]
    if todo:
        for (o, w), (path, err) in zip(todo, pool.build_many(todo)):
            r2c = None if err else (check(str(path), parent, tol) if parent else [])
            con.execute("INSERT OR REPLACE INTO cand VALUES (?,?,?,?,?,?)",
                        (cand_id(o, w), json.dumps(o, sort_keys=True), w, str(path), err, json.dumps(r2c)))
        con.commit()
    ok = []
    for o, w in specs:
        err, r2c = con.execute("SELECT build_error, r2c FROM cand WHERE id=?", (cand_id(o, w),)).fetchone()
        if err is None and json.loads(r2c) == []:
            ok.append(cand_id(o, w))
    return list(dict.fromkeys(ok))


# ---------------------------------------------------------------- scoring
def metrics(chars: pd.DataFrame, classes: list[str]) -> dict:
    chars = chars[~chars.cropped]
    members = {c: i for i, g in enumerate(OBJECTIVE) for c in g}
    p = chars[(chars.engine == "paddle") & chars.truth.isin(members)].copy()
    p["margin"] = paddle_margin(p, classes, OBJECTIVE)
    p.loc[p.pred == "", "margin"] = -HINGE          # deletion: counted as an error, worst score
    p["hinged"] = np.minimum(p.margin, HINGE)
    per_line = p.groupby("inst").hinged.mean()
    t = chars[chars.engine == "tesseract"]
    gate_of = {c: i for i, g in enumerate(GATE) for c in g}
    tg = t[t.truth.isin(gate_of)]
    tk = int(((tg.pred != tg.truth) & (tg.pred.map(gate_of) == tg.truth.map(gate_of))).sum())
    return {"objective": float(p.hinged.mean()),
            "within_obj": within_cluster_rate(chars[chars.engine == "paddle"], OBJECTIVE),
            "n_obj": len(p), "tess_k": tk, "tess_n": len(tg),
            "per_line": json.dumps({int(k): round(float(v), 4) for k, v in per_line.items()})}


def score(con, ids: list[str], bank_name: str, suite: str, paddle, insts) -> None:
    todo = [i for i in ids if con.execute("SELECT 1 FROM score WHERE id=? AND bank=? AND suite=?",
                                          (i, bank_name, suite)).fetchone() is None]
    for group in [todo[k:k + 40] for k in range(0, len(todo), 40)]:   # bound memory per run() call
        fonts = {i: con.execute("SELECT font FROM cand WHERE id=?", (i,)).fetchone()[0] for i in group}
        jobs = [Job(i, fonts[i], SEVERITY, suite, c) for i in group for c in chunk(insts, 50)]
        chars, _, classes = run(jobs, EVAL_WORKERS, paddle=paddle, progress=False)
        for i, g in chars.groupby("font"):
            m = metrics(g, classes)
            con.execute("INSERT OR REPLACE INTO score VALUES (?,?,?,?,?,?,?,?,?)",
                        (i, bank_name, suite, m["objective"], m["within_obj"], m["n_obj"],
                         m["tess_k"], m["tess_n"], m["per_line"]))
        con.commit()


def clean_score(con, ids: list[str], paddle, insts) -> None:
    todo = [i for i in ids if con.execute("SELECT 1 FROM clean WHERE id=?", (i,)).fetchone() is None]
    if not todo:
        return
    fonts = {i: con.execute("SELECT font FROM cand WHERE id=?", (i,)).fetchone()[0] for i in todo}
    jobs = [Job(i, fonts[i], -1.0, s, c, clean=True) for i in todo for s in "ab" for c in chunk(insts, 50)]
    chars, _, _ = run(jobs, EVAL_WORKERS, paddle=paddle, progress=False)
    for (i, e, s, ch), g in chars.groupby(["font", "engine", "suite", "truth"]):
        con.execute("INSERT OR REPLACE INTO clean VALUES (?,?,?,?,?,?)",
                    (i, e, s, ch, int((g.pred == g.truth).sum()), len(g)))
    con.commit()


def get_score(con, i, bank_name="opt", suite="a") -> dict:
    r = con.execute("SELECT objective, within_obj, n_obj, tess_k, tess_n, per_line FROM score "
                    "WHERE id=? AND bank=? AND suite=?", (i, bank_name, suite)).fetchone()
    return dict(zip(["objective", "within_obj", "n_obj", "tess_k", "tess_n", "per_line"], r))


# ---------------------------------------------------------------- acceptance
def improves(con, cand: str, elite: str) -> tuple[bool, float]:
    a = json.loads(get_score(con, cand)["per_line"])
    b = json.loads(get_score(con, elite)["per_line"])
    keys = sorted(set(a) & set(b))
    if len(keys) < 10:
        return False, 1.0
    x, y = np.array([a[k] for k in keys]), np.array([b[k] for k in keys])
    if np.allclose(x, y):
        return False, 1.0
    p = ttest_rel(x, y, alternative="greater").pvalue
    return bool(p < ACCEPT_P), float(p)


def worse_rate(k1, n1, k0, n0) -> float:
    """One-sided two-proportion z-test p-value that rate 1 > rate 0."""
    if n1 == 0 or n0 == 0:
        return 1.0
    p = (k1 + k0) / (n1 + n0)
    se = np.sqrt(max(p * (1 - p) * (1 / n1 + 1 / n0), 1e-12))
    return float(norm.sf((k1 / n1 - k0 / n0) / se))


def gate(con, cand: str, elite: str, parent: str, paddle, banks) -> tuple[bool, dict]:
    score(con, [cand, elite], "opt", "b", paddle, banks["opt"])
    detail = {}
    for suite in "ab":
        c, e = get_score(con, cand, suite=suite), get_score(con, elite, suite=suite)
        p = worse_rate(c["tess_k"], c["tess_n"], e["tess_k"], e["tess_n"])
        detail[f"tess_{suite}"] = {"cand": round(c["tess_k"] / max(c["tess_n"], 1), 4),
                                   "elite": round(e["tess_k"] / max(e["tess_n"], 1), 4), "p": round(p, 4)}
        if p < GATE_P:
            return False, detail
    clean_score(con, [cand, parent], paddle, banks["clean"])
    worst = []
    for e, s, ch, k1, n1 in con.execute("SELECT engine, suite, ch, correct, n FROM clean WHERE id=?", (cand,)):
        k0, n0 = con.execute("SELECT correct, n FROM clean WHERE id=? AND engine=? AND suite=? AND ch=?",
                             (parent, e, s, ch)).fetchone()
        p = fisher_exact([[k1, n1 - k1], [k0, n0 - k0]], alternative="less").pvalue
        if p < CLEAN_P:
            worst.append({"engine": e, "suite": s, "char": ch, "cand_acc": round(k1 / n1, 3),
                          "parent_acc": round(k0 / n0, 3), "p": round(float(p), 5)})
    detail["clean_failures"] = worst
    return not worst, detail


# ---------------------------------------------------------------- search
def cluster_moves(cluster: list[str], elite: dict) -> tuple[list[dict], bool]:
    """Candidate override dicts for one cluster round, and whether the round is exhaustive.
    Exhaustive: every combination of the members' variants. Otherwise (coordinate ascent) each
    candidate changes one member character."""
    keys = [CHAR_KEY[c] for c in cluster if VARIANTS.get(CHAR_KEY.get(c, ""), [])]
    if int(np.prod([len(VARIANTS[k]) for k in keys])) <= EXHAUSTIVE_MAX:
        combos = itertools.product(*[VARIANTS[k] for k in keys])
        return [{**elite, **dict(zip(keys, combo))} for combo in combos], True
    return [{**elite, k: v} for k in keys for v in VARIANTS[k]], False


def search_cluster(con, pool, cluster, elite, sweep, parent_id, parent_path, tol, paddle, banks) -> dict:
    name = "".join(cluster)
    for rnd in range(MAX_COORD_ROUNDS):
        moves, exhaustive = cluster_moves(cluster, elite)
        specs = [(m, 400) for m in moves] + [(elite, 400)]
        ok = ensure_built(con, pool, specs, parent_path, tol)
        elite_id = cand_id(elite)
        rejected = len({cand_id(m) for m in moves} - set(ok))
        score(con, ok, "opt", "a", paddle, banks["opt"])
        ranked = sorted(ok, key=lambda i: -get_score(con, i)["objective"])
        e = get_score(con, elite_id)
        log(con, sweep, name, "round", {"round": rnd, "candidates": len(moves), "r2c_rejected": rejected,
                                        "elite_objective": round(e["objective"], 4),
                                        "best_objective": round(get_score(con, ranked[0])["objective"], 4)})
        accepted = None
        for cid in [i for i in ranked if i != elite_id][:3]:
            better, p = improves(con, cid, elite_id)
            if not better:
                break                    # ranked by objective: later ones will not pass either
            passed, detail = gate(con, cid, elite_id, parent_id, paddle, banks)
            o = json.loads(con.execute("SELECT overrides FROM cand WHERE id=?", (cid,)).fetchone()[0])
            log(con, sweep, name, "gate", {"cand": cid, "overrides": {k: v for k, v in o.items() if k not in elite
                                           or elite[k] != v}, "p_improve": round(p, 4), "passed": passed, **detail})
            if passed:
                accepted = o
                break
        if accepted is None:
            break
        elite = accepted
        set_state(con, "elite", elite)
        log(con, sweep, name, "accepted", {"elite": elite, "objective": round(get_score(con, cand_id(elite))["objective"], 4)})
        if exhaustive:
            break
    return elite


def validate(con, ids, paddle, banks, sweep, label):
    score(con, ids, "val", "a", paddle, banks["val"])
    for i in ids:
        s = get_score(con, i, "val", "a")
        log(con, sweep, label, "validation", {"id": i, "objective": round(s["objective"], 4),
                                              "within_obj": round(s["within_obj"], 4),
                                              "tess_gate": round(s["tess_k"] / max(s["tess_n"], 1), 4)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clusters", nargs="*", help="cluster names (members concatenated), default all")
    ap.add_argument("--max-sweeps", type=int, default=5)
    ap.add_argument("--skip-joint", action="store_true")
    a = ap.parse_args()
    con = db()
    pool = BuildPool(BUILD_WORKERS, WORK / "rung0" / "fonts")
    paddle = PaddleRec()
    banks = {k: bank(k) for k in BANKS}

    # Rung parent (R30a): Iosevka defaults built through the same pipeline.
    ensure_built(con, pool, [({}, 400)], None, None)
    parent_id = cand_id({})
    parent_path = con.execute("SELECT font FROM cand WHERE id=?", (parent_id,)).fetchone()[0]

    clusters = [g for g in OBJECTIVE if not a.clusters or "".join(g) in a.clusters]

    # R2a tolerance from the full rung-0 variant set: every single-cluster move relative to the parent.
    tol_file = OUT / "tolerance.json"
    if tol_file.exists():
        tol = {c: tuple(v) for c, v in json.loads(tol_file.read_text()).items()}
    else:
        specs = [(m, 400) for g in OBJECTIVE for m in cluster_moves(g, {})[0]]
        print(f"pre-building {len(specs)} rung-0 variants for the R2a tolerance", flush=True)
        built = ensure_built(con, pool, specs, None, None)
        paths = [con.execute("SELECT font FROM cand WHERE id=?", (i,)).fetchone()[0] for i in built]
        tol = tolerance(paths + [parent_path])
        tol_file.write_text(json.dumps({c: list(map(float, v)) for c, v in tol.items()}))
        # Re-check every candidate on record against the (new) tolerance, not only the pre-built set:
        # a restart after a tolerance change must not keep stale verdicts.
        for i, path in con.execute("SELECT id, font FROM cand WHERE build_error IS NULL").fetchall():
            con.execute("UPDATE cand SET r2c=? WHERE id=?", (json.dumps(check(path, parent_path, tol)), i))
        con.commit()
        n_bad = con.execute("SELECT COUNT(*) FROM cand WHERE r2c != '[]'").fetchone()[0]
        log(con, 0, "-", "tolerance", {"variants": len(built), "r2c_rejected": n_bad})

    elite = get_state(con, "elite", {})
    start = get_state(con, "sweep", 1)
    validate(con, [parent_id], paddle, banks, 0, "parent")
    for sweep in range(start, a.max_sweeps + 1):
        before = dict(elite)
        for g in clusters:
            elite = search_cluster(con, pool, g, elite, sweep, parent_id, parent_path, tol, paddle, banks)
        set_state(con, "sweep", sweep + 1)
        validate(con, [cand_id(elite)], paddle, banks, sweep, "elite")
        if elite == before:
            log(con, sweep, "-", "fixed point", {"elite": elite})
            break

    if not a.skip_joint:
        specs = [(elite, w) for w in WEIGHTS]
        ok = ensure_built(con, pool, specs, parent_path, tol)
        score(con, ok, "opt", "a", paddle, banks["opt"])
        best = max(ok, key=lambda i: get_score(con, i)["objective"])
        validate(con, sorted(set(ok)), paddle, banks, 99, "joint")
        w = con.execute("SELECT weight FROM cand WHERE id=?", (best,)).fetchone()[0]
        set_state(con, "final", {"elite": elite, "weight": w, "id": best})
        log(con, 99, "-", "final", {"elite": elite, "weight": w, "id": best,
                                    "rejected_weights": [x for x in WEIGHTS if cand_id(elite, x) not in ok]})


if __name__ == "__main__":
    main()
