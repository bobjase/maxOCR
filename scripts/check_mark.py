"""Prototype: a light grey mark next to a number that carries its check digit, invisible to OCR after the
black-and-white step (James, 2026-10-21: "a 20-30% opacity pipe after the last char which indicated (by its height or
dashed pattern) the ECC info", "make a few options and try all at once").

The number's Damm check value (it catches every single wrong digit and every swap of two neighbours) goes into 10
slots: start 1, the 4 bits, the 4 bits inverted, end 1, so a damaged mark is recognised as damaged. The mark is drawn
on the clean grey line (prototype at image level; the font would draw it with its contextual features), the print
condition is applied, the four engines read the black-and-white line, and a decoder reads the slots from the grey scan.
Measured per option and condition: does the mark change what the engines read (extra characters, error), how often
the decoder recovers the check value, and how many misread numbers it catches.

    python scripts/check_mark.py [--n 300]   -> out/report/check_mark.csv
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import readme_bench as rb  # noqa: E402
from text_eval import char_err, read_tesseract_dict  # noqa: E402

DAMM = [[0, 3, 1, 7, 5, 9, 8, 6, 4, 2], [7, 0, 9, 2, 1, 5, 4, 8, 6, 3], [4, 2, 0, 6, 8, 7, 1, 3, 5, 9],
        [1, 7, 5, 0, 9, 8, 3, 4, 2, 6], [6, 1, 2, 3, 0, 4, 5, 9, 7, 8], [3, 6, 7, 4, 2, 0, 9, 5, 8, 1],
        [5, 8, 6, 9, 7, 2, 0, 1, 3, 4], [8, 9, 4, 5, 3, 6, 2, 0, 1, 7], [9, 4, 3, 8, 6, 1, 7, 2, 0, 5],
        [2, 5, 8, 1, 4, 3, 6, 7, 9, 0]]


def damm(digits: str) -> int:
    s = 0
    for c in digits:
        s = DAMM[s][int(c)]
    return s


def slots(check: int) -> list:
    b = [(check >> i) & 1 for i in (3, 2, 1, 0)]
    return [1] + b + [1 - x for x in b] + [1]


OPTIONS = {   # name: (shape, grey ink level 0..1, thickness in px at 300 dpi)
    "A underline 25%": ("under", 0.25, 2), "B underline 35%": ("under", 0.35, 2),
    "C thick underline 25%": ("under", 0.25, 4), "D dot row 25%": ("dots", 0.25, 4), "E pipe 25%": ("pipe", 0.25, 3),
    # round 2 (James: "WAY too prominent", "the grey is too dark", underlines at most half the thinnest): hairlines
    "F hairline 15%": ("under", 0.15, 1), "G hairline 10%": ("under", 0.10, 1), "H stipple hairline 25%": ("stipple", 0.25, 1),
    # James: "so close to each other that it would be almost impossible to tell where one ends and the next begins":
    # each dash only the middle 60% of its slot
    "F2 short dashes 15%": ("short", 0.15, 1), "G2 short dashes 10%": ("short", 0.10, 1)}
ROUND = None   # set from --options
GAP = 3


def ink_box(g):
    ys, xs = np.where(g < 128)
    return ys.min(), ys.max(), xs.min(), xs.max()


def draw(g, shape, level, th, check):
    g = np.pad(g, ((0, 10), (0, 24)), constant_values=255)
    y0, y1, x0, x1 = ink_box(g)
    v = 255 * (1 - level)
    for i, b in enumerate(slots(check)):
        if not b:
            continue
        if shape in ("under", "dots", "stipple", "short"):
            w = (x1 - x0 + 1) / 10
            a, c = int(x0 + i * w + 1), int(x0 + (i + 1) * w - 1)
            if shape == "short":
                a, c = int(x0 + (i + 0.2) * w), int(x0 + (i + 0.8) * w)
                g[y1 + GAP, a:c] = np.minimum(g[y1 + GAP, a:c], v)
            elif shape == "stipple":                       # every other pixel: a hairline of separate tiny dots
                g[y1 + GAP, a:c:2] = np.minimum(g[y1 + GAP, a:c:2], v)
            elif shape == "under":
                g[y1 + GAP:y1 + GAP + th, a:c] = np.minimum(g[y1 + GAP:y1 + GAP + th, a:c], v)
            else:
                cv2.circle(g, ((a + c) // 2, y1 + GAP + th // 2), th // 2 + 1, v, -1)
        else:
            h = (y1 - y0 + 1) / 10
            a, c = int(y0 + i * h + 0.5), int(y0 + (i + 1) * h - 0.5)
            g[a:c, x1 + 6:x1 + 6 + th] = np.minimum(g[a:c, x1 + 6:x1 + 6 + th], v)
    return g


def decode(grey, bw, shape, th):
    """The check value, or None when the mark cannot be read reliably."""
    try:
        y0, y1, x0, x1 = ink_box(bw)
    except ValueError:
        return None
    d = 255 - grey.astype(np.float32)
    if shape in ("under", "dots", "stipple", "short"):
        band = d[y1 + 1:y1 + GAP + th + 4, x0:x1 + 1]
        prof = band.max(0) if band.size else None
    else:
        band = d[y0:y1 + 1, x1 + 2:x1 + 14]
        prof = band.max(1) if band.size else None
    if prof is None or len(prof) < 10:
        return None
    prof = cv2.GaussianBlur(prof.reshape(1, -1).astype(np.float32), (0, 0), 1).ravel()
    n = len(prof)
    vals = [prof[int(n * i / 10):max(int(n * (i + 1) / 10), int(n * i / 10) + 1)].mean() for i in range(10)]
    lo, hi = min(vals), max(vals)
    if hi - lo < 12:
        return None
    bits = [1 if v > (lo + hi) / 2 else 0 for v in vals]
    if bits[0] != 1 or bits[9] != 1 or any(bits[1 + i] == bits[5 + i] for i in range(4)):
        return None
    c = bits[1] * 8 + bits[2] * 4 + bits[3] * 2 + bits[4]
    return c if c <= 9 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--options", help="comma-separated option names (default: all, plus no mark)")
    ap.add_argument("--out", default="out/report/check_mark.csv")
    a = ap.parse_args()
    import rung0
    from maxocr.corpus import GENERAL_ALPHABET
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    from maxocr.fonts import matched_size
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**{**eng, "alphabet": GENERAL_ALPHABET + " "}), Parseq(**eng)
    lines = rb.texts(a.n)["numbers"]
    P = rb.FONTS["MaxOCR"]
    size = matched_size(P, 8.0)
    conds = ["clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "thermal", "dot-matrix lq", "phone photo"]
    real_clean, real_otsu = rb.clean, rb.otsu
    truth = [damm(t.replace(" ", "")) for t in lines]
    rows = []
    opts = a.options.split(",") if a.options else ["none"] + list(OPTIONS)
    for opt in opts:
        for cond in conds:
            greys, bws = [], []
            for k, t in enumerate(lines):
                def marked(font, text, sz, dpi, binarize=False, _k=k):
                    g = real_clean(font, text, sz, dpi, binarize=False).astype(np.float32)
                    if opt == "none":
                        return np.pad(g, ((0, 10), (0, 24)), constant_values=255)
                    shape, level, th = OPTIONS[opt]
                    return draw(g, shape, level, th, truth[_k])
                rb.clean, rb.otsu = marked, (lambda x: x)
                try:
                    grey = np.clip(rb.image(P, t, size, cond, k), 0, 255).astype(np.uint8)
                finally:
                    rb.clean, rb.otsu = real_clean, real_otsu
                greys.append(grey)
                bws.append(real_otsu(grey.astype(np.float32)))
            preds = {"paddle": [paddle.text(im) for im in bws], "easyocr": rb.in_batches(easy.texts, bws),
                     "parseq": rb.read_by_words(pq, bws), "tesseract": read_tesseract_dict(bws, fold=False)}
            row = {"option": opt, "condition": cond,
                   "error": round(float(np.mean([char_err(lines, p) for p in preds.values()])), 2),
                   "extra chars": int(sum(max(0, len(p.replace(" ", "")) - len(t.replace(" ", "")))
                                          for ps in preds.values() for t, p in zip(lines, ps)))}
            if opt != "none":
                shape, _, th = OPTIONS[opt]
                dec = [decode(gy, bw, shape, th) for gy, bw in zip(greys, bws)]
                row["decoded %"] = round(100 * np.mean([d is not None for d in dec]), 1)
                row["decoded right %"] = round(100 * np.mean([d == c for d, c in zip(dec, truth)]), 1)
                wrong = caught = 0
                for ps in preds.values():
                    for t, p, d in zip(lines, ps, dec):
                        got = "".join(ch for ch in p if ch.isdigit())
                        if got != t.replace(" ", ""):
                            wrong += 1
                            if d is not None and (not got or damm(got) != d):
                                caught += 1
                row["misreads"] = wrong
                row["caught"] = caught
            rows.append(row)
            print(json.dumps(row), flush=True)
            pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
