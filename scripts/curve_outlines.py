"""Real curves for every glyph. The blend pipeline (maxocr/blend.py) traces blended bitmaps back into outlines made
only of short straight segments (300-600 corner points per letter, no curve points), so enlarged curves show flats
(James, 2026-10-12: "the left of the e looks cut flat"). Each glyph is rendered at one pixel per font unit, traced
with potrace (smooth Bezier curves, corners kept where the outline really turns sharply), converted to TrueType
quadratic curves (cu2qu) and written back with the same advance; contour direction follows TrueType (outer
clockwise, holes counter-clockwise).

    python scripts/curve_outlines.py SRC.ttf DST.ttf [--chars ...] [--alphamax 1.0] [--tolerance 0.2] [--blur 6]
--blur smooths the shape before tracing, so facets and wobbles of the traced-bitmap outlines melt away.
"""
import argparse
import string

import freetype
import numpy as np
import potrace
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from scipy.ndimage import binary_closing, binary_opening, gaussian_filter

DEFAULT_CHARS = string.digits + string.ascii_letters + string.punctuation


def _polyline_pts(curve) -> list:
    """Rough polygon of a potrace curve (control points included), for nesting tests only."""
    pts = [curve.start_point]
    for s in curve.segments:
        pts += [s.c, s.end_point] if s.is_corner else [s.c1, s.c2, s.end_point]
    return pts


def _inside(pt, poly) -> bool:
    x, y = pt
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _area(poly) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1])) / 2


def _disc(r: int) -> np.ndarray:
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def trace_glyph(face, gid: int, alphamax: float, tolerance: float, blur: float = 0.0, close: int = 0, open_: int = 0):
    """Contours of one glyph in font units: list of (start, segments) with segments as potrace gives them,
    mapped from bitmap pixels (y down) to font units (y up)."""
    face.load_glyph(gid, freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_NO_BITMAP | freetype.FT_LOAD_RENDER)
    bmp = face.glyph.bitmap
    if not (bmp.width and bmp.rows):
        return []
    img = np.array(bmp.buffer, dtype=np.uint8).reshape(bmp.rows, bmp.pitch)[:, :bmp.width]
    left, top = face.glyph.bitmap_left, face.glyph.bitmap_top
    if close or open_:   # fill notches narrower than 2*close, shave bumps narrower than 2*open (font units)
        pad = max(close, open_) + 2
        ink = np.pad(img >= 128, pad)
        if close:
            ink = binary_closing(ink, _disc(close))
        if open_:
            ink = binary_opening(ink, _disc(open_))
        img = ink.astype(np.uint8) * 255
        left, top = left - pad, top + pad
    if blur > 0:   # melt facets and wobbles (font units = pixels); real corners keep most of their shape
        pad = int(3 * blur) + 2
        img = np.pad(img, pad)
        img = gaussian_filter(img.astype(np.float32), blur)
        left, top = left - pad, top + pad
    path = potrace.Bitmap(img < 128).trace(   # potracer fills the dark (False) pixels
        turdsize=4, alphamax=alphamax, opticurve=True, opttolerance=tolerance)

    def fu(p):
        x, y = (p.x, p.y) if hasattr(p, "x") else (p[0], p[1])
        return (left + x, top - y)

    out = []
    for curve in path:
        segs = []
        for s in curve.segments:
            if s.is_corner:
                segs.append(("corner", fu(s.c), fu(s.end_point)))
            else:
                segs.append(("bezier", fu(s.c1), fu(s.c2), fu(s.end_point)))
        out.append((fu(curve.start_point), segs, [fu(p) for p in _polyline_pts(curve)]))
    return out


def draw(contours, pen):
    """Draw contours with TrueType orientation: even nesting depth (outer) clockwise, odd (holes) counter-clockwise."""
    polys = [c[2] for c in contours]
    for k, (start, segs, poly) in enumerate(contours):
        depth = sum(_inside(poly[0], q) for j, q in enumerate(polys) if j != k)
        clockwise = depth % 2 == 0
        if (_area(poly) < 0) != clockwise:      # y-up: clockwise has negative signed area
            start, segs = _reverse(start, segs)
        pen.moveTo(start)
        for s in segs:
            if s[0] == "corner":
                pen.lineTo(s[1])
                pen.lineTo(s[2])
            else:
                pen.curveTo(s[1], s[2], s[3])
        pen.closePath()


def _reverse(start, segs):
    """The same closed path traversed the other way."""
    pts = [start]
    for s in segs:
        pts.append(s[-1])
    new_segs, cur = [], pts[-1]
    for i in range(len(segs) - 1, -1, -1):
        s, prev_end = segs[i], pts[i]
        if s[0] == "corner":
            new_segs.append(("corner", s[1], prev_end))
        else:
            new_segs.append(("bezier", s[2], s[1], prev_end))
    return cur, new_segs


def curve_font(src: str, dst: str, chars: str = DEFAULT_CHARS, alphamax: float = 1.0, tolerance: float = 0.2,
               blur: float = 0.0, close: int = 0, open_: int = 0) -> dict:
    f = TTFont(src)
    upem = f["head"].unitsPerEm
    face = freetype.Face(src)
    face.set_pixel_sizes(0, upem)          # one pixel per font unit
    cmap = f.getBestCmap()
    order = {n: i for i, n in enumerate(f.getGlyphOrder())}
    stats = {}
    for c in chars:
        name = cmap.get(ord(c))
        if name is None or f["glyf"][name].numberOfContours <= 0:
            continue
        before = len(f["glyf"][name].getCoordinates(f["glyf"])[0])
        contours = trace_glyph(face, face.get_char_index(ord(c)), alphamax, tolerance, blur, close, open_)
        if not contours:
            continue
        tt = TTGlyphPen(None)
        draw(contours, Cu2QuPen(tt, max_err=1.0, reverse_direction=False))
        g = tt.glyph()
        g.recalcBounds(f["glyf"])
        adv, _ = f["hmtx"][name]
        f["glyf"][name] = g
        f["hmtx"][name] = (adv, g.xMin)
        stats[c] = (before, len(g.getCoordinates(f["glyf"])[0]))
    f.save(dst)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--chars", default=DEFAULT_CHARS)
    ap.add_argument("--alphamax", type=float, default=1.0, help="potrace corner threshold (higher = smoother)")
    ap.add_argument("--tolerance", type=float, default=0.2, help="potrace curve optimisation tolerance")
    ap.add_argument("--blur", type=float, default=0.0, help="Gaussian blur (font units) before tracing: smooths flats")
    ap.add_argument("--close", type=int, default=0, help="fill notches narrower than 2x this (font units)")
    ap.add_argument("--open", type=int, default=0, dest="open_", help="shave bumps narrower than 2x this (font units)")
    a = ap.parse_args()
    s = curve_font(a.src, a.dst, a.chars, a.alphamax, a.tolerance, a.blur, a.close, a.open_)
    print({c: f"{b}->{n}" for c, (b, n) in list(s.items())[:12]}, "...", len(s), "glyphs")


if __name__ == "__main__":
    main()
