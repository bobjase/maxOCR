"""Score a scanned print test (James, 2026-10-13): out/print_test/scan_p<N>.png (page images from the scanner) against
out/print_test/truth.json. Text lines are found by row profile (header, three section labels, then the lines in
order), each line is brought to the benchmark's 200 dpi, converted to black and white (Otsu) and read by the four
engines; character error per page and kind of text.

    python scripts/score_scans.py [--dpi 600]       writes out/print_test/scan_scores.csv and .md
"""
import argparse
import glob
import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readme_bench import in_batches, otsu  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "out" / "print_test"


def rows(img: np.ndarray, merge: int) -> list[tuple[int, int]]:
    clean = cv2.morphologyEx((img < 128).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ink = clean.sum(1) >= 8                      # a row needs real ink, not scanner specks
    runs, y = [], 0
    while y < len(ink):
        if ink[y]:
            y0 = y
            while y < len(ink) and ink[y]:
                y += 1
            if runs and y0 - runs[-1][1] < merge:
                runs[-1] = (runs[-1][0], y)
            else:
                runs.append((y0, y))
        y += 1
    return [r for r in runs if r[1] - r[0] > 3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpi", type=int, default=600)
    a = ap.parse_args()
    truth = {p["page"]: p for p in json.load(open(OUT / "truth.json"))["pages"]}
    import rung0
    from text_eval import char_err, read_tesseract_dict
    from maxocr.corpus import GENERAL_ALPHABET
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    k = a.dpi / 200
    results = []
    readings = open(OUT / "scan_readings.jsonl", "w")
    for f in sorted([g for g in glob.glob(str(OUT / "scan_p*.png")) if re.fullmatch(r"scan_p\d+\.png", Path(g).name)], key=lambda s: int(re.findall(r"\d+", Path(s).name)[0])):
        n = int(re.findall(r"\d+", Path(f).name)[0])
        t = truth[n]
        img = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        img[:, : int(0.3 * a.dpi)] = 255          # scanner edge
        img[:, -int(0.3 * a.dpi):] = 255
        img[-int(0.3 * a.dpi):] = 255
        # where every line was printed (scripts/print_test.py layout, points from the top of the page), fitted to the
        # scan: the header's top and the last line's bottom fix the offset and scale (printers and scanners shrink a
        # little), then each expected line snaps to the nearest row of ink found on the scan
        px = a.dpi / 72
        found = rows(img, merge=int(0.02 * a.dpi))
        expect, base = [], 0.6 * 72 + 9 + 22
        for kind in ("paragraphs", "codes", "numbers"):
            base += 13
            expect += [(kind, j, base + 12 * j) for j in range(len(t[kind]))]
            base += 12 * len(t[kind]) + 10
        top_pt, last_pt = 0.6 * 72 + 9 - 9 * 0.716, expect[-1][2]
        scale = (found[-1][1] - found[0][0]) / ((last_pt + 2.5 - top_pt) * px)
        shift = found[0][0] - top_pt * px * scale
        centers = np.array([(y0 + y1) / 2 for y0, y1 in found])
        crops_by = {kind: [] for kind in ("paragraphs", "codes", "numbers")}
        for kind, j, b_pt in expect:
            yb = int(shift + b_pt * px * scale)                  # the line's baseline on the scan
            # a window a full line tall around the expected line, then only this line's own ink rows: the run with
            # the most ink (x-height band) plus anything touching it (capitals, ascenders, descenders of g y p),
            # without slivers of the lines above and below (an earlier, tighter crop cut the tails off g and y)
            win = img[yb - int(11 * px): yb + int(7 * px)]
            rowink = cv2.morphologyEx((win < 128).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).sum(1)
            on = rowink > 0
            # the line itself sits at the middle of its x-height, about 1 pt above its real baseline, which is about
            # 3.5 pt below the layout estimate (measured on the first scans): pick the ink run nearest to there
            target = int((11 + 2.5) * px)
            ink_rows = np.where(on)[0]
            core = int(ink_rows[np.argmin(np.abs(ink_rows - target))])
            r0 = core
            while r0 > 0 and on[r0 - 1]:
                r0 -= 1
            r1 = core
            while r1 < len(on) - 1 and on[r1 + 1]:
                r1 += 1
            band = win[max(0, r0 - 6): r1 + 7]
            ink = cv2.morphologyEx((band < 128).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            colsum = ink.sum(0)
            cols = np.where(colsum > 0)[0]
            # the text is one run of columns; specks far from it (more than an inch of paper away) are dropped
            gaps = np.where(np.diff(cols) > a.dpi)[0]
            if len(gaps):
                cols = cols[: gaps[0] + 1]
            band = band[:, max(0, cols[0] - 10): cols[-1] + 10]
            small = cv2.resize(band, (int(band.shape[1] / k), int(band.shape[0] / k)), interpolation=cv2.INTER_AREA)
            crops_by[kind].append(otsu(np.pad(small, 6, constant_values=255).astype(np.float32)))
        if n == 1:
            for kind, cs in crops_by.items():
                cv2.imwrite(str(OUT / f"debug_{kind}_0.png"), cs[0]); cv2.imwrite(str(OUT / f"debug_{kind}_last.png"), cs[-1])
        print(f"page {n}: scale {scale:.4f}, {len(found)} ink rows", flush=True)
        for kind in ("paragraphs", "codes", "numbers"):
            lines, crops = t[kind], crops_by[kind]
            preds = {"paddle": [paddle.text(im) for im in crops], "easyocr": in_batches(easy.texts, crops),
                     "parseq": in_batches(pq.read, crops), "tesseract": read_tesseract_dict(crops, fold=False)}
            for e, ps in preds.items():
                for j, (tl, pl) in enumerate(zip(lines, ps)):
                    readings.write(json.dumps({"page": n, "font": t["font"], "text": kind, "engine": e, "line": j,
                                               "truth": tl, "read": pl}) + "\n")
            row = {"page": n, "font": t["font"], "text": kind, **{e: round(char_err(lines, p), 2) for e, p in preds.items()}}
            row["mean"] = round(float(np.mean([row[e] for e in preds])), 2)
            results.append(row)
            print(json.dumps(row), flush=True)
    df = pd.DataFrame(results)
    df.to_csv(OUT / "scan_scores.csv", index=False)
    piv = df.pivot(index="font", columns="text", values="mean")[["paragraphs", "codes", "numbers"]]
    piv["all"] = piv.mean(axis=1)
    piv = piv.sort_values("all")
    md = ["# Print-and-scan test", "", "Character error %, lower is better; four engines.", "",
          "| Font | Paragraphs | Codes | Numbers | All |", "|---|---:|---:|---:|---:|"]
    md += [f"| {f} | {r.paragraphs:.2f} | {r.codes:.2f} | {r.numbers:.2f} | {r['all']:.2f} |" for f, r in piv.iterrows()]
    (OUT / "scan_scores.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(piv.round(2).to_string())


if __name__ == "__main__":
    main()
