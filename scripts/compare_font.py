"""Run the README benchmark on any font and report how it compares (James, 2026-10-13).

The font is given as a file path or a name: a name is looked up (full name or family, case-insensitive) in
Windows Fonts, your own installed fonts and vendor/ofl. Every condition (clean, blurry, noisy, low-res, JPEG,
ink bleed, smudged, damaged, heavy) on every kind of text (paragraphs, codes, numbers), 300 lines each, read by the
four engines, exactly as in the README. Compared with MaxOCR and the best other font in out/report/readme_bench.csv.

    python scripts/compare_font.py "Times New Roman"      (or a path to a .ttf/.otf)
Writes out/report/compare_<name>.json and .md.
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readme_bench import CONDITIONS, ROOT, USER_FONTS, WIN, image, in_batches, texts  # noqa: E402


def find_font(arg: str) -> tuple[str, str]:
    """(path, display name) for a path or a font name."""
    from fontTools.ttLib import TTFont
    if Path(arg).is_file():
        f = TTFont(arg, lazy=True, fontNumber=0)
        return arg, f["name"].getDebugName(4) or Path(arg).stem
    want = arg.lower().replace(" ", "")
    files = [p for d in (WIN, USER_FONTS, str(ROOT / "vendor" / "ofl") + "/**/")
             for ext in ("ttf", "otf", "TTF", "OTF") for p in glob.glob(d + "*." + ext, recursive=True)]
    hits = []
    for p in files:
        try:
            n = TTFont(p, lazy=True, fontNumber=0)["name"]
        except Exception:
            continue
        full, fam = (n.getDebugName(4) or ""), (n.getDebugName(1) or "")
        if want in (full.lower().replace(" ", ""), fam.lower().replace(" ", "")):
            hits.append((full.lower().replace(" ", "") != want, "regular" not in full.lower(), p, full))
    if not hits:
        sys.exit(f"No font named {arg!r} found in Windows Fonts, your fonts or vendor/ofl. Give the file path instead.")
    hits.sort()
    return hits[0][2], hits[0][3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font", help="font file path or font name")
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    path, name = find_font(a.font)
    print(f"Font: {name}  ({path})", flush=True)

    import rung0
    from text_eval import char_err, read_tesseract_dict
    from maxocr.corpus import GENERAL_ALPHABET
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    from maxocr.fonts import matched_size
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    sets, size = texts(a.n), matched_size(path, 8.0)
    rows = []
    for cond in CONDITIONS:
        for kind, lines in sets.items():
            imgs = [image(path, t, size, cond, k) for k, t in enumerate(lines)]
            preds = {"paddle": [paddle.text(im) for im in imgs], "easyocr": in_batches(easy.texts, imgs),
                     "parseq": in_batches(pq.read, imgs), "tesseract": read_tesseract_dict(imgs, fold=False)}
            row = {"text": kind, "condition": cond, **{e: round(char_err(lines, p), 2) for e, p in preds.items()}}
            row["mean"] = round(float(np.mean([row[e] for e in preds])), 2)
            rows.append(row)
            print(f"  {kind:10} {cond:9} {row['mean']:6.2f}", flush=True)

    ref = pd.read_csv(ROOT / "out" / "report" / "readme_bench.csv")
    ref = ref[ref.font != name]
    out = []
    for r in rows:
        cell = ref[(ref.text == r["text"]) & (ref.condition == r["condition"])].set_index("font")["mean"]
        others = cell.drop("MaxOCR", errors="ignore")
        out.append({**r, "maxocr": float(cell.get("MaxOCR", np.nan)), "best_other": others.idxmin(),
                    "best_other_error": float(others.min())})
    df = pd.DataFrame(out)
    avg = {k: round(float(df[df.text == k]["mean"].mean()), 2) for k in sets}
    avg["all"] = round(float(df["mean"].mean()), 2)
    mx = {k: round(float(df[df.text == k]["maxocr"].mean()), 2) for k in sets}
    mx["all"] = round(float(df["maxocr"].mean()), 2)

    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    rep = ROOT / "out" / "report"
    json.dump({"font": name, "path": path, "lines_per_cell": a.n, "averages": avg, "maxocr_averages": mx,
               "cells": out}, open(rep / f"compare_{slug}.json", "w"), indent=1)
    md = [f"# {name} vs MaxOCR", "", f"`{path}`  ", f"Character error %, lower is better. {a.n} lines per cell, "
          "average of PaddleOCR, EasyOCR, PARSeq and Tesseract.", "",
          "| Text | " + name + " | MaxOCR |", "|---|---:|---:|"]
    md += [f"| {k} | {avg[k]:.2f} | {mx[k]:.2f} |" for k in list(sets) + ["all"]]
    md += ["", "| Text | Condition | " + name + " | MaxOCR | Best other font |", "|---|---|---:|---:|---|"]
    for r in out:
        md.append(f"| {r['text']} | {r['condition']} | {r['mean']:.2f} | {r['maxocr']:.2f} | "
                  f"{r['best_other_error']:.2f} {r['best_other']} |")
    (rep / f"compare_{slug}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nAverage: {name} {avg['all']:.2f}  MaxOCR {mx['all']:.2f}")
    print(f"Reports: out/report/compare_{slug}.md and .json")


if __name__ == "__main__":
    main()
