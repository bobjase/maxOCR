"""Draw lowercase letters from clean parts of our own font (James, 2026-10-12: transform our f, g, j to look normal,
"don't start with an existing font; use OUR font"). Blended glyphs carry notches where a curve meets a stem (b d h k
m n p q r) and f g j are off-style, so these letters are rebuilt by joining clean pieces with boolean union:
our i's head serif, foot slab and dot, our o as the bowl, straight stems at our stem width, and hooks, arches and
crossbars drawn as smooth elliptical curves at our stroke weight. Output glyphs are real curves (cu2qu).

    python scripts/construct_lc.py SRC.ttf DST.ttf [--chars jfgq]
"""
import argparse
import math

import pathops
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.statisticsPen import StatisticsPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

XH, ASC, DESC = 541, 828, -235       # exact bands (exact_heights.py)
W = 95                                # our stem width (i 87, l 85, n 95, h 100, o side 101)
BAR = 62                              # crossbar thickness (horizontal strokes are thinner than stems)


class Kit:
    def __init__(self, font: TTFont):
        self.f, self.gs, self.cm = font, font.getGlyphSet(), font.getBestCmap()

    def glyph(self, c: str, dx: float = 0, dy: float = 0) -> pathops.Path:
        p = pathops.Path()
        rec = DecomposingRecordingPen(self.gs)
        self.gs[self.cm[ord(c)]].draw(rec)
        rec.replay(TransformPen(p.getPen(), (1, 0, 0, 1, dx, dy)))
        return p

    def part(self, c: str, x0, y0, x1, y1, dx=0, dy=0) -> pathops.Path:
        """The piece of glyph c inside the box, moved by (dx, dy)."""
        return translate(pathops.op(self.glyph(c), rect(x0, y0, x1, y1), pathops.PathOp.INTERSECTION), dx, dy)


def rect(x0, y0, x1, y1) -> pathops.Path:
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x1, y1)); pen.lineTo((x1, y0)); pen.closePath()
    return p


def translate(p: pathops.Path, dx, dy) -> pathops.Path:
    out = pathops.Path()
    p.draw(TransformPen(out.getPen(), (1, 0, 0, 1, dx, dy)))
    return out


def _arc(pen, cx, cy, rx, ry, a0, a1, move=False):
    """Elliptical arc from angle a0 to a1 (radians) as cubic Beziers of at most 90 degrees each."""
    n = max(1, math.ceil(abs(a1 - a0) / (math.pi / 2) - 1e-9))
    da = (a1 - a0) / n
    k = 4 / 3 * math.tan(da / 4)
    x, y = cx + rx * math.cos(a0), cy + ry * math.sin(a0)
    if move:
        pen.moveTo((x, y))
    else:
        pen.lineTo((x, y))
    for i in range(n):
        t0, t1 = a0 + i * da, a0 + (i + 1) * da
        p1 = (cx + rx * (math.cos(t0) - k * math.sin(t0)), cy + ry * (math.sin(t0) + k * math.cos(t0)))
        p2 = (cx + rx * (math.cos(t1) + k * math.sin(t1)), cy + ry * (math.sin(t1) - k * math.cos(t1)))
        pen.curveTo(p1, p2, (cx + rx * math.cos(t1), cy + ry * math.sin(t1)))


def ring(cx, cy, rxo, ryo, rxi, ryi, a0, a1, cxi=None, cyi=None) -> pathops.Path:
    """Elliptical ring sector between angles a0 and a1 (degrees); the inner ellipse may have its own centre,
    which lets the stroke swell or taper like a drawn curve."""
    a0, a1 = math.radians(a0), math.radians(a1)
    cxi = cx if cxi is None else cxi
    cyi = cy if cyi is None else cyi
    p = pathops.Path()
    pen = p.getPen()
    _arc(pen, cx, cy, rxo, ryo, a0, a1, move=True)
    _arc(pen, cxi, cyi, rxi, ryi, a1, a0)
    pen.closePath()
    return p


def disc(cx, cy, r) -> pathops.Path:
    p = pathops.Path()
    pen = p.getPen()
    _arc(pen, cx, cy, r, r, 0, 2 * math.pi, move=True)
    pen.closePath()
    return p


def ring_end_ball(cx, cy, rxo, ryo, rxi, ryi, a, cxi=None, cyi=None, scale=1.1) -> pathops.Path:
    """Ball terminal centred on the stroke at angle a (degrees), as wide as the stroke there x scale."""
    a = math.radians(a)
    cxi = cx if cxi is None else cxi
    cyi = cy if cyi is None else cyi
    xo, yo = cx + rxo * math.cos(a), cy + ryo * math.sin(a)
    xi, yi = cxi + rxi * math.cos(a), cyi + ryi * math.sin(a)
    return disc((xo + xi) / 2, (yo + yi) / 2, scale * math.hypot(xo - xi, yo - yi) / 2)


