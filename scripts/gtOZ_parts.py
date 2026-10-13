"""Candidates for g, t, O, Z that fit the family better, built only from our own glyphs (James, 2026-10-12: "g and t
don't fit font family", "O and Z just look off"). Writes one font per candidate into OUTDIR (base font with only that
glyph replaced).
  g_qj : our q's bowl, stem and top spur (no straight descender) + our j's hooked descender under the stem
  t_f  : our f's stem and flat crossbar (crossbar top on the x-height) + our f's top arch flipped vertically as the foot
  O80, O70 : our O at 80 / 70 % of its width (height kept)
  Z86, Z79 : our Z at 86 / 79 % of its width (1.2x / 1.1x a normal Z instead of 1.4x)
"""
import os
import sys
sys.path.insert(0, "scripts")  # run from the repo root
import pathops
from fontTools.ttLib import TTFont
from glyph_edit import clip, glyph_path, rect, stem_span, transformed, write

base, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
XH = 541
BIG = 3000


def save(name, ch, path, adv=None, lsb_target=None):
    f = TTFont(base)
    write(f, ch, path)
    gname = f.getBestCmap()[ord(ch)]
    g = f["glyf"][gname]; g.recalcBounds(f["glyf"])
    if lsb_target is not None:                     # shift so the ink starts at lsb_target
        dx = lsb_target - g.xMin
        g.coordinates.translate((dx, 0)); g.recalcBounds(f["glyf"])
    if adv is not None:
        f["hmtx"][gname] = (int(round(adv)), g.xMin)
    f.save(f"{outdir}/{name}.ttf")
    print(name, "ink", g.xMin, g.xMax, g.yMin, g.yMax, "adv", f["hmtx"][gname][0])


f0 = TTFont(base)
cm = f0.getBestCmap()
adv_of = lambda c: f0["hmtx"][cm[ord(c)]][0]
def ink(c):
    g = f0["glyf"][cm[ord(c)]]; g.recalcBounds(f0["glyf"]); return g.xMin, g.xMax

# --- g from q + j ---
q, j = glyph_path(f0, "q"), glyph_path(f0, "j")
q0, q1 = stem_span(q, -100)                     # the descender: only the stem there
j0, j1 = stem_span(j, -60)
upper = clip(q, (-BIG, -2, BIG, BIG))                          # bowl, stem to the baseline, top spur
hook = transformed(clip(j, (-BIG, -BIG, BIG, 2)), (1, 0, 0, 1, q0 - j0, 0))
stem_join = rect(q0, -20, q1, 20)
g = pathops.op(pathops.op(upper, hook, pathops.PathOp.UNION), stem_join, pathops.PathOp.UNION)
qx0, qx1 = ink("q")
save("g_qj", "g", g, adv=adv_of("q"))

# --- t from f ---
ff = glyph_path(f0, "f")
s0, s1 = stem_span(ff, 250)
rows = []
for y in range(380, 600, 2):
    a, _, b, _ = clip(ff, (-BIG, y - 1, BIG, y + 1)).bounds
    if b - a > (s1 - s0) + 60:
        rows.append(y)
bar_lo, bar_hi = rows[0] - 2, rows[-1] + 2
bar = transformed(clip(ff, (-BIG, bar_lo, BIG, bar_hi)), (1, 0, 0, 1, 0, XH - bar_hi))
_, _, _, ftop = ff.bounds
arch = clip(ff, (-BIG, 600, BIG, BIG))
foot = transformed(arch, (1, 0, 0, -1, 0, ftop - 8))               # flipped: arch top lands at y = -8
_, _, _, foot_top = foot.bounds
top = XH + 100
stem = pathops.Path(); pen = stem.getPen()                         # stem with a slanted top cut
pen.moveTo((s0, foot_top - 20)); pen.lineTo((s0, top - 40)); pen.lineTo((s1, top)); pen.lineTo((s1, foot_top - 20)); pen.closePath()
t = pathops.op(pathops.op(foot, stem, pathops.PathOp.UNION), bar, pathops.PathOp.UNION)
save("t_f", "t", t)
f1 = TTFont(f"{outdir}/t_f.ttf"); gt = f1["glyf"][f1.getBestCmap()[ord("t")]]; gt.recalcBounds(f1["glyf"])
f1["hmtx"][f1.getBestCmap()[ord("t")]] = (int(gt.xMax + 40 - gt.xMin + 40), 40)
gt.coordinates.translate((40 - gt.xMin, 0)); gt.recalcBounds(f1["glyf"]); f1.save(f"{outdir}/t_f.ttf")
print("t_f final adv", f1["hmtx"][f1.getBestCmap()[ord("t")]])

# --- O and Z narrower ---
for ch, sxs in (("O", (0.8, 0.7)), ("Z", (0.86, 0.79))):
    p = glyph_path(f0, ch)
    x0, x1 = ink(ch)
    adv = adv_of(ch)
    lsb, rsb = x0, adv - x1
    for sx in sxs:
        sc = transformed(p, (sx, 0, 0, 1, x0 - sx * x0, 0))       # scale about the left ink edge
        new_adv = lsb + sx * (x1 - x0) + rsb
        save(f"{ch}{int(sx * 100)}", ch, sc, adv=new_adv)
