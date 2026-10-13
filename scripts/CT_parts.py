"""C narrower and a simpler T, from our own glyphs (James, 2026-10-12: "C (too wide) and T (simplify) are next").
  C85, C75 : our C at 85 / 75 % of its width (height kept)
  T_plain  : a plain T drawn to our proportions: a straight bar (as thick as our E's arms) with lightly rounded ends,
             a straight stem as wide as our I's, a small foot slab, and small brackets where the stem meets bar and foot
  T_I      : (dropped: the I's top is not a flat slab, so stretching it left steps) a T built from our I: the I's top slab (with its end spurs and the brackets under it) stretched to the
             T's width by moving its ends apart along a straight bar, the I's straight stem, and the I's foot slab
             narrowed by moving its ends inward. No droopy bar ends, no waisted stem.
    python scripts/CT_parts.py BASE.ttf OUTDIR
"""
import os
import sys

import pathops
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import clip, glyph_path, rect, stem_span, transformed, write

base, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
BIG = 3000
f0 = TTFont(base)
cm = f0.getBestCmap()


def ink(c):
    g = f0["glyf"][cm[ord(c)]]; g.recalcBounds(f0["glyf"]); return g.xMin, g.xMax


def save(name, ch, path, lsb, rsb):
    f = TTFont(base)
    write(f, ch, path)
    gn = f.getBestCmap()[ord(ch)]
    g = f["glyf"][gn]; g.recalcBounds(f["glyf"])
    g.coordinates.translate((lsb - g.xMin, 0)); g.recalcBounds(f["glyf"])
    f["hmtx"][gn] = (int(round(g.xMax + rsb)), g.xMin)
    f.save(f"{outdir}/{name}.ttf")
    print(name, "ink", g.xMin, g.xMax, g.yMin, g.yMax, "adv", f["hmtx"][gn][0])


def yspan(p, xs, lo, hi):
    """The thinnest vertical run of ink over the x positions xs (the plain slab, away from brackets and spurs)."""
    best = None
    for x in xs:
        _, y0, _, y1 = clip(p, (x - 1, lo, x + 1, hi)).bounds
        if best is None or y1 - y0 < best[1] - best[0]:
            best = (y0, y1)
    return best


# --- C narrower ---
C = glyph_path(f0, "C")
x0, x1 = ink("C")
adv = f0["hmtx"][cm[ord("C")]][0]
for sx in (0.85, 0.75):
    save(f"C{int(sx * 100)}", "C", transformed(C, (sx, 0, 0, 1, x0 - sx * x0, 0)), x0, adv - x1)

# --- T from I ---
I = glyph_path(f0, "I")
s0, s1 = stem_span(I, 300)
xc = (s0 + s1) / 2
ix0, ix1 = ink("I")
tx0, tx1 = ink("T")
d = ((tx1 - tx0) - (ix1 - ix0)) / 2                    # how far each top end moves out
e = 80                                                 # how far each foot end moves in
cut_l, cut_r = s0 - 60, s1 + 60                        # ends vs middle (stem, brackets)
# top: ends moved apart, a straight bar between them at the slab's own height
ty0, ty1 = yspan(I, range(int(s1 + 10), int(ix1 - 10), 4), 500, BIG)   # the slab itself, between bracket and spur
top_l = transformed(clip(I, (-BIG, 560, cut_l, BIG)), (1, 0, 0, 1, -d, 0))
top_r = transformed(clip(I, (cut_r, 560, BIG, BIG)), (1, 0, 0, 1, d, 0))
top_m = clip(I, (cut_l, 560, cut_r, BIG))
bar = rect(cut_l - d - 1, ty0, cut_r + d + 1, ty1)
# foot: ends moved inward over the middle
by0, by1 = yspan(I, range(int(s1 + 10), int(ix1 - 10), 4), -BIG, 200)
bot_l = transformed(clip(I, (-BIG, -BIG, cut_l, 140)), (1, 0, 0, 1, e, 0))
bot_r = transformed(clip(I, (cut_r, -BIG, BIG, 140)), (1, 0, 0, 1, -e, 0))
bot_m = clip(I, (cut_l, -BIG, cut_r, 140))
stem = clip(I, (cut_l, 130, cut_r, 570))
T = top_m
for part in (top_l, top_r, bar, bot_l, bot_r, bot_m, stem):
    T = pathops.op(T, part, pathops.PathOp.UNION)
tadv = f0["hmtx"][cm[ord("T")]][0]
save("T_I", "T", T, tx0, tadv - tx1)
print("I stem", s0, s1, "top slab", ty0, ty1, "foot slab", by0, by1, "d", d)


# --- plain T, drawn ---
from glyph_edit import rounded_rect
K = 0.5523


def fillet(x, y, r, sx, sy) -> pathops.Path:
    """Concave bracket in the corner at (x, y): a r x r square on the side (sx, sy) minus a quarter disc."""
    sq = rect(min(x, x + sx * r), min(y, y + sy * r), max(x, x + sx * r), max(y, y + sy * r))
    cx, cy = x + sx * r, y + sy * r
    disc = pathops.Path(); pen = disc.getPen()
    pen.moveTo((cx - r, cy)); pen.curveTo((cx - r, cy + K * r), (cx - K * r, cy + r), (cx, cy + r))
    pen.curveTo((cx + K * r, cy + r), (cx + r, cy + K * r), (cx + r, cy)); pen.curveTo((cx + r, cy - K * r), (cx + K * r, cy - r), (cx, cy - r))
    pen.curveTo((cx - K * r, cy - r), (cx - r, cy - K * r), (cx - r, cy)); pen.closePath()
    return pathops.op(sq, disc, pathops.PathOp.DIFFERENCE)


W, top, bar_t, foot_t, foot_w, br = 640, 698, 55, 60, 280, 16
sw = s1 - s0                                            # our I's stem width
xm = W / 2
T2 = rounded_rect(0, top - bar_t, W, top, 0.3 * bar_t)
T2 = pathops.op(T2, rect(xm - sw / 2, foot_t - 1, xm + sw / 2, top - bar_t + 1), pathops.PathOp.UNION)
T2 = pathops.op(T2, rounded_rect(xm - foot_w / 2, 0, xm + foot_w / 2, foot_t, 0.3 * foot_t), pathops.PathOp.UNION)
for x, sxn in ((xm - sw / 2, -1), (xm + sw / 2, 1)):
    T2 = pathops.op(T2, fillet(x, top - bar_t, br, sxn, -1), pathops.PathOp.UNION)
    T2 = pathops.op(T2, fillet(x, foot_t, br, sxn, 1), pathops.PathOp.UNION)
save("T_plain", "T", T2, tx0, tadv - tx1 + (tx1 - tx0 - W) / 2 + (tx1 - tx0 - W) / 2)

# --- plain T with our E's arm-end serif at both bar ends ---
E = glyph_path(f0, "E")
ex0, ex1 = ink("E")
_, ebar0, _, ebar1 = clip(E, (ex1 - 30, 500, ex1 + 1, BIG)).bounds       # E's top-right end: serif + bar end
eser = clip(E, (ex1 - 110, 480, BIG, top - bar_t + 2))                      # the serif hanging under the bar end
sx0, _, sx1, _ = eser.bounds
right = transformed(eser, (1, 0, 0, 1, W - sx1, 0))                         # flush with the bar's right end
left = transformed(eser, (-1, 0, 0, 1, sx1, 0))                             # mirrored, flush with the left end
T3 = pathops.op(pathops.op(T2, right, pathops.PathOp.UNION), left, pathops.PathOp.UNION)
save("T_serif", "T", T3, tx0, tadv - tx1)
