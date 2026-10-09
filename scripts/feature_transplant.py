"""Feature transplants: put one distinguishing idea at a time into the optimized amalgam, changing only
the 0 and/or the O, so an isolation test (scripts/isolation_eval.py --fonts-json) measures the idea
itself rather than a whole different font. Ideas come from fonts James tried on "BO0K":
  stencil  - gaps cut through the ring (O split vertically, 0 cut on the diagonal);
  curl     - script-style O with an entry curl and ball terminal inside the counter (marks the letter);
  oldstyle - short 0 at about x-height (old-style figures);
  squared  - superellipse ring (pixel / square fonts) for one of the pair, the other stays round;
  inverted - white 0 on a black disk (negative circled digit);
  faceted  - blackletter 'broken' curves: the 0 as a hexagon with flat sides (also short, as in Fraktur).
All added strokes, cuts and dots respect the discovery minimum feature size (strokes.MIN_W).

    python scripts/feature_transplant.py [--dial]
Writes fonts to ~/maxocr-work/transplant/, out/transplant/fonts.json and out/transplant/sheet.png.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from maxocr.render import render
from maxocr.strokes import MIN_W, Genome, Part, from_glyph, with_glyphs

ROOT = Path(__file__).resolve().parents[1]
OUT = Path.home() / "maxocr-work" / "transplant"


def box(pts: np.ndarray) -> tuple[float, float, float, float]:
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


def outer(g: Genome) -> Part:
    return max((p for p in g.parts if p.sign > 0 and p.kind == "contour"), key=lambda p: np.ptp(p.pts[:, 1]))


def counter(g: Genome) -> Part:
    return max((p for p in g.parts if p.sign < 0 and p.kind == "contour"), key=lambda p: np.ptp(p.pts[:, 1]))


def stroke(sign: int, pts, w0: float, w1: float | None = None) -> Part:
    return Part("stroke", sign, np.asarray(pts, float), w0, w0 if w1 is None else w1)


def dot(c, r: float) -> Part:
    c = np.asarray(c, float)
    return stroke(1, [c, c + [1e-3, 0], c + [2e-3, 0]], 2 * r)


def stencil_zero(g: Genome, w: float = 0.12) -> Genome:
    g = g.copy()
    x0, y0, x1, y1 = box(outer(g).pts)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d = np.array([(x1 - x0) * 0.5, (y1 - y0) * 0.5]) * 1.15
    g.parts.append(stroke(-1, [[cx + d[0], cy + d[1]], [cx, cy], [cx - d[0], cy - d[1]]], w))
    return g


def stencil_letter_o(g: Genome, w: float = 0.12) -> Genome:
    g = g.copy()
    x0, y0, x1, y1 = box(outer(g).pts)
    cx = (x0 + x1) / 2
    g.parts.append(stroke(-1, [[cx, y0 - 0.1], [cx, 0.5], [cx, y1 + 0.1]], w))
    return g


def curl(g: Genome) -> Genome:
    """Entry curl from the top of the ring, hooking down-left into the counter, ending in a ball."""
    g = g.copy()
    x0, y0, x1, y1 = box(counter(g).pts)
    cw, ch = x1 - x0, y1 - y0
    cx = (x0 + x1) / 2
    pts = [[cx + 0.10 * cw, y1 + 0.04], [cx - 0.05 * cw, y1 - 0.10 * ch], [cx - 0.12 * cw, y1 - 0.24 * ch]]
    g.parts.append(stroke(1, pts, MIN_W, 0.13))
    g.parts.append(dot(pts[-1], 0.085))
    return g


def oldstyle(g: Genome, ky: float = 0.70, kx: float = 0.92) -> Genome:
    g = g.copy()
    x0, _, x1, _ = box(outer(g).pts)
    cx = (x0 + x1) / 2
    for p in g.parts:
        p.pts[:, 0] = cx + (p.pts[:, 0] - cx) * kx
        p.pts[:, 1] = p.pts[:, 1] * ky
    return g


def squared(g: Genome, n: float = 4.0) -> Genome:
    """Push every contour toward a superellipse of exponent n, each about its own box."""
    g = g.copy()
    for p in g.parts:
        if p.kind != "contour":
            continue
        x0, y0, x1, y1 = box(p.pts)
        c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
        ab = np.array([(x1 - x0) / 2, (y1 - y0) / 2])
        uv = (p.pts - c) / ab
        th = np.arctan2(uv[:, 1], uv[:, 0])
        k = 1 / (np.abs(np.cos(th)) ** n + np.abs(np.sin(th)) ** n) ** (1 / n)
        p.pts = c + uv * k[:, None] * ab
    return g


def faceted(g: Genome, k: int = 6, per_edge: int = 8) -> Genome:
    """Blackletter 'broken' curves: every contour becomes a k-gon with points at the top and bottom
    and flat sides, sampled densely along each edge so the spline keeps the edges straight."""
    g = g.copy()
    for p in g.parts:
        if p.kind != "contour":
            continue
        c = p.pts.mean(0)
        ang = np.arctan2(*(p.pts - c)[:, ::-1].T)
        verts = []
        for a in np.pi / 2 - 2 * np.pi * np.arange(k) / k:          # clockwise from the top
            d = np.angle(np.exp(1j * (ang - a)))
            verts.append(p.pts[np.argmin(np.abs(d))])
        v = np.array(verts)
        t = np.linspace(0, 1, per_edge, endpoint=False)[:, None]
        p.pts = np.vstack([v[i] + t * (v[(i + 1) % k] - v[i]) for i in range(k)])
    return g


def inverted(g0: Genome) -> Genome:
    """Black disk the size of the 0, with a white 0 (stroke >= MIN_W) cut out of it."""
    x0, y0, x1, y1 = box(outer(g0).pts)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = max((x1 - x0) / 2, 0.42), (y1 - y0) / 2 + 0.02
    t = np.linspace(0, 2 * np.pi, 32, endpoint=False)
    ell = lambda a, b: np.c_[cx + a * np.cos(t), cy + b * np.sin(t)]  # noqa: E731
    sw = 0.11
    return Genome([Part("contour", 1, ell(rx, ry)),
                   Part("contour", -1, ell(0.42 * rx, 0.62 * ry)),
                   Part("contour", 1, ell(0.42 * rx - sw, 0.62 * ry - sw))])


def sheet(fonts: dict[str, str], path: Path):
    rows = []
    for name, p in fonts.items():
        img = render(p, "BO0K 4KOTWX7 1O20", size_pt=24, dpi=200)
        rows.append((name, img))
    W = max(im.shape[1] for _, im in rows) + 340
    H = sum(im.shape[0] + 16 for _, im in rows)
    canvas = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(canvas)
    y = 0
    for name, im in rows:
        d.text((8, y + im.shape[0] // 2 - 6), name, fill=0)
        canvas.paste(Image.fromarray(im), (330, y))
        y += im.shape[0] + 16
    canvas.save(path)


def dial():
    """Short-0 height dial, on the control and on discovery run 3's #2 design (wide O)."""
    base = json.loads((ROOT / "out" / "amalgam_opt" / "08BDEOQ" / "elite.json").read_text())["font"]
    run3 = json.loads((ROOT / "out" / "discover" / "0O" / "archive.json").read_text())[1]["font"]
    fonts = {}
    for tag, src, heights in (("control", base, (0.78, 0.86)), ("run 3 #2", run3, (0.70, 0.78, 0.86))):
        zero = from_glyph(src, "0", 48)
        for ky in heights:
            path = OUT / f"dial_{'c' if tag == 'control' else 'r'}{int(ky * 100)}.ttf"
            fonts[f"{tag} + 0 at {ky:.2f} height"] = with_glyphs(src, {"0": oldstyle(zero, ky, 1 - 0.27 * (1 - ky))},
                                                                 str(path))
    d = ROOT / "out" / "transplant"
    (d / "dial.json").write_text(json.dumps(fonts, indent=1))
    sheet(fonts, d / "dial_sheet.png")
    print(json.dumps(fonts, indent=1))


