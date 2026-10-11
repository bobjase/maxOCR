"""Consistent lowercase heights: glyphs borrowed or blended from other fonts keep their source's x-height, so
letters like r (Cousine) stand taller than o (serif blend). Each lowercase glyph is scaled uniformly (shape and
proportions kept; sidebearings kept, advance adjusted) so its top matches the same glyph in a reference font
whose lowercase is one consistent design (the equal serif blend): x-height letters, overshoots of round letters,
ascenders and the t all follow the reference. For i and j the stem top is matched, not the dot.

    python scripts/normalize_xheight.py SRC.ttf REF.ttf DST.ttf [--chars abc...] [--tall]
"""
import argparse

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

LOWER = "abcdefghijklmnopqrstuvwxyz"


def body_top(f: TTFont, name: str, ch: str) -> float:
    """Top of the glyph; for i and j the top of the largest contour (the stem), not the dot."""
    g = f["glyf"][name]
    if ch not in "ij":
        return g.yMax
    coords, ends, _ = g.getCoordinates(f["glyf"])
    best, start = None, 0
    for e in ends:
        pts = coords[start:e + 1]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if best is None or area > best[0]:
            best = (area, max(ys))
        start = e + 1
    return best[1]


def tall_factor(src: str, ref: str, chars: str = "agnrsxz") -> float:
    """Median ratio current/reference of top heights over letters borrowed from tall-x-height fonts."""
    f, r = TTFont(src), TTFont(ref)
    cf, cr = f.getBestCmap(), r.getBestCmap()
    ratios = sorted(body_top(f, cf[ord(c)], c) / body_top(r, cr[ord(c)], c) for c in chars)
    return ratios[len(ratios) // 2]


def normalize(src: str, ref: str, dst: str, chars: str = LOWER, k: float = 1.0, match_width: bool = False) -> dict:
    f, r = TTFont(src), TTFont(ref)
    cf, cr = f.getBestCmap(), r.getBestCmap()
    gs = f.getGlyphSet()
    scales = {}
    for ch in chars:
        name = cf[ord(ch)]
        g = f["glyf"][name]
        g.recalcBounds(f["glyf"])
        top, target = body_top(f, name, ch), k * body_top(r, cr[ord(ch)], ch)
        s = target / top
        x0, x1 = g.xMin, g.xMax
        sx = s
        if match_width:
            rg = r["glyf"][cr[ord(ch)]]
            sx = k * (rg.xMax - rg.xMin) / max(x1 - x0, 1)   # the reference's proportions, at the same scale
        scales[ch] = (round(sx, 3), round(s, 3))
        if abs(s - 1) < 0.005 and abs(sx - 1) < 0.005:
            continue
        adv, lsb = f["hmtx"][name]
        rsb = adv - x1
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(rec)
        pen = TTGlyphPen(None)
        rec.replay(TransformPen(pen, (sx, 0, 0, s, x0 - sx * x0, 0)))   # scale about (left ink edge, baseline)
        f["glyf"][name] = pen.glyph()
        f["glyf"][name].recalcBounds(f["glyf"])
        f["hmtx"][name] = (int(round(lsb + sx * (x1 - x0) + rsb)), lsb)
    f.save(dst)
    return scales


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("ref")
    ap.add_argument("dst")
    ap.add_argument("--chars", default=LOWER)
    ap.add_argument("--match-width", action="store_true",
                    help="also scale each glyph horizontally to the reference glyph's width (x the same factor)")
    ap.add_argument("--tall", action="store_true",
                    help="match the taller, borrowed x-height: reference heights x the median ratio of borrowed letters")
    a = ap.parse_args()
    k = tall_factor(a.src, a.ref) if a.tall else 1.0
    print("height factor", round(k, 3))
    print(normalize(a.src, a.ref, a.dst, a.chars, k, a.match_width))


if __name__ == "__main__":
    main()
