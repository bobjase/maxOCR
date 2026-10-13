"""Print-and-scan test sheet (James, 2026-10-13): one US Letter page per font, the same text on every page, set at
8 pt with equal capital height as in the README benchmark. Vector PDF ("a png scales badly"): every glyph is the
font's own outline, placed where HarfBuzz puts it (as the benchmark's renderer does, so MaxOCR's letter-digit
kerning applies). Print at 100% (no "fit to page"), scan, and the
scans can be read and scored against out/print_test/truth.json.

    python scripts/print_test.py        (writes out/print_test/print_test.pdf and truth.json)
"""
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from readme_bench import FONTS, texts  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402
from maxocr.prose import story_lines  # noqa: E402

import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath

W, H = 8.5 * 72, 11 * 72          # points
MARGIN = 0.6 * 72
PAGE_FONTS = ["MaxOCR", "Courier New", "Courier Prime", "Arial", "Times New Roman", "Georgia", "Calibri", "Verdana"]
LABEL = FONTS["Arial"]


class _Pen(BasePen):
    def __init__(self, gs, dx, dy, k):
        super().__init__(gs); self.v, self.c, self.t = [], [], (dx, dy, k)
    def _p(self, p):
        dx, dy, k = self.t; return (dx + p[0] * k, dy + p[1] * k)
    def _moveTo(self, p): self.v.append(self._p(p)); self.c.append(MPath.MOVETO)
    def _lineTo(self, p): self.v.append(self._p(p)); self.c.append(MPath.LINETO)
    def _curveToOne(self, a, b, p):
        self.v += [self._p(a), self._p(b), self._p(p)]; self.c += [MPath.CURVE4] * 3
    def _qCurveToOne(self, a, p):
        self.v += [self._p(a), self._p(p)]; self.c += [MPath.CURVE3] * 2
    def _closePath(self): self.v.append((0, 0)); self.c.append(MPath.CLOSEPOLY)


_cache = {}


def _font(path):
    if path not in _cache:
        data = open(path, "rb").read()
        f = TTFont(path)
        _cache[path] = (hb.Font(hb.Face(data)), f.getGlyphSet(), f.getGlyphOrder(), f["head"].unitsPerEm)
    return _cache[path]


def draw(fig, path, text, size, x, y):
    """Text as filled glyph outlines at (x, y) points from the bottom left (baseline)."""
    hbf, gs, order, upm = _font(path)
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(hbf, buf, {"liga": False})
    k = size / upm
    pen_x = x
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = _Pen(gs, pen_x + pos.x_offset * k, y + pos.y_offset * k, k)
        gs[order[info.codepoint]].draw(pen)
        if pen.v:
            fig.add_artist(PathPatch(MPath(pen.v, pen.c), transform=fig.dpi_scale_trans + _pt, facecolor="black",
                                     edgecolor="none"))
        pen_x += pos.x_advance * k


from matplotlib.transforms import Affine2D  # noqa: E402
_pt = None


def main():
    global _pt
    out = Path(__file__).resolve().parents[1] / "out" / "print_test"
    out.mkdir(parents=True, exist_ok=True)
    t = texts(30)
    blocks = {"paragraphs": story_lines(44)[:20], "codes": t["codes"][:14], "numbers": t["numbers"][:14]}
    truth = {"note": "8 pt, equal capital height, vector; print at 100%", "pages": []}
    step = 8 * 1.5
    with PdfPages(out / "print_test.pdf") as pdf:
        for i, name in enumerate(PAGE_FONTS, 1):
            path = FONTS[name]
            size = matched_size(path, 8.0)
            fig = Figure(figsize=(8.5, 11))
            _pt = Affine2D().scale(1 / 72)          # points -> inches, then the figure's inch transform
            y = H - MARGIN - 9
            draw(fig, LABEL, f"Page {i}: {name}  ({size:.2f} pt)", 9, MARGIN, y)
            y -= 22
            for kind, lines in blocks.items():
                draw(fig, LABEL, kind.upper(), 7, MARGIN, y)
                y -= 13
                for line in lines:
                    draw(fig, path, line, size, MARGIN, y)
                    y -= step
                y -= 10
            assert y > MARGIN, f"page {i} overflows"
            pdf.savefig(fig)
            truth["pages"].append({"page": i, "font": name, "size_pt": size, **blocks})
    json.dump(truth, open(out / "truth.json", "w"), indent=1)
    print(out / "print_test.pdf", len(PAGE_FONTS), "pages")


if __name__ == "__main__":
    main()
