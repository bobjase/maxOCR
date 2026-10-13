"""The W drawn from straight strokes (James, 2026-10-13: "this should be a straight line (and so should its mirror on
the left)", "the weird bubble at the top center looks stupid", "the curves at the bottom of the W ... should both
match the V"; "why do points 19 and 61 exist?": every stroke edge now runs straight right up under its serif).

Each of the four strokes has two straight, parallel edges (taken from the borrowed W's own lines, the wavy stretches
and stray points dropped). The thin second and fourth strokes are 30 units thicker on their inside-corner side,
like the V's right arm, so the inside corners are sharp and level and the bottom points keep their width. The middle
strokes end in a flat cut at the cap height (no ball). Each bottom point is built like the V's: the right edge runs
down to 27, the left edge to 78, joined through a low point 41% of the way across (quadratic curves whose control
points sit where each edge meets the baseline, so every join is smooth). The serifs are the W's own.

    python scripts/draw_w.py SRC.ttf DST.ttf        (SRC: the font with the real-outline W)
"""
import sys

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

THICKER = 30


def line(p, q):
    """x as a function of y on the line through p and q."""
    (x0, y0), (x1, y1) = p, q
    k = (x1 - x0) / (y1 - y0)
    return lambda y: x0 + (y - y0) * k


def meet(f, g, lo=-500, hi=1500):
    """The height where two x(y) lines cross."""
    for _ in range(80):
        mid = (lo + hi) / 2
        if (f(lo) - g(lo)) * (f(mid) - g(mid)) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def bottom(right, left):
    """A bottom point like the V's: on-curve and off-curve points from the right edge down to the left edge."""
    r0, l0 = right(0), left(0)
    b = l0 + 0.41 * (r0 - l0)
    return [((right(27), 27), True), ((r0, 0), False), ((b, 0), True), ((l0, 0), False), ((left(78), 78), True)]


def main():
    src, dst = sys.argv[1:3]
    f = TTFont(src)
    name = f.getBestCmap()[ord("W")]
    g = f["glyf"][name]
    P, ends, flags = g.getCoordinates(f["glyf"])
    P = [tuple(p) for p in P]
    on = [bool(fl & 1) for fl in flags]
    pt = lambda i: (P[i], on[i])

    # the borrowed W's own lines (point numbers of the real-outline W)
    a_out = line(P[144], P[143])                                    # first stroke, outer edge
    a_in = lambda y: P[13][0] + (y - P[13][1]) * (P[143][0] - P[144][0]) / (P[143][1] - P[144][1])   # parallel
    b_right = line(P[118], P[130])                                  # second stroke, right edge
    width_b = b_right(400) - line(P[30], P[36])(400) + THICKER       # its width, 30 thicker on the left
    b_left = lambda y: b_right(y) - width_b
    c_right = line(P[57], P[62])                                    # third stroke, right edge
    width_c = c_right(400) - line(P[117], P[116])(400)
    c_left = lambda y: c_right(y) - width_c
    d_out = line(P[89], P[98])                                      # fourth stroke, outer edge
    width_d = d_out(400) - line(P[66], P[71])(400) + THICKER         # 30 thicker on its inner side
    d_in = lambda y: d_out(y) - width_d
    top = P[4][1]

    y_ab = meet(a_in, b_left)                                       # inside corners
    y_bc = meet(b_right, c_left)
    y_cd = meet(c_right, d_in)
    serif_shift = d_in(P[71][1]) - P[71][0]                          # the fourth stroke's serif comes along

    pts = [pt(i) for i in range(0, 14)]                             # left serif, down to where the inner edge starts
    pts += [((a_in(y_ab), y_ab), True)]                             # inside corner A-B
    pts += [((b_left(top), top), True), ((c_right(top), top), True)]  # flat top of the middle
    pts += [((c_right(y_cd), y_cd), True)]                          # inside corner C-D
    pts += [((d_in(P[71][1]), P[71][1]), True)]                     # fourth stroke's inner edge to its bracket
    pts += [((P[i][0] + serif_shift, P[i][1]), on[i]) for i in range(72, 81)]
    pts += [pt(i) for i in range(81, 90)]                           # right serif, down to where the outer edge starts
    pts += bottom(d_out, c_left)                                    # bottom right point
    pts += [((c_left(y_bc), y_bc), True)]                           # inside corner of the middle (B-C)
    pts += bottom(b_right, a_out)                                   # bottom left point
    pts += [pt(i) for i in range(144, 151)]                         # left serif's outer lobe

    pen = TTGlyphPen(None)
    pen.moveTo(pts[0][0])
    pending = []
    for (xy, is_on) in pts[1:] + [pts[0]]:
        if is_on:
            if pending:
                pen.qCurveTo(*pending, xy)
                pending = []
            else:
                pen.lineTo(xy)
        else:
            pending.append(xy)
    pen.closePath()
    new = pen.glyph()
    new.coordinates.toInt()
    new.recalcBounds(f["glyf"])
    f["glyf"][name] = new
    f["hmtx"][name] = (f["hmtx"][name][0], new.xMin)
    f.save(dst)
    print(dst, "corners at", round(y_ab), round(y_bc), round(y_cd), "top", round(b_left(top)), round(c_right(top)))


if __name__ == "__main__":
    main()
