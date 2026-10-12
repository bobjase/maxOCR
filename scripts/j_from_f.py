"""j built only from our own shapes: our i's head serif and dot, a stem as wide as the i's, and our f's top arch rotated
half a turn as the hook (an f's top is a j's hook upside down)."""
import sys
sys.path.insert(0, "scripts")
import pathops
from fontTools.ttLib import TTFont
from glyph_edit import clip, glyph_path, rect, stem_span, transformed, write

src, dst = sys.argv[1], sys.argv[2]
f = TTFont(src)
i, ff = glyph_path(f, "i"), glyph_path(f, "f")
j0, j1 = stem_span(i, 300)                       # the i's stem
f0, f1 = stem_span(ff, 250)                      # the f's stem (below its crossbar)
XH, DESC, ASC = 541, -235, 828
head = clip(i, (-500, 260, 1500, 700))           # i's head serif and upper stem (no foot)
dot = clip(i, (-500, 650, 1500, 1200))
# the f's stem and arch as one piece, crossbar removed: the stem below the crossbar is straight, so keeping the f's own
# stem means the j's edge runs from stem into hook in one line, as on the f (no butt joint, no corner)
s0, s1 = stem_span(ff, 250)
top = pathops.op(clip(ff, (-500, 600, 1500, 1200)), clip(ff, (s0, 150, s1, 640)), pathops.PathOp.UNION)
_, _, _, ftop = top.bounds
sx = (j1 - j0) / (f1 - f0)                       # match the f stem's width to the i stem's
# rotate half a turn: x' = c - sx*x, y' = d - y; the f stem's right edge lands on the j stem's left edge... mirrored,
# so its left edge f0 maps to the j's right edge j1, and the arch top lands on the descender
c = j1 + sx * f0
d = DESC + ftop
hook = transformed(top, (-sx, 0, 0, -1, c, d))
_, hb, _, ht = hook.bounds
stem = rect(j0, ht - 40, j1, 300)                # meets the f's own stem well above the hook

def circle(cx, cy, r) -> pathops.Path:
    """A perfect circle: four quarter arcs (cubic, kappa 0.5523)."""
    k = 0.5523 * r
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((cx - r, cy))
    pen.curveTo((cx - r, cy + k), (cx - k, cy + r), (cx, cy + r))
    pen.curveTo((cx + k, cy + r), (cx + r, cy + k), (cx + r, cy))
    pen.curveTo((cx + r, cy - k), (cx + k, cy - r), (cx, cy - r))
    pen.curveTo((cx - k, cy - r), (cx - r, cy - k), (cx - r, cy))
    pen.closePath()
    return p


x0, y0, x1, y1 = dot.bounds
r = ((x1 - x0) + (y1 - y0)) / 4                  # the i's dot size, made round
cy = (y0 + y1) / 2
j = pathops.op(pathops.op(pathops.op(head, circle((j0 + j1) / 2, cy, r), pathops.PathOp.UNION), stem,
                          pathops.PathOp.UNION), hook, pathops.PathOp.UNION)
write(f, "j", j)
# the i gets the same round dot, centred over its own stem
i_body = clip(i, (-500, -500, 1500, 640))
write(f, "i", pathops.op(i_body, circle((j0 + j1) / 2, cy, r), pathops.PathOp.UNION))
f.save(dst)
print(dst, "i stem", (round(j0), round(j1)), "f stem", (round(f0), round(f1)), "hook", (round(hb), round(ht)))

# spacing: the same space after the j as after the i
g = TTFont(dst)
cm = g.getBestCmap()
gj, gi = g["glyf"][cm[ord("j")]], g["glyf"][cm[ord("i")]]
gj.recalcBounds(g["glyf"]); gi.recalcBounds(g["glyf"])
rsb = g["hmtx"][cm[ord("i")]][0] - gi.xMax
g["hmtx"][cm[ord("j")]] = (int(round(gj.xMax + rsb)), gj.xMin)
g.save(dst)