def union(*paths) -> pathops.Path:
    out = paths[0]
    for p in paths[1:]:
        out = pathops.op(out, p, pathops.PathOp.UNION)
    return out


# ----- letters ---------------------------------------------------------------------------------------------------

def build_j(k: Kit):
    """i's head serif and dot on a stem that runs below the baseline into a hook to the left with a ball end."""
    s0 = 129                                           # i's stem (y=300: 129-215)
    s1 = s0 + W
    head = k.part("i", -50, 380, 400, 700)            # head serif and stem top
    dot = k.part("i", -50, 650, 400, 900)
    stem = rect(s0, -95, s1, 400)
    hk = (s1 - 165, -95, 165, 140, 165 - W, 140 - W * 0.6)
    hook = ring(*hk, 0, -160, cxi=s1 - 165 - 4, cyi=-95 + 6)
    ball = ring_end_ball(*hk, -160, cxi=s1 - 165 - 4, cyi=-95 + 6, scale=1.15)
    return union(head, dot, stem, hook, ball), 348


def build_f(k: Kit):
    """Stem with i's foot slab, an arch at the top bending right into a ball terminal, crossbar at the x-height."""
    s0 = 129
    s1 = s0 + W
    foot = k.part("i", -50, -20, 400, 75)             # foot slab
    top = 600                                          # where the stem turns into the arch
    stem = rect(s0, 40, s1, top)
    ar = (s0 + 230, top, 230, ASC - top, 230 - W, ASC - top - W * 0.6)
    arch = ring(*ar, 180, 25, cxi=s0 + 230 + 8, cyi=top - 6)
    ball = ring_end_ball(*ar, 25, cxi=s0 + 230 + 8, cyi=top - 6, scale=1.1)
    bar = rect(s0 - 105, XH - BAR, s1 + 150, XH)
    return union(foot, stem, arch, ball, bar), 430


def build_q(k: Kit):
    """Our o as the bowl, a stem on its right running to the descender, i's foot slab at the bottom."""
    bowl = k.glyph("o")                                # o: x 41-542, right stroke 439-539
    s1 = 539
    s0 = s1 - W
    stem = rect(s0, DESC + 60, s1, XH)
    foot = k.part("i", -50, -20, 400, 75, dx=s0 - 129, dy=DESC)
    spur = rect(s1 - 4, XH - 40, s1 + 38, XH)          # small flat spur at the top right
    return union(bowl, stem, foot, spur), 600


def build_g(k: Kit):
    """Single-storey g: our o as the bowl, a stem on the right that turns into a hook below the baseline, ending in
    a ball under the bowl; a flat ear at the top right (the typewriter g's tell against 9, drawn at our weight)."""
    bowl = k.glyph("o")
    s1 = 539
    s0 = s1 - W
    stem = rect(s0, -60, s1, XH)
    hk = (s1 - 230, -60, 230, -60 - DESC, 230 - W, -60 - DESC - W * 0.6)
    hook = ring(*hk, 0, -165, cxi=s1 - 230 - 6, cyi=-60 + 8)
    ball = ring_end_ball(*hk, -165, cxi=s1 - 230 - 6, cyi=-60 + 8, scale=1.1)
    ear = rect(s1 - 10, XH - BAR, s1 + 90, XH)
    return union(bowl, stem, hook, ball, ear), 640


BUILDERS = {"j": build_j, "f": build_f, "q": build_q, "g": build_g}


def write(font: TTFont, c: str, path: pathops.Path, advance: int) -> None:
    rec = RecordingPen()
    path.draw(rec)
    stats = StatisticsPen()
    rec.replay(stats)
    tt = TTGlyphPen(None)
    target = Cu2QuPen(tt, max_err=0.8)
    rec.replay(ReverseContourPen(target) if stats.area > 0 else target)   # TrueType: outer contours clockwise
    g = tt.glyph()
    name = font.getBestCmap()[ord(c)]
    g.recalcBounds(font["glyf"])
    font["glyf"][name] = g
    font["hmtx"][name] = (advance, g.xMin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--chars", default="jfqg")
    a = ap.parse_args()
    src = TTFont(a.src)
    kit = Kit(src)
    built = {c: BUILDERS[c](kit) for c in a.chars}   # every letter from the source's clean parts
    out = TTFont(a.src)
    for c, (path, adv) in built.items():
        write(out, c, path, adv)
    out.save(a.dst)
    print(a.dst, "".join(built))


if __name__ == "__main__":
    main()
