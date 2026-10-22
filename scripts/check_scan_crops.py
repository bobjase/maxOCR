"""Cut the scanned MaxOCR Check test (out/print_test/check_scan_p1..4.png, 600 dpi) into lines and pair each with its
truth (out/check_page/truth.json): per page and column, rows of ink merged across small gaps (the underlines), in reading
order; pages 1-2 are version A (colour layer), 3-4 version B (hatched); each version: header, 40 codes at 8 pt, header,
40 numbers at 8 pt, header, 40 codes at 10 pt, header, 40 numbers at 10 pt.

    python scripts/check_scan_crops.py    -> out/print_test/check_crops/*.png, index.json
"""
import json
import os

import numpy as np
from PIL import Image

OUT = "out/print_test/check_crops"


def lines(im):
    h, w = im.shape
    found = []
    for x0, x1 in ((0, w // 2), (w // 2, w)):
        rows = (im[:, x0:x1] < 150).sum(1) > 3
        runs, y = [], 0
        while y < h:
            if rows[y]:
                a = y
                while y < h and rows[y]:
                    y += 1
                runs.append((a, y))
            y += 1
        merged = []
        for r in runs:
            if merged and r[0] - merged[-1][1] < 10:
                merged[-1] = (merged[-1][0], r[1])
            else:
                merged.append(r)
        for a, b in merged:
            if 15 < b - a < 110:          # taller is the page title
                cols = np.where((im[a:b, x0:x1] < 150).any(0))[0]
                found.append((a, b, x0 + cols.min(), x0 + cols.max()))
    return found


def main():
    truth = json.load(open("out/check_page/truth.json"))
    seq = [None] + [("codes", 8, t) for t in truth["codes"]] + [None] + [("numbers", 8, t) for t in truth["numbers"]] + \
          [None] + [("codes", 10, t) for t in truth["codes"]] + [None] + [("numbers", 10, t) for t in truth["numbers"]]
    os.makedirs(OUT, exist_ok=True)
    index = []
    for version, pages in (("A", (1, 2)), ("B", (3, 4))):
        found = []
        for p in pages:
            im = np.array(Image.open(f"out/print_test/check_scan_p{p}.png")).astype(np.float32)
            found += [(im, *f) for f in lines(im)]
        print(version, len(found), "lines found,", len(seq), "expected")
        if len(found) != len(seq):
            continue
        for k, ((im, a, b, x0, x1), item) in enumerate(zip(found, seq)):
            if item is None:
                continue
            kind, size, text = item
            crop = im[max(0, a - 20):b + 30, max(0, x0 - 20):x1 + 20]
            f = f"{OUT}/{version}_{k:03d}.png"
            Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8)).save(f)
            index.append({"file": f, "version": version, "kind": kind, "size": size, "truth": text})
    json.dump(index, open(f"{OUT}/index.json", "w"), indent=0)
    print(len(index), "crops")


if __name__ == "__main__":
    main()
