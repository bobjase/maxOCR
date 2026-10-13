"""The four README benchmark cells where another font still has fewer errors than MaxOCR v0.97 (James: "we're still
not #1 in all criteria", 2026-10-13). For each: is the gap real, and which characters do we lose?

Each cell is run twice for MaxOCR and the font ahead of it, keeping every engine's reading:
  bench   the README's own lines and damage (should reproduce the table)
  fresh   new lines and new damage (codes from another seed, the story wrapped at 26 instead of 22, damage seeds
          shifted by 1000): a gap that is real shows up here too; a gap that is noise may flip
    python scripts/why_behind.py            (writes out/report/why_behind_preds.jsonl and prints the comparison)
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
from why_courier import errors  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402
from maxocr.prose import story_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CELLS = [("paragraphs", "low-res", "Courier Prime"), ("paragraphs", "heavy", "Courier New"),
         ("codes", "noisy", "Bookman Old Style"), ("codes", "low-res", "Courier Prime")]


def fresh(n: int) -> dict[str, list[str]]:
    rng = np.random.default_rng(2027)
    alnum = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return {"paragraphs": story_lines(26)[:n],
            "codes": ["".join(rng.choice(list(alnum), rng.integers(6, 13))) for _ in range(n)]}


def main():
    sets = {"bench": (texts(100), 0), "fresh": (fresh(100), 1000)}
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    out = open(ROOT / "out" / "report" / "why_behind_preds.jsonl", "w")
    for kind, cond, rival in CELLS:
        for set_name, (lines_by_kind, shift) in sets.items():
            lines = lines_by_kind[kind]
            for name in ("MaxOCR", rival):
                path = FONTS[name]
                size = matched_size(path, 8.0)
                imgs = [image(path, t, size, cond, k + shift) for k, t in enumerate(lines)]
                preds = {"paddle": [paddle.text(im) for im in imgs], "easyocr": easy.texts(imgs),
                         "parseq": pq.read(imgs), "tesseract": read_tesseract_dict(imgs, fold=False)}
                lost, became = Counter(), Counter()
                for e, ps in preds.items():
                    for k, (t, p) in enumerate(zip(lines, ps)):
                        out.write(json.dumps({"set": set_name, "font": name, "text": kind, "condition": cond,
                                              "engine": e, "line": k, "truth": t, "pred": p}) + "\n")
                        for c, b in errors(t, p):
                            lost[c] += 1
                            became[f"{c}>{b or '_'}"] += 1
                per = {e: round(char_err(lines, ps), 2) for e, ps in preds.items()}
                print(json.dumps({"set": set_name, "text": kind, "condition": cond, "font": name,
                                  "mean": round(float(np.mean(list(per.values()))), 2), "engines": per,
                                  "most_lost": lost.most_common(12), "became": became.most_common(12)}), flush=True)
                out.flush()
    out.close()
    print("WHY BEHIND DONE", flush=True)


if __name__ == "__main__":
    main()
