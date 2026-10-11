"""Does the gain survive at larger sizes? Character error vs point size and scan resolution.

1,000 uncropped validation lines per configuration, s=0.5 (blur and the other operators are in pixels,
so a larger rendering is also a relatively cleaner one, as with a better scan), suite (a); PaddleOCR,
EasyOCR (general alphabet, case folded), Tesseract (whitelist) and the held-out PARSeq (general alphabet,
case folded). Fonts are compared at equal capital height (maxocr.fonts.matched_size; the size column is
the MaxOCR point size).

    python scripts/size_sweep.py --fonts-json f.json [--sizes 6,8,10,12] [--dpis 200,300]
Writes out/report/size_sweep.csv.
"""
import argparse
import json
import sys
from multiprocessing import get_context
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.degrade import degrade  # noqa: E402
from maxocr.engines.easyocr_rec import EasyOCRRec  # noqa: E402
from maxocr.engines.parseq import Parseq  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _imgs(args):
    font, insts, size, dpi = args
    import cv2
    cv2.setNumThreads(1)
    return [degrade(font, i, rung0.SEVERITY, size, dpi) for i in insts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--sizes", default="6,8,10,12")
    ap.add_argument("--dpis", default="200,300")
    ap.add_argument("--lines", type=int, default=1000)
    a = ap.parse_args()
    fonts = json.loads(Path(a.fonts_json).read_text())
    val = [i for i in rung0.bank("val") if not i.cropped][:a.lines]
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=True)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    rows = []
    for dpi in [int(x) for x in a.dpis.split(",")]:
        for size in [float(x) for x in a.sizes.split(",")]:
            ms = {n: matched_size(p, size) for n, p in fonts.items()}
            jobs = [Job(n, p, rung0.SEVERITY, "a", c, size_pt=ms[n], dpi=dpi) for n, p in fonts.items() for c in chunk(val, 50)]
            chars, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy)
            with get_context("spawn").Pool(16) as pool:
                for n, p in fonts.items():
                    imgs = [im for part in pool.map(_imgs, [(p, val[i:i + 125], ms[n], dpi) for i in range(0, len(val), 125)])
                            for im in part]
                    recs = []
                    for inst, pred in zip(val, pq.read(imgs)):
                        _, mapping, _ = align(inst.text, pred)
                        recs += [(inst.text[i], pred[j] if j is not None else "") for i, j in enumerate(mapping)]
                    d = pd.DataFrame(recs, columns=["truth", "pred"])
                    row = {"font": n, "dpi": dpi, "size_pt": size,
                           "cap_px": round(size / 72 * dpi * 0.7, 1)}
                    for e in ("paddle", "tesseract", "easyocr"):
                        g = chars[(chars.font == n) & (chars.engine == e)]
                        row[e] = round(100 * float((g.pred != g.truth).mean()), 2)
                    row["parseq"] = round(100 * float((d.pred != d.truth).mean()), 2)
                    row["mean"] = round((row["paddle"] + row["tesseract"] + row["easyocr"] + row["parseq"]) / 4, 2)
                    rows.append(row)
                    print(json.dumps(row), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / "size_sweep.csv", index=False)
    with pd.option_context("display.width", 200):
        print(df.pivot_table(index=["dpi", "size_pt"], columns="font", values="mean").round(2).to_string())


if __name__ == "__main__":
    main()
