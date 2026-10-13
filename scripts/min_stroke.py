"""Thicken the thin strokes of chosen letters, leaving the thick ones as they are (the last four cells, 2026-10-13: at
half resolution the hairlines of our C, V, W, X ... vanish and the capitals are read as lowercase).

A stroke is thin where a disc of radius r does not fit inside it: thin = glyph minus its morphological opening
(erode by r, dilate by r, both drawn with skia strokes). Specks at sharp corners (which the opening also trims) are
dropped by area. The thin parts are grown by t on each side and joined to the glyph, but nothing grows past the
glyph's own box, so heights, widths and spacing stay the same.

Bigger dots: --dots s scales the period, the colon's dots and the semicolon's dot by s about their own centres,
bottoms kept on the line (the left side bearing kept, the advance widened by the growth).

    python scripts/min_stroke.py SRC.ttf DST.ttf --chars CKOSUVWXYZ --r 40 --t 20 [--dots 1.25]
"""
import argparse
import os
import sys

import numpy as np
import pathops
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, rect, write  # noqa: E402

OP = pathops.PathOp


def copy(p: pathops.Path) -> pathops.Path:
    q = pathops.Path()
    q.addPath(p)
    return q


def band(p: pathops.Path, width: float) -> pathops.Path:
    """The outline drawn with a round pen of the given width (the region within width/2 of the edge)."""
    q = copy(p)
    q.stroke(width, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    q.convertConicsToQuads()
    return q


def erode(p, r):
    return pathops.op(p, band(p, 2 * r), OP.DIFFERENCE)


def dilate(p, r):
    return pathops.op(p, band(p, 2 * r), OP.UNION)


def thin_parts(p: pathops.Path, r: float, min_area: float) -> pathops.Path:
    """Where a disc of radius r does not fit: the glyph minus the thick parts (everything within r of a point where
    the disc fits, plus a 3-unit margin so the curve approximations leave no slivers along the edges)."""
    thick = dilate(erode(p, r), r + 3)
    thin = pathops.op(p, thick, OP.DIFFERENCE)
    keep = pathops.Path()
    for c in thin.contours:
        if abs(c.area) >= min_area:
            keep.addPath(c)
    return keep


def thicken(p: pathops.Path, r: float, t: float, min_area: float) -> pathops.Path:
    """The glyph's own outline offset by t (smooth curves parallel to the original), but only within t of the thin
    parts and never past the glyph's own box."""
    thin = thin_parts(p, r, min_area)
    if not list(thin.contours):
        return p
    grown = pathops.op(dilate(p, t), dilate(thin, t), OP.INTERSECTION)
    grown = pathops.op(grown, rect(*p.bounds), OP.INTERSECTION)
    return pathops.op(p, grown, OP.UNION)


def _samples(Q: np.ndarray, on: np.ndarray, step: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    """Points along one closed TrueType contour (real quadratic curves; lines subdivided too), in order, each with
    the control-polygon edge it belongs to (edge k runs from point k to point k+1)."""
    n = len(Q)
    pts, edge = [], []
    for k in range(n):
        j0, j1 = (k - 1) % n, (k + 1) % n
        if on[k]:
            if on[j1]:                                       # a straight line: edge k
                m = max(1, int(np.hypot(*(Q[j1] - Q[k])) / step))
                for t in np.linspace(0, 1, m + 1)[1:]:
                    pts.append((1 - t) * Q[k] + t * Q[j1]); edge.append(k)
            continue
        a = Q[j0] if on[j0] else (Q[j0] + Q[k]) / 2         # the quadratic piece around off-curve point k
        b = Q[j1] if on[j1] else (Q[k] + Q[j1]) / 2
        m = max(2, int((np.hypot(*(Q[k] - a)) + np.hypot(*(b - Q[k]))) / step))
        for t in np.linspace(0, 1, m + 1)[1:]:
            pts.append((1 - t) ** 2 * a + 2 * (1 - t) * t * Q[k] + t * t * b); edge.append(j0 if t < 0.5 else k)
    return np.array(pts), np.array(edge)


def _ray(p, d, segs) -> float:
    """Distance from p along unit d to the nearest outline crossing beyond 1 unit (inf if none)."""
    a, b = segs[:, :2], segs[:, 2:]
    e = b - a
    den = d[0] * e[:, 1] - d[1] * e[:, 0]
    ok = np.abs(den) > 1e-9
    w = a - p
    t = np.where(ok, (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / np.where(ok, den, 1), np.inf)
    u = np.where(ok, (w[:, 0] * d[1] - w[:, 1] * d[0]) / np.where(ok, den, 1), -1)
    hit = ok & (t > 1.0) & (u >= 0) & (u <= 1)
    return float(t[hit].min()) if hit.any() else np.inf


def _out_normals(v: np.ndarray) -> np.ndarray:
    """Outward unit normals of travel directions v (TrueType: the ink lies to the right of travel)."""
    nn = np.stack([-v[:, 1], v[:, 0]], 1)
    return nn / np.maximum(np.hypot(nn[:, 0], nn[:, 1]), 1e-9)[:, None]


def offset_thin(f: TTFont, ch: str, half: float, gmax: float, sigma: float = 30.0, zone: float = 0) -> None:
    """Thicken strokes thinner than 2 x half by moving the outline's own edges outward, each by what the stroke there
    lacks (at most gmax), measured along the real outline and smoothed along it so thickened strokes run into the
    thick ones without steps. Each edge of the control polygon moves parallel to itself (a straight edge stays
    straight and keeps its angle); each point goes to where its two moved edges meet. Curves stay curves, the number
    of points stays the same; nothing moves past the glyph's box (heights and widths kept). zone > 0 leaves the
    serifs alone: nothing within that distance of the glyph's top or bottom grows."""
    glyf = f["glyf"]
    name = f.getBestCmap()[ord(ch)]
    g = glyf[name]
    coords, ends, flags = g.getCoordinates(glyf)
    P = np.array(coords, float)
    x0, y0, x1, y1 = P[:, 0].min(), P[:, 1].min(), P[:, 0].max(), P[:, 1].max()
    conts, start = [], 0
    for end in ends:
        idx = np.arange(start, end + 1)
        on = np.array([bool(flags[i] & 1) for i in idx])
        conts.append((idx, on) + _samples(P[idx], on))
        start = end + 1
    segs = np.vstack([np.hstack([S, np.roll(S, -1, 0)]) for _, _, S, _ in conts])
    new = P.copy()
    for idx, on, S, edge in conts:
        Q, n = P[idx], len(idx)
        nrm = _out_normals(np.roll(S, -1, 0) - np.roll(S, 1, 0))
        thick = np.array([_ray(S[i] - 0.5 * nrm[i], -nrm[i], segs) for i in range(len(S))])
        lack = np.clip((2 * half - thick) / 2, 0, gmax)
        if zone:
            lack[(S[:, 1] > y1 - zone) | (S[:, 1] < y0 + zone)] = 0
        arc = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(S, axis=0).T))])
        L = arc[-1] + np.hypot(*(S[0] - S[-1]))
        dd = np.abs(arc[:, None] - arc[None, :])
        dd = np.minimum(dd, L - dd)
        w = np.exp(-0.5 * (dd / sigma) ** 2)
        lack = (w @ lack) / w.sum(1)
        # each point moves by what the outline lacks where it is (off-curve points: at the nearest outline sample);
        # a straight edge whose two ends move differently tilts a little but stays straight
        near = np.argmin(np.hypot(S[None, :, 0] - Q[:, None, 0], S[None, :, 1] - Q[:, None, 1]), axis=1)
        m = lack[near]
        n_edge = _out_normals(np.roll(Q, -1, 0) - Q)            # edge k: point k -> k+1
        for k in range(n):
            na, nb = n_edge[k - 1], n_edge[k]                    # edges arriving at and leaving point k
            det = na[0] * nb[1] - na[1] * nb[0]
            if abs(det) < 0.25:                                  # (nearly) smooth point: move along the mean normal
                nv = na + nb
                d = nv / max(np.hypot(*nv), 1e-9) * m[k]
            else:                                                # a corner: where both moved edges meet
                d = np.linalg.solve(np.array([na, nb]), np.array([m[k], m[k]]))
                # outward-pointing corners (serif tips) must not shoot out; inside corners (where strokes meet)
                # take the full meeting point so no notch is left
                cap = (1.2 if det < 0 else 4.0) * m[k]
                if np.hypot(*d) > cap:
                    d *= cap / np.hypot(*d)
            new[idx[k]] = Q[k] + d
    new[:, 0] = np.clip(new[:, 0], x0, x1)
    new[:, 1] = np.clip(new[:, 1], y0, y1)
    g.coordinates = GlyphCoordinates([(int(round(x)), int(round(y))) for x, y in new])
    g.recalcBounds(glyf)
    f["hmtx"][name] = (f["hmtx"][name][0], g.xMin)


