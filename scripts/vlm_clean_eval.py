"""Clean-print reading by a vision-language model (Qwen2.5-VL, held out): where does it misread MaxOCR?

Clean renders (no damage) of everyday prose, the same words shuffled (no sentence to predict from) and
mixed codes, at several sizes (200 dpi, equal capital height), read case-sensitively with a plain prompt.
Character error from alignment, spaces ignored. Also tallies which characters are misread and
whole-word skips (3+ consecutive characters missing), per font.

    python scripts/vlm_clean_eval.py --fonts-json f.json [--sizes 6,7,8,9,10] [--name run]
Writes out/report/vlm_clean_<name>.csv (font, set, size, char error) and vlm_clean_<name>_chars.csv
(font, truth char, count, errors, error %, top misreadings).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maxocr.align import align  # noqa: E402
from maxocr.degrade import clean  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402
from maxocr.prose import code_lines, prose_lines, shuffled_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROMPT = "Transcribe the text in this image exactly. Output only the text."


def tally(truth: str, pred: str, count: Counter, errs: Counter, subs: dict) -> tuple[int, int, int]:
    """Errors (substitutions, deletions, insertions) of one line, spaces ignored; returns (errors, chars, skips)."""
    t, p = truth.replace(" ", ""), pred.replace(" ", "")
    _, mapping, n_ins = align(t, p)
    k, run, skips = n_ins, 0, 0
    for i, j in enumerate(mapping):
        count[t[i]] += 1
        bad = j is None or p[j] != t[i]
        if bad:
            k += 1
            errs[t[i]] += 1
            subs[t[i]][p[j] if j is not None else "-"] += 1
        run = run + 1 if j is None else 0
        skips += run == 3
    return k, len(t), skips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--sizes", default="6,7,8,9,10")
    ap.add_argument("--name", default="run")
    a = ap.parse_args()
    fonts = json.loads(Path(a.fonts_json).read_text())
    sets = {"prose": prose_lines(), "shuffled": shuffled_lines(), "codes": code_lines()}
    from maxocr.engines.qwenvl import QwenVL
    vlm = QwenVL(prompt=PROMPT, casefold=False)
    rows, char_rows = [], []
    for name, path in fonts.items():
        count, errs, subs = Counter(), Counter(), defaultdict(Counter)
        for pt in (float(s) for s in a.sizes.split(",")):
            sz = matched_size(path, pt)
            for set_name, texts in sets.items():
                preds = vlm.read([clean(path, t, sz, 200, True) for t in texts], max_new_tokens=64)
                k = n = skips = 0
                for t, p in zip(texts, preds):
                    dk, dn, ds = tally(t, p, count, errs, subs)
                    k, n, skips = k + dk, n + dn, skips + ds
                rows.append({"font": name, "set": set_name, "pt": pt, "char_err": round(100 * k / n, 3),
                             "errors": k, "chars": n, "word_skips": skips})
                print(json.dumps(rows[-1]), flush=True)
        for c in sorted(count):
            char_rows.append({"font": name, "char": c, "count": count[c], "errors": errs[c],
                              "err_pct": round(100 * errs[c] / count[c], 2),
                              "read_as": " ".join(f"{q}:{m}" for q, m in subs[c].most_common(3))})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / f"vlm_clean_{a.name}.csv", index=False)
    pd.DataFrame(char_rows).to_csv(ROOT / "out" / "report" / f"vlm_clean_{a.name}_chars.csv", index=False)
    summary = df.groupby(["font", "set"]).apply(lambda g: 100 * g.errors.sum() / g.chars.sum()).unstack().round(3)
    summary["skips"] = df.groupby("font").word_skips.sum()
    print(summary.to_string())


if __name__ == "__main__":
    main()
