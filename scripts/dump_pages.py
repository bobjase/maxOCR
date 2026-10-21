"""Pages for engines that read whole pages (Windows OCR, Google Cloud Vision; 2026-10-21): for every README font, kind of
text and condition, the first N benchmark lines (exactly the images the other engines get) stacked on one page with gaps,
plus a JSON of each line's truth and vertical span, so recognised words can be put back on their lines.

    python scripts/dump_pages.py --n 100 --out out/pages
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from readme_bench import CONDITIONS, EXTRA, FONTS, image, texts  # noqa: E402

GAP, MARGIN = 36, 40


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", default="out/pages")
    ap.add_argument("--fonts", help="comma-separated subset")
    ap.add_argument("--conds", help="comma-separated conditions (default: the nine plus thermal, dot-matrix, phone photo)")
    a = ap.parse_args()
    from maxocr.fonts import matched_size
    sets = texts(300)
    fonts = {k: v for k, v in FONTS.items() if not a.fonts or k in a.fonts.split(",")}
    for name, path in fonts.items():
        size = matched_size(path, 8.0)
        d = os.path.join(a.out, name.replace(" ", "_")); os.makedirs(d, exist_ok=True)
        for cond in (a.conds.split(",") if a.conds else list(CONDITIONS) + ["thermal", "dot-matrix", "phone photo"]):
            for kind in ("paragraphs", "codes", "numbers"):
                f = os.path.join(d, f"{kind}_{cond.replace(' ', '-')}.png")
                if os.path.exists(f):
                    continue
                lines = sets[kind][:a.n]
                ims = [image(path, t, size, cond, k).astype(np.uint8) for k, t in enumerate(lines)]
                W = max(im.shape[1] for im in ims) + 2 * MARGIN
                H = sum(im.shape[0] for im in ims) + GAP * (len(ims) - 1) + 2 * MARGIN
                page = np.full((H, W), 255, np.uint8); y = MARGIN; spans = []
                for im, t in zip(ims, lines):
                    page[y:y + im.shape[0], MARGIN:MARGIN + im.shape[1]] = im
                    spans.append({"truth": t, "y0": y, "y1": y + im.shape[0]}); y += im.shape[0] + GAP
                cv2.imwrite(f, page)
                json.dump(spans, open(f[:-4] + ".json", "w"))
        print(name, flush=True)


if __name__ == "__main__":
    main()
