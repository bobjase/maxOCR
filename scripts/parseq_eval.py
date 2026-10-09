"""R13/R13b: held-out evaluation on PARSeq (never used for any selection or optimization).

Validation bank, s=0.5, suite (a), every font at Source Code Pro's capital height. Metrics on
uncropped lines: within-objective-cluster substitution, 0/O pair confusion, character error, for all
lengths, length 1 and length 8+ (R20, R13b).

    python scripts/parseq_eval.py
Writes out/report/parseq_eval.csv.
"""
import json
import os
import sys
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from font_survey import matched_size  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.analysis import within_cluster_rate  # noqa: E402
from maxocr.build import cand_id  # noqa: E402
from maxocr.degrade import degrade  # noqa: E402
from maxocr.engines.parseq import REPO, Parseq  # noqa: E402
from maxocr.fonts import BASELINES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.path.expanduser("~/maxocr-work"))


def _imgs(args):
    font, size, insts = args
    import cv2
    cv2.setNumThreads(1)
    return [degrade(font, i, rung0.SEVERITY, size_pt=size, binarize=True) for i in insts]


def fonts_to_test() -> dict[str, str]:
    ofl = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    fonts = {f"baseline: {k}": str(v) for k, v in BASELINES.items()}
    fonts["OFL best single serif: Spectral"] = ofl["spectral"]
    fonts["amalgam P0 (serif top-3)"] = str(WORK / "amalgam" / "serif_top3.ttf")
    fonts["amalgam sans top-3"] = str(WORK / "amalgam" / "sans_top3.ttf")
    elite = ROOT / "out" / "amalgam_opt" / "08BDEOQ" / "elite.json"
    if elite.exists():
        fonts["amalgam optimized (0/O cluster)"] = json.loads(elite.read_text())["font"]
    con = rung0.db()
    e = con.execute("SELECT value FROM state WHERE key='elite'").fetchone()
    if e:
        fonts["Iosevka rung-0 elite"] = con.execute("SELECT font FROM cand WHERE id=?", (cand_id(json.loads(e[0])),)).fetchone()[0]
    return fonts


def main():
    objective = rung0.OBJECTIVE
    fonts = fonts_to_test()
    sizes = {n: matched_size(TTFont(p)) for n, p in fonts.items()}
    insts = rung0.bank("val")
    chunks = [insts[i:i + 250] for i in range(0, len(insts), 250)]
    model = Parseq()
    rows = []
    with get_context("spawn").Pool(16) as pool:
        for n, p in fonts.items():
            imgs = [im for part in pool.map(_imgs, [(p, sizes[n], c) for c in chunks]) for im in part]
            preds = model.read(imgs)
            recs = []
            for inst, pred in zip(insts, preds):
                if inst.cropped:
                    continue
                _, mapping, _ = align(inst.text, pred)
                for i, j in enumerate(mapping):
                    recs.append({"truth": inst.text[i], "pred": pred[j] if j is not None else "", "length": len(inst.text)})
            d = pd.DataFrame(recs)
            for stratum, s in (("all", d), ("len1", d[d.length == 1]), ("len8plus", d[d.length >= 8])):
                z, o = s[s.truth == "0"], s[s.truth == "O"]
                rows.append({"font": n, "stratum": stratum, "size_pt": round(sizes[n], 2),
                             "within_obj_pct": round(100 * within_cluster_rate(s, objective), 2),
                             "pair_0O_pct": round(100 * ((z.pred == "O").sum() + (o.pred == "0").sum()) / max(len(z) + len(o), 1), 2),
                             "char_error_pct": round(100 * float((s.pred != s.truth).mean()), 2), "n": len(s)})
            print(n, "done", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / "parseq_eval.csv", index=False)
    print(f"PARSeq {REPO}")
    with pd.option_context("display.width", 200):
        print(df.pivot_table(index="font", columns="stratum", values=["within_obj_pct", "char_error_pct"])
              .sort_values(("within_obj_pct", "all")).to_string())
        print(df[df.stratum == "all"].set_index("font")["pair_0O_pct"].sort_values().to_string())


if __name__ == "__main__":
    main()