def main():
    if "--dial" in sys.argv:
        return dial()
    base = json.loads((ROOT / "out" / "amalgam_opt" / "08BDEOQ" / "elite.json").read_text())["font"]
    OUT.mkdir(parents=True, exist_ok=True)
    zero, oh = from_glyph(base, "0", 48), from_glyph(base, "O", 48)
    variants = {
        "stencil 0 (diagonal gap)": {"0": stencil_zero(zero)},
        "stencil O + 0": {"0": stencil_zero(zero), "O": stencil_letter_o(oh)},
        "curl O (script)": {"O": curl(oh)},
        "old-style 0 (short)": {"0": oldstyle(zero)},
        "old-style 0 + curl O": {"0": oldstyle(zero), "O": curl(oh)},
        "squared 0": {"0": squared(zero)},
        "squared O": {"O": squared(oh)},
        "inverted 0 (white on disk)": {"0": inverted(zero)},
        "inverted 0 + curl O": {"0": inverted(zero), "O": curl(oh)},
        "faceted 0 (blackletter)": {"0": faceted(zero)},
        "faceted short 0 (blackletter old-style)": {"0": faceted(oldstyle(zero))},
    }
    fonts = {"amalgam (control)": base}
    for k, (name, gl) in enumerate(variants.items()):
        fonts[name] = with_glyphs(base, gl, str(OUT / f"t{k:02d}.ttf"))
    d = ROOT / "out" / "transplant"
    d.mkdir(parents=True, exist_ok=True)
    (d / "fonts.json").write_text(json.dumps(fonts, indent=1))
    sheet(fonts, d / "sheet.png")
    print(json.dumps(fonts, indent=1))


if __name__ == "__main__":
    main()
