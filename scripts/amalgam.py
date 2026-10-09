"""First amalgam experiment: fonts assembled per character from the OFL ingredient pool.

Ingredient quality per character comes from the OFL survey (out/survey_ofl): for each face and
character, the error rate of that character (both engines, clean and s=0.5, suite a, uncropped).
Within one style (serif or sans; blends across styles produce partial-serif debris):
  best1:  every character taken whole from its best face (no blending)
  top3:   every character blended from its 3 best faces, weights proportional to 1 / (error + eps)
Each candidate is scored with the rung-0 objective and metrics on the optimization and validation
banks, next to the best single OFL faces of each style.

    python scripts/amalgam.py
Writes fonts to ~/maxocr-work/amalgam/ and out/report/amalgam.csv.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.blend import CharRecipe, Ingredient, Recipe, build_font  # noqa: E402
from maxocr.build import WORK  # noqa: E402
from maxocr.corpus import PRIMARY_ALPHABET  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTF = WORK / "amalgam"
SERIF = {"gelasio", "ebgaramond", "crimsonpro", "sourceserif4", "literata", "lora", "merriweather",
         "librebaskerville", "ptserif", "notoserif", "spectral", "alegreya", "cormorantgaramond", "vollkorn",
         "bitter", "caladea", "tinos", "ibmplexserif"}
SANS = {"robotoflex", "roboto", "opensans", "firasans", "sourcesans3", "inter", "worksans", "carlito", "arimo",
        "lato", "publicsans", "ibmplexsans", "atkinsonhyperlegible", "andika", "lexend"}
EPS = 0.005


def char_errors() -> pd.DataFrame:
    chars = pd.concat(pd.read_parquet(p) for p in glob.glob(str(ROOT / "out" / "survey_ofl" / "batch_*_chars.parquet")))
    chars = chars[(chars.suite == "a") & ~chars.cropped]
    return chars.assign(err=chars.pred != chars.truth).groupby(["face", "truth"]).err.mean().unstack("truth")


def pair_confusion(g: pd.DataFrame, engine: str, a="0", b="O") -> float:
    g = g[(g.engine == engine) & ~g.cropped]
    x, y = g[g.truth == a], g[g.truth == b]
    return float(((x.pred == b).sum() + (y.pred == a).sum()) / max(len(x) + len(y), 1))


def main():
    OUTF.mkdir(parents=True, exist_ok=True)
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    err = char_errors()
    fonts = {}
    for style, pool in (("serif", SERIF), ("sans", SANS)):
        e = err.loc[[f for f in err.index if f in pool]]
        overall = e.mean(axis=1).sort_values()
        fonts[f"{style}: best single ({overall.index[0]})"] = path_of[overall.index[0]]
        best1, top3 = {}, {}
        for c in PRIMARY_ALPHABET:
            ranked = e[c].sort_values()
            best1[c] = CharRecipe([Ingredient(path_of[ranked.index[0]], 1.0)])
            top = ranked.head(3)
            top3[c] = CharRecipe([Ingredient(path_of[f], 1 / (v + EPS)) for f, v in top.items()])
        for kind, rec in (("best1", best1), ("top3", top3)):
            p = OUTF / f"{style}_{kind}.ttf"
            build_font(Recipe(rec, name=f"MaxOCR {style} {kind}"), str(p))
            fonts[f"{style}: amalgam {kind}"] = str(p)
        print(style, "per-character best faces:", {c: e[c].idxmin() for c in "0O85S1IB"}, flush=True)
    for name in ("Source Code Pro", "IBM Plex Mono"):
        from maxocr.fonts import BASELINES
        fonts[f"baseline: {name}"] = str(BASELINES[name])
    con = rung0.db()
    final = con.execute("SELECT value FROM state WHERE key='elite'").fetchone()
    if final:
        from maxocr.build import cand_id
        r = con.execute("SELECT font FROM cand WHERE id=?", (cand_id(json.loads(final[0])),)).fetchone()
        if r:
            fonts["Iosevka rung-0 elite (so far)"] = r[0]

    paddle = rung0.PaddleRec()
    rows = []
    for bank_name in ("opt", "val"):
        insts = rung0.bank(bank_name)
        jobs = [Job(n, p, rung0.SEVERITY, "a", c) for n, p in fonts.items() for c in chunk(insts, 50)]
        chars, _, classes = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False)
        for n, g in chars.groupby("font"):
            m = rung0.metrics(g, classes)
            rows.append({"font": n, "bank": bank_name, "objective": round(m["objective"], 3),
                         "paddle_within_obj_pct": round(100 * m["within_obj"], 2),
                         "tess_within_gate_pct": round(100 * m["tess_k"] / max(m["tess_n"], 1), 2),
                         "paddle_0O_pct": round(100 * pair_confusion(g, "paddle"), 2),
                         "tess_0O_pct": round(100 * pair_confusion(g, "tesseract"), 2),
                         "char_error_pct": round(100 * float((g[~g.cropped].pred != g[~g.cropped].truth).mean()), 2)})
        print(f"{bank_name} done", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / "amalgam.csv", index=False)
    with pd.option_context("display.width", 220):
        print(df[df.bank == "val"].sort_values("paddle_within_obj_pct").to_string(index=False))


if __name__ == "__main__":
    main()
