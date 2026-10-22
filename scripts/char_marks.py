"""Faint grey half-underlines on digits and on the letters OCR confuses with them (James, 2026-10-21: "Should we try it
on the A-Za-z as well?" ... "yes"). Groups from out/report/char_confusions.csv, chosen so each common confused pair
gets different marks while ordinary lowercase stays unmarked:

  left half : 2 6 8, C K O S U V W X Y F, l q
  right half: 0 1 3 4 5 7 9, Z
  both      : I
  none      : every other character

The mark is a 1-pixel 15% grey line under the left or right half of the character, 2 px below the line's lowest
ink-free row (what a colour-font layer would print), drawn at the character's real position (HarfBuzz). Measured on
numbers, codes and paragraphs in ten conditions with the four engines: the change in OCR error, how often each mark is
read back right (none / left / right), how many misread lines it flags (catches) and how many correctly read lines it
wrongly flags (false alarms). The decoder is given each character's box, as an OCR engine reports it.

    python scripts/char_marks.py   -> out/report/char_marks.csv
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from digit_marks import baseline_row, char_drops, digit_spans  # noqa: E402

LEFT = set("268CKOSUVWXYFlq")
RIGHT = set("0134579Z")
BOTH = set("I")          # James: "you have left + right + none; what about BOTH?" -- separates I from l, 1 and i


BINARY = os.environ.get("MARKS") == "binary"   # James, 2026-10-21: "Only use two kinds of marking - full line under char vs none"


def cls(ch):
    if BINARY:
        return "B" if ch.isdigit() else "N"
    return "B" if ch in BOTH else "L" if ch in LEFT else ("R" if ch in RIGHT else "N")


def marked(g, spans, base, drops, level=0.15):
    """The hairline 2 px under each character's own bottom (the baseline, or lower for MaxOCR's low-set digits; tails
    of g p q y j ignored). James: "very far from the capital chars" when it hung below the tails."""
    g = np.pad(g, ((0, 6), (0, 0)), constant_values=255).astype(np.float32)
    v = 255 * (1 - level)
    for (ch, a, b), dr in zip(spans, drops):
        c = cls(ch)
        if c == "N":
            continue
        mid = (a + b) / 2
        x0, x1 = {"L": (a, mid - 1), "R": (mid + 1, b), "B": (a, b)}[c]
        y = int(round(base + (dr or 0))) + 2
        g[y, int(round(x0)):int(round(x1)) + 1] = np.minimum(g[y, int(round(x0)):int(round(x1)) + 1], v)
    return g


def decode(grey, spans, base, drops):
    """Per character: 'L', 'R', 'B', 'N' or None (cannot tell)."""
    d = 255 - grey.astype(np.float32)
    out = []
    for (ch, a, b), dr in zip(spans, drops):
        if dr is None:                     # a tail runs through the mark row: cannot tell
            out.append(None); continue
        y = int(round(base + dr)) + 2
        band = d[y - 1:y + 2]
        a, b = int(round(a)), int(round(b)); mid = (a + b) // 2
        if band.size == 0 or b <= a + 1:
            out.append(None); continue
        vl = band[:, a:mid].mean(1).max() if mid > a else 0
        vr = band[:, mid + 1:b + 1].mean(1).max() if b > mid else 0
        below = d[y + 3:y + 6, a:b + 1]                        # plain paper just under the mark row
        bg = float(np.median(below)) if below.size else 0.0
        hi, lo = max(vl, vr), min(vl, vr)
        if BINARY:     # whole width averaged: a spot of spread ink from a serif is not a full line
            row = d[y - 1:y + 2, a:b + 1].mean(1).max() if b > a else 0
            out.append("B" if row - bg >= 15 else "N" if row - bg <= 5 else None)
            continue
        # cautious (James, 2026-10-21: "yes" to flagging only clearly readable marks): a clean 15% mark is about 38 grey
        # levels above the paper; anything between "clearly there" and "clearly not" is reported as cannot-tell
        on, off = 15, 4
        if hi - bg <= off:
            out.append("N")
        elif lo - bg >= on and hi - lo <= 6:
            out.append("B")
        elif hi - bg >= on and lo - bg <= off and hi - lo >= on - off:
            out.append("L" if vl > vr else "R")
        else:
            out.append(None)
    return out


def main():
    import pandas as pd
    import readme_bench as rb
    import rung0
    from text_eval import char_err, read_tesseract_dict
    from maxocr.corpus import GENERAL_ALPHABET
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    from maxocr.fonts import matched_size
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**{**eng, "alphabet": GENERAL_ALPHABET + " "}), Parseq(**eng)
    P = rb.FONTS["MaxOCR"]; size = matched_size(P, 8.0); sets = rb.texts(300)
    conds = ["clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "thermal", "dot-matrix lq", "phone photo"]
    real_clean, real_otsu = rb.clean, rb.otsu
    rows = []
    for kind in ("numbers", "codes", "paragraphs"):
        lines = sets[kind]
        spans_all = [digit_spans(P, t, size, rb.DPI) for t in lines]
        drops_all = [char_drops(P, t, size, rb.DPI) for t in lines]
        for opt in ("none", "grey"):
            for cond in conds:
                greys, bases = [], []
                for k, (t, sp, dr) in enumerate(zip(lines, spans_all, drops_all)):
                    base_holder = {"b": baseline_row(P, t, size, rb.DPI)}

                    def mk(font, text, sz, dpi, binarize=False, _sp=sp, _b=base_holder["b"], _dr=dr):
                        g = real_clean(font, text, sz, dpi, binarize=False).astype(np.float32)
                        return marked(g, _sp, _b, _dr) if opt == "grey" else np.pad(g, ((0, 6), (0, 0)), constant_values=255)
                    rb.clean, rb.otsu = mk, (lambda x: x)
                    try:
                        greys.append(np.clip(rb.image(P, t, size, cond, k), 0, 255).astype(np.uint8))
                    finally:
                        rb.clean, rb.otsu = real_clean, real_otsu
                    bases.append(base_holder["b"])
                bws = [real_otsu(g.astype(np.float32)) for g in greys]
                preds = {"paddle": [paddle.text(im) for im in bws], "easyocr": rb.in_batches(easy.texts, bws),
                         "parseq": rb.read_by_words(pq, bws), "tesseract": read_tesseract_dict(bws, fold=False)}
                row = {"text": kind, "option": opt, "condition": cond,
                       "error": round(float(np.mean([char_err(lines, p) for p in preds.values()])), 2)}
                if opt == "grey":
                    # the line geometry only survives unchanged in the conditions that do not move the text
                    same_geom = cond in ("clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "thermal", "dot-matrix lq")
                    marks = [decode(g, sp, b, dr) if same_geom else None for g, sp, b, dr in zip(greys, spans_all, bases, drops_all)]
                    tot = ok = 0
                    for sp, m in zip(spans_all, marks):
                        if m is None:
                            continue
                        for (ch, _, _), mk_ in zip(sp, m):
                            tot += 1; ok += mk_ == cls(ch)
                    row["marks right %"] = round(100 * ok / max(1, tot), 1) if tot else None
                    wrong = caught = right = false_alarm = 0
                    for ps in preds.values():
                        for t, p, m in zip(lines, ps, marks):
                            tt, pp = t.replace(" ", ""), p.replace(" ", "")
                            if m is None:
                                continue
                            # a line whose digits show no mark at all was printed without them (thermal and dot-matrix
                            # printers cannot print grey): cannot tell
                            unmarked = any(c.isdigit() for c in pp) and not any(x in ("B", "L", "R") for x in m)
                            # self-check per line: when the marks are not trustworthy on this scan, no verdict
                            # (James, 2026-10-21: "better to have some validation than none")
                            if len(pp) == len(tt) and not unmarked:
                                exp = [cls(c) for c in pp]
                                none_seen = [x for e, x in zip(exp, m) if e == "N" and x is not None]
                                mark_seen = [x for e, x in zip(exp, m) if e != "N" and x is not None]
                                if none_seen and sum(x != "N" for x in none_seen) / len(none_seen) > 0.2:
                                    unmarked = True
                                if mark_seen and sum(x == "N" for x in mark_seen) / len(mark_seen) > 0.3:
                                    unmarked = True
                            flag = (not unmarked) and len(pp) == len(tt) and any(x is not None and x != cls(c) for c, x in zip(pp, m))
                            if tt == pp:
                                right += 1; false_alarm += flag
                            else:
                                wrong += 1; caught += flag
                    row.update({"misreads": wrong, "caught": caught, "right": right, "false alarms": false_alarm})
                rows.append(row); print(json.dumps(row), flush=True)
                pd.DataFrame(rows).to_csv("out/report/char_marks_binary.csv" if BINARY else "out/report/char_marks.csv", index=False)


if __name__ == "__main__":
    main()
