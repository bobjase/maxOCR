"""Score the printed and scanned MaxOCR Check test (James, 2026-10-22: printed black and white, scanned in colour at
600 dpi, pages a little crumpled). Lines from scripts/check_scan_crops.py. Version A has the colour-layer underline,
B the hatched one.

Per version, kind and size: the four engines' character error (each line brought to the benchmark's dpi, black and
white), and the checker: for each character, is there a grey band under it (digit) or not (letter), read from the
grey scan; a reading whose digits and letters disagree with the marks is flagged. Character places come from HarfBuzz
with the printed font, stretched to the line's ink, as an engine's character boxes would give them.

    python scripts/check_scan_score.py   -> out/report/check_scan.csv
    python scripts/check_scan_score.py --crops out/print_test/hatch_crops --fonts out/check_page/MaxOCR-Hatch{v}.ttf         --out out/report/hatch_scan            (James, 2026-10-23: the four hatch options B C D E)
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
FONTS = {"A": "out/fonts/MaxOCR-Check.ttf", "B": "out/fonts/MaxOCR-Hatch.ttf"}
INK = 130          # darker than this is ink; the scanned hatching never is (its darkest pixels are about 150)


def spans(font, text):
    """x range of each non-space character's outline, in font units from the first one's left edge."""
    import uharfbuzz as hb
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTFont
    tt = TTFont(font); gs = tt.getGlyphSet(); order = tt.getGlyphOrder()
    face = hb.Face(open(font, "rb").read()); hf = hb.Font(face)
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(hf, buf, {})                                  # browser defaults: calt on
    out, pen = [], 0
    for info, pos, ch in zip(buf.glyph_infos, buf.glyph_positions, text):
        if ch != " ":
            b = BoundsPen(gs); gs[order[info.codepoint]].draw(b)
            out.append((ch, pen + pos.x_offset + b.bounds[0], pen + pos.x_offset + b.bounds[2]))
        pen += pos.x_advance
    x0 = out[0][1]
    return [(c, a - x0, b - x0) for c, a, b in out]


def marks(grey, font, text):
    """Per character: 'B' (band under it), 'N' (none) or None (cannot tell)."""
    ink = grey < INK
    cols = np.where(ink.any(0))[0]
    sp = spans(font, text)
    k = (cols[-1] - cols[0]) / sp[-1][2]
    d = 255 - grey.astype(np.float32)
    out = []
    for ch, a, b in sp:
        x0, x1 = int(cols[0] + a * k) + 1, int(cols[0] + b * k) - 1
        rows = np.where((ink[:, x0:x1 + 1].sum(1)) >= 2)[0]
        if x1 <= x0 or not len(rows):
            out.append(None); continue
        y = rows[-1]                                       # the character's own bottom (a tail's, for g j p q y)
        # from 3 rows under the bottom (the scanned edge of the ink fades over 2 rows); columns where a neighbour's
        # ink reaches into the band (MaxOCR's digits sit lower than the letters) are left out
        clear = ~(ink[y + 1:y + 26, x0:x1 + 1].any(0))
        band = d[y + 3:y + 14, x0:x1 + 1][:, clear]
        paper = d[y + 16:y + 26, x0:x1 + 1][:, clear]
        if clear.sum() < 3 or band.shape[0] < 8 or paper.shape[0] < 5:
            out.append(None); continue
        v = band.mean(1).max() - float(np.median(paper))
        out.append("B" if v >= 20 else "N" if v <= 8 else None)
    return out


def cls(ch):
    return "B" if ch.isdigit() else "N"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crops", default="out/print_test/check_crops")
    ap.add_argument("--fonts", help="font path with {v} for the version (default: A Check, B Hatch)")
    ap.add_argument("--out", default="out/report/check_scan")
    a = ap.parse_args()
    import readme_bench as rb
    import rung0
    from text_eval import char_err, read_tesseract_dict
    from maxocr.corpus import GENERAL_ALPHABET
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**{**eng, "alphabet": GENERAL_ALPHABET + " "}), Parseq(**eng)
    index = json.load(open(f"{a.crops}/index.json"))
    fonts = {v: a.fonts.format(v=v) for v in sorted({it["version"] for it in index})} if a.fonts else FONTS
    rows, readings = [], []
    for v in fonts:
        for kind in ("codes", "numbers"):
            for size in (8, 10):
                items = [it for it in index if (it["version"], it["kind"], it["size"]) == (v, kind, size)]
                lines = [it["truth"] for it in items]
                greys = [np.array(Image.open(it["file"])) for it in items]
                small = [np.array(Image.fromarray(g).resize((round(g.shape[1] * rb.DPI / 600), round(g.shape[0] * rb.DPI / 600)),
                                                            Image.LANCZOS)).astype(np.float32) for g in greys]
                bws = [rb.otsu(np.pad(s, 6, constant_values=255)) for s in small]
                preds = {"paddle": [paddle.text(im) for im in bws], "easyocr": rb.in_batches(easy.texts, bws),
                         "parseq": rb.read_by_words(pq, bws), "tesseract": read_tesseract_dict(bws, fold=False)}
                m = [marks(g, fonts[v], t) for g, t in zip(greys, lines)]
                tot = sum(x is not None for mm in m for x in mm)
                ok = sum(x == cls(c) for mm, t in zip(m, lines) for x, c in zip(mm, t.replace(" ", "")))
                wrong = caught = right = false_alarm = 0
                for e, ps in preds.items():
                    for t, p, mm in zip(lines, ps, m):
                        tt, pp = t.replace(" ", ""), p.replace(" ", "")
                        readings.append({"version": v, "kind": kind, "size": size, "engine": e, "truth": t, "read": p,
                                         "marks": "".join(x or "?" for x in mm)})
                        seen = [x for x in mm if x is not None]
                        unmarked = any(c.isdigit() for c in pp) and "B" not in seen
                        flag = (not unmarked) and len(pp) == len(tt) and any(x is not None and x != cls(c) for c, x in zip(pp, mm))
                        if tt == pp:
                            right += 1; false_alarm += flag
                        else:
                            wrong += 1; caught += flag
                row = {"version": v, "text": kind, "size": size,
                       **{e: round(char_err(lines, p), 2) for e, p in preds.items()},
                       "error": round(float(np.mean([char_err(lines, p) for p in preds.values()])), 2),
                       "marks read %": round(100 * tot / sum(len(t.replace(" ", "")) for t in lines), 1),
                       "marks right %": round(100 * ok / max(1, tot), 1),
                       "misreads": wrong, "caught": caught, "right": right, "false alarms": false_alarm}
                rows.append(row); print(json.dumps(row), flush=True)
    pd.DataFrame(rows).to_csv(f"{a.out}.csv", index=False)
    with open(f"{a.out}_readings.jsonl", "w") as f:
        for r in readings:
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
