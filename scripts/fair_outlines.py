"""Redraw our own glyph outlines cleanly, the way a type designer would (James, 2026-10-12: our letters, but not "a
child's chicken scratch"; no other font). Input is our font's curve version (curve_outlines.py), whose outlines follow
the old traced bitmaps closely, wobbles included. For each contour:
  1. follow the outline at 2-unit steps;
  2. find real corners (sharp turns: serif tips, junctions) and keep them sharp;
  3. long runs that are nearly straight become one straight line, snapped exactly vertical or horizontal when within
     a few degrees (stems, serif bottoms, crossbars);
  4. the curved stretches between are smoothed along their length (wobbles out, endpoints fixed);
  5. each curved stretch is split at its horizontal and vertical extremes and redrawn with as few cubic curves as fit
     within a small tolerance (Schneider's method), tangents continuous with the neighbouring lines.
Result: TrueType quadratics (cu2qu), same advance, same contour direction.

    python scripts/fair_outlines.py SRC.ttf DST.ttf [--chars ...] [--smooth 30] [--tol 2.5]
"""
import argparse
import math
import string

import numpy as np
import pathops
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

STEP = 2.0
CORNER_DEG = 38.0
CORNER_WIN = 6           # samples each side (12 units)
MIN_LINE = 24.0          # units: shortest straight run (serif sides)
LONG_LINE = 70.0         # longer runs may wobble a little and still be straight (stems)
SHORT = 14.0             # pieces and gaps shorter than this become straight joins
SNAP_DEG = 4.0
SPLIT_TOL = 12.0         # a quarter is drawn as one curve unless that misses the outline by more than this


# ----- outline sampling -----------------------------------------------------------------------------------------