def bigger_dots(f: TTFont, s: float) -> None:
    """Scale the dots of . : ; by s about their centres, bottoms fixed; the advance grows by the added width."""
    cm, glyf, hmtx = f.getBestCmap(), f["glyf"], f["hmtx"]
    for ch in ".:;":
        name = cm[ord(ch)]
        g = glyf[name]
        coords, ends, _ = g.getCoordinates(glyf)
        start, grow = 0, 0.0
        for end in ends:
            pts = coords[start:end + 1]
            xs, ys = [x for x, _ in pts], [y for _, y in pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if h < 1.6 * w:                               # a dot (the semicolon's tail is tall and is left alone)
                cx, y0 = (min(xs) + max(xs)) / 2, min(ys)
                if ch == ":" and y0 > 200:                # the colon's upper dot grows about its centre
                    y0 = (min(ys) + max(ys)) / 2
                for i in range(start, end + 1):
                    x, y = coords[i]
                    coords[i] = (round(cx + (x - cx) * s), round(y0 + (y - y0) * s))
                grow = max(grow, w * (s - 1))
            start = end + 1
        g.coordinates = coords
        g.recalcBounds(glyf)
        adv, _ = hmtx[name]
        # keep the left side bearing: shift right by half the growth
        dx = round(grow / 2)
        coords2, _, _ = g.getCoordinates(glyf)
        for i in range(len(coords2)):
            x, y = coords2[i]
            coords2[i] = (x + dx, y)
        g.coordinates = coords2
        g.recalcBounds(glyf)
        hmtx[name] = (adv + round(grow), g.xMin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--chars", default="")
    ap.add_argument("--r", type=float, default=40)
    ap.add_argument("--t", type=float, default=15)
    ap.add_argument("--min-area", type=float, default=2000)
    ap.add_argument("--offset", action="store_true", help="move the outline's points instead (clean curves)")
    ap.add_argument("--half", type=float, default=45, help="--offset: thicken strokes thinner than 2x this")
    ap.add_argument("--sigma", type=float, default=30, help="--offset: smoothing along the outline (units)")
    ap.add_argument("--zone", type=float, default=0, help="--offset: leave serifs alone (within this of top/bottom)")
    ap.add_argument("--round", default="COS", help="--offset: letters whose top and bottom do grow (no serif zone)")
    ap.add_argument("--dots", type=float, default=0)
    ap.add_argument("--report", action="store_true", help="print the thin area of each char and stop")
    a = ap.parse_args()
    f = TTFont(a.src)
    for c in a.chars:
        p = glyph_path(f, c)
        if a.report:
            print(c, round(abs(thin_parts(p, a.r, a.min_area).area)))
            continue
        if a.offset:
            offset_thin(f, c, a.half, a.t, a.sigma, 0 if c in a.round else a.zone)
        else:
            write(f, c, thicken(p, a.r, a.t, a.min_area))
    if a.report:
        return
    if a.dots:
        bigger_dots(f, a.dots)
    f.save(a.dst)
    print(a.dst)


if __name__ == "__main__":
    main()
