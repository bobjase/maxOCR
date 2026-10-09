"""Held-out check with a vision-language model (maxocr/engines/qwenvl.py): ordinary lines and the
isolation test, s=0.5, suite (a), uncropped, case-folded open-vocabulary reading.

    python scripts/vlm_eval.py --fonts-json f.json [--lines 1000] [--pairs 0O,5S,...] [--time-only]
Writes out/report/vlm_lines.csv (per font: character error, pair confusion for each pair) and
out/report/vlm_isolation.csv (per font, glyph, context: correct reads, exact length).
"""
import argparse
import json
import sys
import time
from multiprocessing import get_context
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from discover_pair import adversarial, isolation_bank  # noqa: E402
from discover_validate import _imgs  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.engines.qwenvl import QwenVL  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def render(pool, font, insts):
    return [im for part in pool.map(_imgs, [(font, insts[i:i + 100]) for i in range(0, len(insts), 100)]) for im in part]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--lines", type=int, default=1000)
    ap.add_argument("--pairs", default="0O,5S,1I,2Z,8B,4A,8S,7T,6G,IJ,9I,1A")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--time-only", action="store_true", help="read 128 lines of the first font, report speed, stop")
    a = ap.parse_args()
    fonts = json.loads(Path(a.fonts_json).read_text())
    pairs = a.pairs.split(",")
    model = QwenVL()
    val = [i for i in rung0.bank("val") if not i.cropped][:a.lines]
    line_rows, iso_rows = [], []
    with get_context("spawn").Pool(16) as pool:
        if a.time_only:
            name, path = next(iter(fonts.items()))
            imgs = render(pool, path, val[:128])
            t0 = time.time()
            preds = model.read(imgs, batch=a.batch)
            dt = time.time() - t0
            ok = sum(p == i.text for p, i in zip(preds, val))
            print(json.dumps({"lines": len(imgs), "seconds": round(dt, 1), "lines_per_s": round(len(imgs) / dt, 2),
                              "exact_lines": ok, "examples": [(i.text, p) for i, p in zip(val[:8], preds[:8])]}))
            return
        for name, path in fonts.items():
            preds = model.read(render(pool, path, val), batch=a.batch)
            recs = []
            for inst, pred in zip(val, preds):
                _, mapping, n_ins = align(inst.text, pred)
                recs += [(inst.text[i], pred[j] if j is not None else "") for i, j in enumerate(mapping)]
            df = pd.DataFrame(recs, columns=["truth", "pred"])
            row = {"font": name, "char_err_pct": round(100 * float((df.pred != df.truth).mean()), 2),
                   "exact_lines_pct": round(100 * sum(p == i.text for p, i in zip(preds, val)) / len(val), 2)}
            for pr in pairs:
                x, y = df[df.truth == pr[0]], df[df.truth == pr[1]]
                row[f"{pr}_pair_pct"] = round(100 * ((x.pred == pr[1]).sum() + (y.pred == pr[0]).sum())
                                              / max(len(x) + len(y), 1), 2)
            line_rows.append(row)
            print(json.dumps(row), flush=True)
            for pr in pairs:
                bank, info = isolation_bank(pr)
                bank = [i for i in bank if not i.cropped]
                preds = model.read(render(pool, path, bank), batch=a.batch)
                for inst, pred in zip(bank, preds):
                    t, ctx, pos = info[inst.index]
                    if ctx not in ("single", "mixed", adversarial(t)):
                        continue
                    exact = len(pred) == len(inst.text)
                    iso_rows.append({"font": name, "pair": pr, "glyph": t, "context": ctx,
                                     "correct": bool(exact and pred[pos] == t), "exact_length": exact})
    pd.DataFrame(line_rows).to_csv(ROOT / "out" / "report" / "vlm_lines.csv", index=False)
    iso = pd.DataFrame(iso_rows)
    iso.to_csv(ROOT / "out" / "report" / "vlm_isolation.csv", index=False)
    summary = iso.groupby(["pair", "glyph", "context", "font"]).correct.mean().mul(100).round(0).unstack("font")
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(pd.DataFrame(line_rows).to_string(index=False))
        print(summary.to_string())


if __name__ == "__main__":
    main()
