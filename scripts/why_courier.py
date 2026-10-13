"""Why does Courier Prime beat MaxOCR on low-res paragraphs, smudged paragraphs and low-res codes (James, 2026-10-13)?
Re-runs those README benchmark cells (same lines, same damage) for MaxOCR, two spacing variants and Courier Prime,
keeping every engine's reading, then counts which characters each font loses.
    python scripts/why_courier.py            (writes out/report/why_courier_preds.jsonl and prints the comparison)
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from readme_bench import FONTS, image, texts  # noqa: E402
from text_eval import char_err, read_tesseract_dict  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {"MaxOCR": FONTS["MaxOCR"],
            "MaxOCR, v0.91 punctuation spacing": str(ROOT / "out" / "golden" / "why_wide_punct.ttf"),
            "MaxOCR Small": str(ROOT / "out" / "fonts" / "MaxOCR-Small.ttf"),
            "Courier Prime": FONTS["Courier Prime"]}
CELLS = [("paragraphs", "low-res"), ("paragraphs", "smudged"), ("codes", "low-res")]


def errors(truth: str, pred: str) -> list[tuple[str, str]]:
    """(truth char, what it became) for every wrong character; spaces ignored as in the benchmark."""
    t, p = truth.replace(" ", ""), pred.replace(" ", "")
    _, mapping, _ = align(t, p)
    return [(t[i], "" if j is None else p[j]) for i, j in enumerate(mapping) if j is None or p[j] != t[i]]


def main():
    sets = texts(100)
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    out = open(ROOT / "out" / "report" / "why_courier_preds.jsonl", "w")
    summary = []
    for kind, cond in CELLS:
        lines = sets[kind]
        for name, path in VARIANTS.items():
            size = matched_size(path, 8.0)
            imgs = [image(path, t, size, cond, k) for k, t in enumerate(lines)]
            preds = {"paddle": [paddle.text(im) for im in imgs], "easyocr": easy.texts(imgs), "parseq": pq.read(imgs),
                     "tesseract": read_tesseract_dict(imgs, fold=False)}
            errs = Counter()
            for e, ps in preds.items():
                for k, (t, p) in enumerate(zip(lines, ps)):
                    out.write(json.dumps({"font": name, "text": kind, "condition": cond, "engine": e, "line": k,
                                          "truth": t, "pred": p}) + "\n")
                    errs.update(c for c, _ in errors(t, p))
            mean = float(np.mean([char_err(lines, ps) for ps in preds.values()]))
            summary.append((kind, cond, name, round(mean, 2), errs.most_common(12)))
            print(json.dumps({"text": kind, "condition": cond, "font": name, "mean": round(mean, 2),
                              "most_lost": errs.most_common(12)}), flush=True)
    out.close()
    print("WHY COURIER DONE", flush=True)


if __name__ == "__main__":
    main()
