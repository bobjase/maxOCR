"""Digits-only comparison (cheque/serial use): MICR E-13B (GnuMICR) against MaxOCR and baselines.

3,000 random digit strings (corpus length mix, 20% single digits), each font sized so its 0 has the same
height as the original amalgam's at 8 pt / 200 dpi. Suite (a) at s=0.5 and undegraded; PaddleOCR,
Tesseract, EasyOCR and the held-out PARSeq, output restricted to 0-9A-Z as in the main harness (a code
reader that may also see letters). Uncropped lines only.

    python scripts/digits_eval.py [--fonts-json f.json --out name.csv]
Writes out/report/digits_eval.csv (or the --out name). Sizes are matched on the capital H (on the 0 for
fonts without letters, i.e. MICR).
"""
import json
import sys
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.corpus import make_strings  # noqa: E402
from maxocr.degrade import clean, degrade, make_instance  # noqa: E402
from maxocr.engines.easyocr_rec import EasyOCRRec  # noqa: E402
from maxocr.engines.parseq import Parseq  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from maxocr.fonts import BASELINES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
ORIGINAL = str(HOME / "maxocr-work/amalgam_opt/08BDEOQ/g06_09.ttf")


def zero_height(path: str) -> float:
    """Reference height for size matching: the capital H, or the 0 for digit-only fonts (MICR)."""
    f = TTFont(path, lazy=False)
    gs, cm = f.getGlyphSet(), f.getBestCmap()
    p = BoundsPen(gs)
    gs[cm[ord("H") if ord("H") in cm else ord("0")]].draw(p)
    return (p.bounds[3] - p.bounds[1]) / f["head"].unitsPerEm


def _imgs(args):
    font, size, insts, sev = args
    import cv2
    cv2.setNumThreads(1)
    return [clean(font, i.text, size, 200, True) if sev < 0 else degrade(font, i, sev, size) for i in insts]


def score(df: pd.DataFrame) -> dict:
    return {"char_err_pct": round(100 * float((df.pred != df.truth).mean()), 2)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json")
    ap.add_argument("--out", default="digits_eval.csv")
    a = ap.parse_args()
    fonts = json.loads(Path(a.fonts_json).read_text()) if a.fonts_json else {
        "MICR E-13B (GnuMICR)": str(ROOT / "vendor/fonts/GnuMICR.ttf"),
        "OCR-A": str(BASELINES["OCR-A"]),
        "OCR-B": str(BASELINES["OCR-B"]),
        "Source Code Pro": str(BASELINES["Source Code Pro"]),
        "original amalgam": ORIGINAL,
        "MaxOCR Machine (current)": open(HOME / "maxocr-work/keep/CURRENT").read().strip(),
        "MaxOCR Text (base F)": str(HOME / "maxocr-work/golden/mixF.ttf"),
    }
    ref = zero_height(ORIGINAL)
    size = {n: round(8.0 * ref / zero_height(p), 3) for n, p in fonts.items()}
    texts = make_strings(3000, 909, alphabet="0123456789")
    bank = [i for i in (make_instance(k, s, 909) for k, s in enumerate(texts)) if not i.cropped]
    paddle, easy, model = rung0.PaddleRec(), EasyOCRRec(), Parseq()
    rows = []
    for sev, label in ((rung0.SEVERITY, "s=0.5"), (-1.0, "clean")):
        jobs = [Job(n, p, sev, "a", c, size_pt=size[n], clean=sev < 0) for n, p in fonts.items() for c in chunk(bank, 50)]
        chars, strings, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy)
        with get_context("spawn").Pool(16) as pool:
            for n, p in fonts.items():
                imgs = [im for part in pool.map(_imgs, [(p, size[n], bank[i:i + 250], sev) for i in range(0, len(bank), 250)])
                        for im in part]
                preds = model.read(imgs)
                recs, exact = [], 0
                for inst, pred in zip(bank, preds):
                    _, mapping, _ = align(inst.text, pred)
                    recs += [{"truth": inst.text[i], "pred": pred[j] if j is not None else ""} for i, j in enumerate(mapping)]
                    exact += pred == inst.text
                pq = pd.DataFrame(recs)
                row = {"font": n, "condition": label, "size_pt": size[n]}
                for e in ("paddle", "tesseract", "easyocr"):
                    g = chars[(chars.font == n) & (chars.engine == e)]
                    s = strings[(strings.font == n) & (strings.engine == e)]
                    row[f"{e}_char_err_pct"] = score(g)["char_err_pct"]
                    row[f"{e}_exact_lines_pct"] = round(100 * float((s.truth == s.pred).mean()), 2)
                    one = s[s.length == 1]
                    row[f"{e}_single_digit_pct"] = round(100 * float((one.truth == one.pred).mean()), 2)
                row["parseq_char_err_pct"] = score(pq)["char_err_pct"]
                row["parseq_exact_lines_pct"] = round(100 * exact / len(bank), 2)
                ones = [(i, p) for i, p in zip(bank, preds) if len(i.text) == 1]
                row["parseq_single_digit_pct"] = round(100 * float(np.mean([p == i.text for i, p in ones])), 2)
                row["mean_char_err_pct"] = round(np.mean([row[f"{e}_char_err_pct"] for e in ("paddle", "tesseract", "easyocr", "parseq")]), 2)
                rows.append(row)
                print(json.dumps(row), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / a.out, index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(df[["font", "condition", "size_pt"] + [c for c in df.columns if "char_err" in c]].to_string(index=False))


if __name__ == "__main__":
    main()
