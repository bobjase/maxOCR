"""Exploratory test of levers outside rung 0's rules, applied on top of the rung-0 result.

1. digit-form = old-style (short 0, descending 5): a built-in Iosevka variant that crosses
   clusters and may fail R2b (ink area) because the 0 becomes shorter.
2. Fork grid (iosevka/maxocr-params.patch): zero inset x capital-O outset, the survey's strongest
   0/O lever (O wider than 0). Widening the O exceeds the rung-0 R2a ink-box tolerance by design.

Every candidate is evaluated even when it violates R2a/R2b; violations are reported, not enforced.
Nothing here enters the rung-0 elite. Results decide whether the spec rules should change.

    python scripts/explore_levers.py
Writes out/report/explore_levers.csv and prints a table.
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.build import WORK, BuildPool, cand_id, plan_text  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from maxocr.invariants import check, tolerance_cell  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FORK = WORK / "iosevka-fork"
OUTF = WORK / "explore"
INSETS = [0, 20, 40, 60]
OUTSETS = [0, 15, 30, 45]


def fork_build(name: str, overrides: dict, inset: int, outset: int) -> Path:
    out = OUTF / f"{name}.ttf"
    if out.exists():
        return out
    params = FORK / "params" / "parameters.toml"
    text = params.read_text()
    text = re.sub(r"^maxocrZeroInset = .*$", f"maxocrZeroInset = {inset}", text, flags=re.M)
    text = re.sub(r"^maxocrOOutset = .*$", f"maxocrOOutset = {outset}", text, flags=re.M)
    params.write_text(text)
    (FORK / "private-build-plans.toml").unlink(missing_ok=True)
    (FORK / "private-build-plans.toml").write_text(plan_text(overrides))
    r = subprocess.run(["npm", "run", "build", "--", "ttf-unhinted::MaxOCRCand"], cwd=FORK, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stdout[-1500:] + r.stderr[-1500:])
    shutil.copy(FORK / "dist" / "MaxOCRCand" / "TTF-Unhinted" / "MaxOCRCand-Regular.ttf", out)
    return out


def pair_confusion(chars: pd.DataFrame, engine: str, a: str = "0", b: str = "O") -> float:
    g = chars[(chars.engine == engine) & ~chars.cropped]
    x, y = g[g.truth == a], g[g.truth == b]
    return float(((x.pred == b).sum() + (y.pred == a).sum()) / max(len(x) + len(y), 1))


def main():
    OUTF.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(rung0.OUT / "run.db")
    final = con.execute("SELECT value FROM state WHERE key='final'").fetchone()
    elite = json.loads(final[0])["elite"] if final else json.loads(
        (con.execute("SELECT value FROM state WHERE key='elite'").fetchone() or ["{}"])[0])
    parent = con.execute("SELECT font FROM cand WHERE id=?", (cand_id({}),)).fetchone()[0]
    tol = {c: tuple(v) for c, v in json.loads((rung0.OUT / "tolerance.json").read_text()).items()}
    print("rung-0 elite:", elite, flush=True)

    pool = BuildPool(1, WORK / "rung0" / "fonts")
    fonts = {"rung0": pool.build_many([(elite, 400)])[0][0],
             "rung0+oldstyle": pool.build_many([({**elite, "digit-form": "old-style"}, 400)])[0][0]}
    for i in INSETS:
        for o in OUTSETS:
            if i or o:
                fonts[f"rung0+zero{i}+O{o}"] = fork_build(f"{cand_id(elite)}_z{i}_o{o}", elite, i, o)
    fonts[f"rung0+oldstyle+zero40+O30"] = fork_build(f"{cand_id(elite)}_os_z40_o30",
                                                    {**elite, "digit-form": "old-style"}, 40, 30)
    print(f"{len(fonts)} fonts built", flush=True)

    paddle = rung0.PaddleRec()
    rows = []
    for bank_name in ("opt", "val"):
        insts = rung0.bank(bank_name)
        jobs = [Job(name, str(path), rung0.SEVERITY, "a", c) for name, path in fonts.items() for c in chunk(insts, 50)]
        chars, _, classes = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False)
        for name, g in chars.groupby("font"):
            m = rung0.metrics(g, classes)
            rows.append({"candidate": name, "bank": bank_name, "objective": round(m["objective"], 3),
                         "paddle_within_obj_pct": round(100 * m["within_obj"], 2),
                         "tess_within_gate_pct": round(100 * m["tess_k"] / max(m["tess_n"], 1), 2),
                         "paddle_0O_pct": round(100 * pair_confusion(g, "paddle"), 2),
                         "tess_0O_pct": round(100 * pair_confusion(g, "tesseract"), 2)})
        print(f"{bank_name} bank done", flush=True)
    df = pd.DataFrame(rows)
    df["r2c"] = df.candidate.map({n: "; ".join(check(str(p), parent, tol)[:3]) or "ok" for n, p in fonts.items()})
    cell = tolerance_cell(tol, parent)
    df["r2c_cell_rule"] = df.candidate.map({n: "; ".join(check(str(p), parent, cell)[:3]) or "ok"
                                            for n, p in fonts.items()})
    df.to_csv(ROOT / "out" / "report" / "explore_levers.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_colwidth", 80):
        print(df[df.bank == "val"].sort_values("paddle_within_obj_pct").to_string(index=False))
        print()
        print(df[df.bank == "opt"].sort_values("paddle_within_obj_pct").to_string(index=False))


if __name__ == "__main__":
    main()