def contours_of(f: TTFont, name: str) -> list[np.ndarray]:
    """Each contour of a TrueType glyph as a dense closed polyline (no repeated end point)."""
    g = f["glyf"][name]
    coords, ends, flags = g.getCoordinates(f["glyf"])
    out, start = [], 0
    for e in ends:
        pts = [(tuple(coords[i]), bool(flags[i] & 1)) for i in range(start, e + 1)]
        start = e + 1
        if not any(on for _, on in pts):          # all off-curve: add implied on-curve midpoint
            p, q = pts[0][0], pts[1][0]
            pts.insert(1, (((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), True))
        k = next(i for i, (_, on) in enumerate(pts) if on)
        pts = pts[k:] + pts[:k]
        poly, n = [], len(pts)
        for i in range(n):
            p, on = pts[i]
            if on:
                poly.append(p)
                continue
            prev, pon = pts[i - 1]
            nxt, non = pts[(i + 1) % n]
            a = prev if pon else ((prev[0] + p[0]) / 2, (prev[1] + p[1]) / 2)
            b = nxt if non else ((p[0] + nxt[0]) / 2, (p[1] + nxt[1]) / 2)
            for t in np.linspace(0, 1, 9)[1:-1]:
                poly.append(((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * p[0] + t * t * b[0],
                             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * p[1] + t * t * b[1]))
        out.append(resample(np.array(poly, float)))
    return out


def resample(poly: np.ndarray, step: float = STEP) -> np.ndarray:
    closed = np.vstack([poly, poly[:1]])
    seg = np.hypot(*np.diff(closed, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(8, int(s[-1] / step))
    t = np.linspace(0, s[-1], n, endpoint=False)
    return np.column_stack([np.interp(t, s, closed[:, 0]), np.interp(t, s, closed[:, 1])])


# ----- corners, lines, smoothing ----------------------------------------------------------------------------------

def corners(P: np.ndarray) -> list[int]:
    """Sharp turns, also slightly rounded ones: the turn is measured over a short and a longer stretch (a corner
    with a small rounding radius turns sharply over the longer stretch; a bowl never does)."""
    n, w = len(P), CORNER_WIN
    turn = np.zeros(n)
    for win in (CORNER_WIN, 2 * CORNER_WIN):
        a = P - np.roll(P, win, axis=0)
        b = np.roll(P, -win, axis=0) - P
        cos = (a * b).sum(1) / (np.hypot(*a.T) * np.hypot(*b.T) + 1e-9)
        turn = np.maximum(turn, np.degrees(np.arccos(np.clip(cos, -1, 1))) * (1.0 if win == CORNER_WIN else 0.8))
    idx = []
    for i in range(n):
        if turn[i] >= CORNER_DEG and turn[i] == max(turn[(i + k) % n] for k in range(-w, w + 1)):
            if not idx or i - idx[-1] > w:
                idx.append(i)
    return idx


def line_runs(Q: np.ndarray) -> list[tuple[int, int]]:
    """Maximal straight runs [s, e] of an open polyline: every point within tol of the chord, tol growing with
    length (a long stem that wobbles a little is still a stem)."""
    runs, s, n = [], 0, len(Q)
    while s < n - 1:
        best, e = None, s + 2
        while e < n:
            A, B = Q[s], Q[e]
            L = math.hypot(*(B - A))
            if L > 0:
                V, R = B - A, Q[s:e + 1] - A
                d = np.abs(V[0] * R[:, 1] - V[1] * R[:, 0]) / L
                tol = 0.7 + 0.003 * L if L >= LONG_LINE else 0.25   # short runs must be truly straight
                if d.max() > tol:
                    break
                # a short straight run only counts where it starts or ends at a corner (the flat sides of a serif);
                # in the middle of a curve it is just a gentle stretch of that curve
                if L >= LONG_LINE or (L >= MIN_LINE and (s == 0 or e == n - 1)):
                    best = e
            e += 1
        if best is not None:
            runs.append((s, best))
            s = best
        else:
            s += 1
    return runs


def smooth_open(Q: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smoothing along an open polyline with both ends fixed (point reflection at the ends)."""
    if len(Q) < 5 or sigma <= 0:
        return Q
    r = int(3 * sigma)
    head = 2 * Q[0] - Q[1:r + 1][::-1]
    tail = 2 * Q[-1] - Q[-r - 1:-1][::-1]
    ext = np.vstack([head, Q, tail])
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    sm = np.column_stack([np.convolve(ext[:, 0], k, "same"), np.convolve(ext[:, 1], k, "same")])[r:r + len(Q)]
    # pull the ends back exactly onto their original positions, easing in over sigma
    wts = np.clip(np.minimum(np.arange(len(Q)), np.arange(len(Q))[::-1]) / max(sigma, 1), 0, 1)[:, None]
    return wts * sm + (1 - wts) * Q


def snap(A: np.ndarray, B: np.ndarray, max_shift: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Make a nearly horizontal or vertical line exact, but only when that moves its ends by at most max_shift
    (a bigger move would pull the neighbouring curves into ticks and slivers)."""
    ang = math.degrees(math.atan2(B[1] - A[1], B[0] - A[0])) % 180
    if min(ang, 180 - ang) <= SNAP_DEG and abs(A[1] - B[1]) / 2 <= max_shift:     # horizontal
        y = (A[1] + B[1]) / 2
        return np.array([A[0], y]), np.array([B[0], y])
    if abs(ang - 90) <= SNAP_DEG and abs(A[0] - B[0]) / 2 <= max_shift:          # vertical
        x = (A[0] + B[0]) / 2
        return np.array([x, A[1]]), np.array([x, B[1]])
    return A, B


# ----- Bezier fitting (Schneider) ---------------------------------------------------------------------------------

def _bez(ctrl, t):
    t = np.asarray(t)[:, None]
    return ((1 - t) ** 3 * ctrl[0] + 3 * (1 - t) ** 2 * t * ctrl[1] + 3 * (1 - t) * t ** 2 * ctrl[2] + t ** 3 * ctrl[3])


def _unit(v):
    n = np.hypot(*v)
    return v / n if n > 1e-9 else v


def fit_cubic(Q: np.ndarray, t0: np.ndarray, t1: np.ndarray, tol: float, depth: int = 0) -> list:
    """Cubic Beziers through Q[0] and Q[-1] with end tangents t0 (leaving) and t1 (arriving, pointing back)."""
    if len(Q) < 3:
        return [(Q[0], Q[0] + (Q[-1] - Q[0]) / 3, Q[-1] - (Q[-1] - Q[0]) / 3, Q[-1])]
    d = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(Q, axis=0).T))])
    u = d / d[-1]
    for _ in range(4):
        b0, b3 = Q[0], Q[-1]
        A1 = (3 * u * (1 - u) ** 2)[:, None] * t0
        A2 = (3 * u ** 2 * (1 - u))[:, None] * t1
        C = np.array([[(A1 * A1).sum(), (A1 * A2).sum()], [(A1 * A2).sum(), (A2 * A2).sum()]])
        base = _bez([b0, b0, b3, b3], u)
        X = np.array([((Q - base) * A1).sum(), ((Q - base) * A2).sum()])
        det = np.linalg.det(C)
        seg_len = d[-1]
        if abs(det) > 1e-9:
            a1, a2 = np.linalg.solve(C, X)
        else:
            a1 = a2 = seg_len / 3
        chord = math.hypot(*(b3 - b0))
        if a1 < 1e-3 * seg_len or a2 < 1e-3 * seg_len or a1 > 0.7 * chord or a2 > 0.7 * chord:
            a1 = a2 = chord / 3          # handles longer than the gap they span make loops: keep them modest
        ctrl = [b0, b0 + a1 * t0, b3 + a2 * t1, b3]
        err = np.hypot(*(_bez(ctrl, u) - Q).T)
        if err.max() <= tol:
            return [tuple(ctrl)]
        # Newton reparameterization
        p = _bez(ctrl, u)
        d1 = 3 * ((1 - u) ** 2)[:, None] * (ctrl[1] - ctrl[0]) + 6 * ((1 - u) * u)[:, None] * (ctrl[2] - ctrl[1]) \
            + 3 * (u ** 2)[:, None] * (ctrl[3] - ctrl[2])
        d2 = 6 * (1 - u)[:, None] * (ctrl[2] - 2 * ctrl[1] + ctrl[0]) + 6 * u[:, None] * (ctrl[3] - 2 * ctrl[2] + ctrl[1])
        num = ((p - Q) * d1).sum(1)
        den = (d1 * d1).sum(1) + ((p - Q) * d2).sum(1)
        u = np.clip(u - np.where(np.abs(den) > 1e-9, num / den, 0), 0, 1)
        u[0], u[-1] = 0, 1
        u = np.maximum.accumulate(u)
    if depth > 12 or len(Q) < 6:
        return [tuple(ctrl)]
    k = int(np.argmax(err[1:-1])) + 1
    tc = _unit(Q[min(k + 1, len(Q) - 1)] - Q[max(k - 1, 0)])
    return fit_cubic(Q[:k + 1], t0, -tc, tol, depth + 1) + fit_cubic(Q[k:], tc, t1, tol, depth + 1)


def extremes(Q: np.ndarray) -> list[int]:
    """Interior indices where x or y reaches a local extreme (points belong there in a well-drawn outline)."""
    idx = []
    for axis in (0, 1):
        v = Q[:, axis]
        dv = np.sign(np.diff(v))
        for i in range(1, len(dv)):
            if dv[i] != 0 and dv[i - 1] != 0 and dv[i] != dv[i - 1] and 6 < i < len(Q) - 7:
                idx.append(i)
    idx = sorted(set(idx))
    keep = []
    for i in idx:                                   # drop extremes too close together (flat wiggles)
        if not keep or i - keep[-1] > 12:
            keep.append(i)
    return keep


# ----- one contour ----------------------------------------------------------------------------------------------

def shallow_dents(P: np.ndarray, cs: list[int], reach: int = 15, depth: float = 25.0) -> list[int]:
    """Corners that are only shallow inward dents (the notches left where blended letters' joins disagreed):
    the outline turns inward and the point lies less than `depth` units from the line across the dent."""
    n = len(P)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    out = []
    for i in cs:
        a, b, c = P[(i - reach) % n], P[i], P[(i + reach) % n]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        inward = cross * area < 0               # turning against the contour's own direction: a dent
        d = abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / (math.hypot(*(c - a)) + 1e-9)
        u, v = b - a, c - b
        turn = math.degrees(math.acos(max(-1.0, min(1.0, (u @ v) / (np.hypot(*u) * np.hypot(*v) + 1e-9)))))
        if inward and d < depth and turn > 105:     # a V-shaped notch; a square inside corner (~90) is kept
            out.append(i)
    return out


def fair_contour(P: np.ndarray, sigma: float, tol: float) -> list:
    """Segments [('line', A, B) | ('curve', c0, c1, c2, c3)] of the cleaned contour, in the original direction."""
    n = len(P)
    cs = corners(P)
    dents = set(shallow_dents(P, cs))
    cs = [i for i in cs if i not in dents]
    if not cs:                                       # smooth closed shape (o, dot): start at the leftmost point
        cs = [int(np.argmin(P[:, 0]))]
        closed_smooth = True
    else:
        closed_smooth = False
    segs = []
    for j, s in enumerate(cs):
        e = cs[(j + 1) % len(cs)]
        idx = np.arange(s, e + (n if e <= s else 0) + 1) % n
        Q = P[idx]
        if closed_smooth:
            Q = smooth_closed_piece(np.vstack([P[s:], P[:s + 1]]), sigma)
        else:
            Q = smooth_open(Q, sigma / STEP)            # wobbles out first, then decide what is straight
        arc = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(Q, axis=0).T))])
        if arc[-1] < SHORT:                           # a tiny piece between two corners: a straight join
            segs.append(("line", Q[0], Q[-1]))
            continue
        pieces = []                                  # ('line', a, b) on Q indices, curves in between
        last = 0
        for a, b in line_runs(Q):
            if a > last:
                pieces.append(("line" if arc[a] - arc[last] < SHORT else "curve", last, a))
            pieces.append(("line", a, b))
            last = b
        if last < len(Q) - 1:
            pieces.append(("line" if arc[-1] - arc[last] < SHORT else "curve", last, len(Q) - 1))
        # fixed endpoints: snapped line ends
        pts = {}
        for kind, a, b in pieces:
            if kind == "line":
                A, B = snap(Q[a], Q[b])
                pts[a], pts[b] = A, B
        for kind, a, b in pieces:
            A = pts.get(a, Q[a])
            B = pts.get(b, Q[b])
            if kind == "line":
                segs.append(("line", A, B))
                continue
            R = Q[a:b + 1].copy()
            R[0], R[-1] = A, B
            prev_line = any(k == "line" and bb == a for k, aa, bb in pieces)
            next_line = any(k == "line" and aa == b for k, aa, bb in pieces)
            t0 = _unit(pts[a] - pts[[aa for k, aa, bb in pieces if k == "line" and bb == a][0]]) if prev_line \
                else _unit(R[min(4, len(R) - 1)] - R[0])
            t1 = _unit(pts[b] - pts[[bb for k, aa, bb in pieces if k == "line" and aa == b][0]]) if next_line \
                else _unit(R[max(len(R) - 5, 0)] - R[-1])
            cuts = [0] + extremes(R) + [len(R) - 1]
            tangents = {0: t0}
            for c in cuts[1:-1]:
                tang = _unit(R[min(c + 2, len(R) - 1)] - R[max(c - 2, 0)])
                if abs(tang[0]) > abs(tang[1]):
                    tang = np.array([math.copysign(1, tang[0]), 0.0])     # y extreme: horizontal tangent
                else:
                    tang = np.array([0.0, math.copysign(1, tang[1])])     # x extreme: vertical tangent
                tangents[c] = tang
            for c0, c1 in zip(cuts[:-1], cuts[1:]):
                ta = tangents[c0]
                tb = -tangents[c1] if c1 in tangents else t1
                # one curve per quarter (extreme to extreme), the way a bowl is drawn; split only when a single
                # curve cannot follow the stretch at all (an S-bend), never to copy small flats
                for bz in fit_cubic(R[c0:c1 + 1], ta, tb, SPLIT_TOL):
                    segs.append(("curve",) + tuple(np.asarray(x) for x in bz))
    return segs


