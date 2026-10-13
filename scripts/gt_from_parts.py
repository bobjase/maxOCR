"""Second try at g and t from our own glyphs.
  g_qj2  : q without its straight descender and foot (the bowl keeps its round bottom) + our j's hooked descender,
           scaled so its stem is exactly as wide as the q's stem, bridged so there is no step.
  t_draw : stem as wide as our f's, slanted top cut, our f's flat crossbar (rounded ends) with its top on the x-height,
           and a foot drawn as a round serif curve (quarter-ellipse turns, slim blunt end), no ball.
"""
import os
import sys
sys.path.insert(0, "scripts")  # run from the repo root
import pathops
from fontTools.ttLib import TTFont
from glyph_edit import clip, glyph_path, rect, rounded_rect, stem_span, transformed, write

base, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
XH, BIG = 541, 3000
f0 = TTFont(base)


def save(name, ch, path, lsb=None, rsb=None, adv=None):
    f = TTFont(base)
    write(f, ch, path)
    gn = f.getBestCmap()[ord(ch)]
    g = f["glyf"][gn]; g.recalcBounds(f["glyf"])
    if lsb is not None:
        g.coordinates.translate((lsb - g.xMin, 0)); g.recalcBounds(f["glyf"])
    if rsb is not None:
        adv = g.xMax + rsb
    if adv is not None:
        f["hmtx"][gn] = (int(round(adv)), g.xMin)
    f.save(f"{outdir}/{name}.ttf")
    print(name, "ink", g.xMin, g.xMax, g.yMin, g.yMax, "adv", f["hmtx"][gn][0])


# --- g ---
q, j = glyph_path(f0, "q"), glyph_path(f0, "j")
q0, q1 = stem_span(q, -100)
j0, j1 = stem_span(j, 0)                       # the j's descender starts tapering at the baseline
upper = pathops.op(q, rect(330, -BIG, BIG, 0), pathops.PathOp.DIFFERENCE)        # q minus descender and foot
sx = (q1 - q0) / (j1 - j0)                     # j's descender widened so it starts exactly as wide as the q's stem
hook = transformed(clip(j, (-BIG, -BIG, BIG, 0)), (sx, 0, 0, 1, q0 - sx * j0, 0))
bridge = rect(q0, -2, q1, 2)
g = pathops.op(pathops.op(upper, hook, pathops.PathOp.UNION), bridge, pathops.PathOp.UNION)
qadv = f0["hmtx"][f0.getBestCmap()[ord("q")]][0]
save("g_qj2", "g", g, adv=qadv)

# --- t ---
ff = glyph_path(f0, "f")
S0, S1 = stem_span(ff, 250)
rows = []
for y in range(380, 600, 2):
    a, _, b, _ = clip(ff, (-BIG, y - 1, BIG, y + 1)).bounds
    if b - a > (S1 - S0) + 60:
        rows.append(y)
thick = rows[-1] - rows[0]
k = 0.5523
p = pathops.Path(); pen = p.getPen()
top_l, top_r = XH + 60, XH + 100
pen.moveTo((S0, top_l))
pen.lineTo((S0, 140))
bx = S1 + 30                                                       # bottom of the foot curve
pen.curveTo((S0, 140 - k * 148), (bx - k * (bx - S0), -8), (bx, -8))
ex = S1 + 175                                                      # blunt end of the foot
pen.curveTo((S1 + 95, -8), (ex - 15, 15), (ex, 48))
pen.lineTo((ex - 12, 92))
ix = S1 + 48
pen.curveTo((ex - 45, 70), (ix + 40, 58), (ix, 60))
pen.curveTo((ix - k * (ix - S1), 60), (S1, 150 - k * 90), (S1, 150))
pen.lineTo((S1, top_r))
pen.closePath()
bar = rounded_rect(S0 - 130, XH - thick, S1 + 190, XH, 0.3 * thick)
t = pathops.op(p, bar, pathops.PathOp.UNION)
save("t_draw", "t", t, lsb=40, rsb=40)
