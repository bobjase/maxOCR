"""Print-and-scan test sheet (James, 2026-10-13): one US Letter page per font, the same text on every page, set at
8 pt with equal capital height as in the README benchmark, drawn at 600 dpi with the benchmark's renderer
(FreeType + HarfBuzz, so MaxOCR's letter-digit kerning applies). Print at 100% (no "fit to page"), scan, and the
scans can be read and scored against out/print_test/truth.json.

    python scripts/print_test.py        (writes out/print_test/print_test.pdf and truth.json)
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readme_bench import FONTS, texts  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402
from maxocr.prose import story_lines  # noqa: E402
from maxocr.render import render  # noqa: E402

DPI = 600
W, H = int(8.5 * DPI), int(11 * DPI)
MARGIN = int(0.6 * DPI)
PAGE_FONTS = ["MaxOCR", "Courier New", "Courier Prime", "Arial", "Times New Roman", "Georgia", "Calibri", "Verdana"]
LABEL = FONTS["Arial"]


def paste(page, img, x, y):
    page.paste(Image.fromarray(img), (x, y))
    return img.shape[0]


def main():
    out = Path(__file__).resolve().parents[1] / "out" / "print_test"
    out.mkdir(parents=True, exist_ok=True)
    t = texts(30)
    blocks = {"paragraphs": story_lines(44)[:20], "codes": t["codes"][:14], "numbers": t["numbers"][:14]}
    pages, truth = [], {"note": "8 pt, equal capital height, 600 dpi; print at 100%", "pages": []}
    for i, name in enumerate(PAGE_FONTS, 1):
        path = FONTS[name]
        size = matched_size(path, 8.0)
        page = Image.new("L", (W, H), 255)
        y = MARGIN
        y += paste(page, render(LABEL, f"Page {i}: {name}  ({size:.2f} pt)", 9, DPI), MARGIN, y) + int(0.12 * DPI)
        for kind, lines in blocks.items():
            y += paste(page, render(LABEL, kind.upper(), 7, DPI), MARGIN, y) + int(0.05 * DPI)
            for line in lines:
                paste(page, render(path, line, size, DPI), MARGIN, y)
                y += int(8 / 72 * DPI * 1.6)
            y += int(0.15 * DPI)
        assert y < H - MARGIN, f"page {i} overflows"
        pages.append(page)
        truth["pages"].append({"page": i, "font": name, "size_pt": size, **blocks})
    pages[0].resize((W // 4, H // 4)).save(out / "page1_preview.png")
    pages[0].save(out / "print_test.pdf", save_all=True, append_images=pages[1:], resolution=DPI)
    json.dump(truth, open(out / "truth.json", "w"), indent=1)
    print(out / "print_test.pdf", len(pages), "pages")


if __name__ == "__main__":
    main()
