"""Isolation test: is each glyph recognizable on its own? Each target alone and among mixed, all-letter
and all-digit neighbours outside its clusters (see discover_pair.isolation_bank), on PaddleOCR,
Tesseract, EasyOCR and the held-out PARSeq, s=0.5, suite (a).

    python scripts/isolation_eval.py [--pair 0O] [--top 6]
Writes out/discover/<pair>/isolation.csv.
"""
import argparse
import json
import sys
from multiprocessing import get_context
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from discover_pair import isolation_bank  # noqa: E402
from maxocr.degrade import degrade  # noqa: E402
from maxocr.engines.easyocr_rec import EasyOCRRec  # noqa: E402
from maxocr.engines.parseq import Parseq  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from maxocr.fonts import BASELINES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _imgs(args):
    font, insts = args
    import cv2
    cv2.setNumThreads(1)
    return [degrade(font, i, rung0.SEVERITY) for i in insts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="0O")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--archive", default="0O_run2", help="discovery run directory under out/discover")
    ap.add_argument("--fonts-json", help="evaluate these fonts instead: JSON {name: path}")
    ap.add_argument("--out", default=None, help="output CSV name under out/report (with --fonts-json)")
    a = ap.parse_args()
    t1, t2 = a.pair[0], a.pair[1]
    base = json.loads((ROOT / "out" / "amalgam_opt" / "08BDEOQ" / "elite.json").read_text())["font"]
    fonts = {"baseline: Source Code Pro": str(BASELINES["Source Code Pro"]), "amalgam (optimized)": base}
    arch = ROOT / "out" / "discover" / a.archive / "archive.json"
    if a.fonts_json:
        fonts = json.loads(Path(a.fonts_json).read_text())
    elif arch.exists():
        for k, r in enumerate(json.loads(arch.read_text())[:a.top]):
            fonts[f"{a.archive} #{k + 1}"] = r["font"]
    bank, info = isolation_bank(a.pair)
    kind = {i: v[1] for i, v in info.items()}
    target_pos = {i: v[2] for i, v in info.items()}
    jobs = [Job(n, p, rung0.SEVERITY, "a", c) for n, p in fonts.items() for c in chunk(bank, 60)]
    chars, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=rung0.PaddleRec(), progress=False, easy=EasyOCRRec())
    rows = []
    model = Parseq()
    with get_context("spawn").Pool(16) as pool:
        for n, p in fonts.items():
            imgs = [im for part in pool.map(_imgs, [(p, bank[i:i + 100]) for i in range(0, len(bank), 100)]) for im in part]
            pq = model.read(imgs)
            for i, pred in zip(bank, pq):
                t = i.text[target_pos[i.index]]
                ok = (pred == t) if len(i.text) == 1 else (len(pred) == len(i.text) and pred[target_pos[i.index]] == t)
                rows.append({"font": n, "engine": "parseq", "kind": kind[i.index], "target": t, "correct": ok})
            g = chars[chars.font == n]
            g = g[g.pos == g.inst.map(target_pos)]
            for (e, inst), x in g.groupby(["engine", "inst"]):
                rows.append({"font": n, "engine": e, "kind": kind[inst], "target": x.truth.iloc[0],
                             "correct": bool((x.pred == x.truth).iloc[0])})
    df = pd.DataFrame(rows)
    out = df.groupby(["font", "engine", "kind", "target"]).correct.mean().mul(100).round(1).unstack(["engine"])
    out.to_csv(ROOT / "out" / "report" / a.out if a.fonts_json else ROOT / "out" / "discover" / a.archive / "isolation.csv")
    with pd.option_context("display.width", 220, "display.max_rows", 200):
        print(out.to_string())


if __name__ == "__main__":
    main()