def smooth_closed_piece(Q: np.ndarray, sigma: float) -> np.ndarray:
    """Smooth a closed loop given as an open polyline whose ends coincide."""
    r = int(3 * sigma / STEP)
    if r < 1:
        return Q
    loop = Q[:-1]
    ext = np.vstack([loop[-r:], loop, loop[:r]])
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / (sigma / STEP)) ** 2)
    k /= k.sum()
    sm = np.column_stack([np.convolve(ext[:, 0], k, "same"), np.convolve(ext[:, 1], k, "same")])[r:r + len(loop)]
    return np.vstack([sm, sm[:1]])


def draw(segs, pen):
    first = True
    for s in segs:
        if first:
            pen.moveTo(tuple(map(float, s[1])))
            first = False
        if s[0] == "line":
            pen.lineTo(tuple(map(float, s[2])))
        else:
            pen.curveTo(tuple(map(float, s[2])), tuple(map(float, s[3])), tuple(map(float, s[4])))
    pen.closePath()


def fair_font(src: str, dst: str, chars: str, sigma: float, tol: float) -> None:
    f = TTFont(src)
    cm = f.getBestCmap()
    for c in chars:
        name = cm.get(ord(c))
        if name is None or f["glyf"][name].numberOfContours <= 0:
            continue
        path = pathops.Path()
        for P in contours_of(f, name):
            draw(fair_contour(P, sigma, tol), path.getPen())
        path.simplify(fix_winding=True)              # removes any small self-overlap left by the fitting
        tt = TTGlyphPen(None)
        path.draw(Cu2QuPen(tt, max_err=0.6, reverse_direction=True))
        g = tt.glyph()
        g.recalcBounds(f["glyf"])
        adv, _ = f["hmtx"][name]
        f["glyf"][name] = g
        f["hmtx"][name] = (adv, g.xMin)
    f.save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--chars", default=string.ascii_lowercase)
    ap.add_argument("--smooth", type=float, default=30.0, help="smoothing length along curves (font units)")
    ap.add_argument("--tol", type=float, default=2.5, help="curve fit tolerance (font units)")
    a = ap.parse_args()
    fair_font(a.src, a.dst, a.chars, a.smooth, a.tol)
    print(a.dst)


if __name__ == "__main__":
    main()
