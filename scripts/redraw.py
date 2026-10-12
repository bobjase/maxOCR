"""Redraw a contour of one of our glyphs from chosen nodes, the way a type designer cleans up an outline by hand: keep
only the nodes named (extremes, corners), delete everything between them, and draw each stretch between two nodes as
one curve (or one straight line) that follows our outline's course. Lumps and notches inside a stretch do not pull the
new curve (robust fit), so they disappear; the letter keeps its own size, proportions and stroke.

Spec (JSON): {"8": {"0": [[x, y, kind, span], ...], "1": [...]}} - per character, per contour index (contours not named
are kept exactly as they are), the nodes in any order (sorted along the contour). x, y: roughly where the node is; it is
snapped onto the outline. kind:
  h  horizontal tangent (top or bottom of a curve; snapped to the local top/bottom, middle of a flat)
  v  vertical tangent (left or right side of a curve; snapped likewise)
  H, V  the same, but kept exactly at x, y (the outline there is a lump)
  s  smooth: tangent taken from the outline there
  c  corner: incoming and outgoing directions taken from the outline on either side
  p  a corner placed exactly at x, y (not snapped)
span: what is drawn from this node to the next: "c" one curve following our outline, "l" a straight line, "r" a clean
rounding (an elliptical quarter in the corner where the two tangents meet: brackets, rounded ends), "k" keep our
original outline unchanged up to the next node (so an edit can touch only the messy stretch), "s" a plain smooth
curve along the two tangents (handles a third of the chord; not fitted to the old outline, which is wrong there).
An optional fifth value gives the tangent's angle in degrees (a line's slope; its direction follows the outline), or
[in, out]: the directions of travel arriving at and leaving a corner, in degrees, in the order the nodes are written.

    python scripts/redraw.py SRC.ttf DST.ttf SPEC.json [--chars 8]
"""
import argparse
import json
import math

import numpy as np
import pathops
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from scipy.optimize import least_squares

from fair_outlines import contours_of
from glyph_edit import write


def _unit(v):
    n = math.hypot(*v)
    return np.asarray(v, float) / n if n else np.asarray(v, float)


def snap(P: np.ndarray, x: float, y: float, kind: str) -> tuple[int, np.ndarray]:
    """Index of the outline point for this node, and the node's exact position."""
    n = len(P)
    i = int(np.argmin(np.hypot(P[:, 0] - x, P[:, 1] - y)))
    if kind in "HVp":
        return i, np.array([x, y], float)
    if kind in "hv":
        a = 1 if kind == "h" else 0
        win = np.arange(i - 30, i + 31) % n
        vals = P[win, a]
        # the local extreme closer to the given value (top vs bottom, left vs right)
        k = int(np.argmax(vals)) if abs(vals.max() - (y if a else x)) <= abs(vals.min() - (y if a else x)) else int(np.argmin(vals))
        target = vals[k]
        flat = np.flatnonzero(np.abs(vals - target) <= 2.0)
        run = [k]                                   # the flat stretch around the extreme: put the node in its middle
        while run[0] - 1 in flat:
            run.insert(0, run[0] - 1)
        while run[-1] + 1 in flat:
            run.append(run[-1] + 1)
        j = int(win[run[len(run) // 2]])
        p = P[j].copy()
        p[a] = target
        return j, p
    if kind == "c":
        best, bi = -1.0, i                          # the sharpest turn nearby
        for j in range(i - 8, i + 9):
            a, b = _unit(P[j % n] - P[(j - 5) % n]), _unit(P[(j + 5) % n] - P[j % n])
            turn = math.acos(max(-1.0, min(1.0, float(a @ b))))
            if turn > best:
                best, bi = turn, j % n
        return bi, P[bi].copy()
    return i, P[i].copy()


def tangents(P: np.ndarray, i: int, kind: str, angle=None) -> tuple[np.ndarray, np.ndarray]:
    """Direction of travel arriving at and leaving the node."""
    n = len(P)
    d = P[(i + 3) % n] - P[(i - 3) % n]
    if isinstance(angle, list):
        return tuple(np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) for a in angle)
    if angle is not None:
        t = np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])
        t = t if t @ d >= 0 else -t
        return t, t
    if kind in "hH":
        t = np.array([math.copysign(1, d[0]), 0.0])
        return t, t
    if kind in "vV":
        t = np.array([0.0, math.copysign(1, d[1])])
        return t, t
    if kind == "s":
        t = _unit(P[(i + 5) % n] - P[(i - 5) % n])
        return t, t
    return _unit(P[i] - P[(i - 8) % n]), _unit(P[(i + 8) % n] - P[i])


def fit_span(Q: np.ndarray, p0, p3, t0, t1) -> list[np.ndarray]:
    """One cubic from p0 (leaving along t0) to p3 (arriving along t1) that follows the points Q; robust, so a lump or
    notch among Q does not pull it."""
    chord = float(np.hypot(*(p3 - p0)))
    ts = np.linspace(0, 1, 400)[:, None]

    def curve(ab):
        p1, p2 = p0 + ab[0] * t0, p3 - ab[1] * t1
        return ((1 - ts) ** 3) * p0 + 3 * ((1 - ts) ** 2) * ts * p1 + 3 * (1 - ts) * ts ** 2 * p2 + ts ** 3 * p3

    def res(ab):
        C = curve(ab)
        return np.sqrt(((Q[:, None, :] - C[None, :, :]) ** 2).sum(-1).min(1))

    r = least_squares(res, [chord / 3, chord / 3], bounds=([1.0, 1.0], [1.5 * chord, 1.5 * chord]),
                      loss="soft_l1", f_scale=2.0)
    a, b = r.x
    return [p0, p0 + a * t0, p3 - b * t1, p3]


def round_span(p0, p3, t0, t1) -> list[np.ndarray]:
    """A clean rounding from p0 (leaving along t0) to p3 (arriving along t1): an elliptical quarter in the corner where
    the two tangent lines meet (handles 0.5523 of the way to that corner), not fitted to the old outline."""
    A = np.column_stack([t0, -t1])
    if abs(np.linalg.det(A)) < 1e-6:
        return fit_span(np.vstack([p0, p3]), p0, p3, t0, t1)
    s, u = np.linalg.solve(A, p3 - p0)
    X = p0 + s * t0
    return [p0, p0 + 0.5523 * (X - p0), p3 + 0.5523 * (X - p3), p3]


def original_segments(f: TTFont, name: str) -> list[list]:
    """Each contour's own TrueType segments, ("line", p0, p1) or ("quad", p0, c, p1), starting at its first on-curve
    point (the same start and direction as contours_of)."""
    g = f["glyf"][name]
    coords, ends, flags = g.getCoordinates(f["glyf"])
    out, start = [], 0
    for e in ends:
        pts = [(np.array(coords[i], float), bool(flags[i] & 1)) for i in range(start, e + 1)]
        start = e + 1
        if not any(on for _, on in pts):
            pts.insert(1, ((pts[0][0] + pts[1][0]) / 2, True))
        k = next(i for i, (_, on) in enumerate(pts) if on)
        pts = pts[k:] + pts[:k]
        # expand implied on-curve points between two off-curve points
        full = []
        for i, (q, on) in enumerate(pts):
            full.append((q, on))
            nq, non = pts[(i + 1) % len(pts)]
            if not on and not non:
                full.append(((q + nq) / 2, True))
        segs, i, n = [], 0, len(full)
        while i < n:
            p0 = full[i][0]
            q, on = full[(i + 1) % n]
            if on:
                segs.append(("line", p0, q)); i += 1
            else:
                segs.append(("quad", p0, q, full[(i + 2) % n][0])); i += 2
        out.append(segs)
    return out


def _seg_point(sg, t):
    if sg[0] == "line":
        return (1 - t) * sg[1] + t * sg[2]
    return (1 - t) ** 2 * sg[1] + 2 * (1 - t) * t * sg[2] + t * t * sg[3]


def _locate(segs, p) -> tuple[int, float]:
    best = (1e18, 0, 0.0)
    ts = np.linspace(0, 1, 65)
    for si, sg in enumerate(segs):
        pts = np.array([_seg_point(sg, t) for t in ts])
        d = np.hypot(*(pts - p).T)
        k = int(np.argmin(d))
        if d[k] < best[0]:
            best = (d[k], si, ts[k])
    return best[1], best[2]


def _sub(sg, ta, tb):
    """The piece of a segment between parameters ta < tb."""
    if sg[0] == "line":
        return ("line", _seg_point(sg, ta), _seg_point(sg, tb))
    p0, c, p1 = sg[1], sg[2], sg[3]
    a, b = _seg_point(sg, ta), _seg_point(sg, tb)
    # the sub-curve's control point is the blossom B(ta, tb)
    ctrl = (1 - ta) * (1 - tb) * p0 + ((1 - ta) * tb + ta * (1 - tb)) * c + ta * tb * p1
    return ("quad", a, ctrl, b)


def kept_stretch(segs, p0, p3) -> list:
    """Our original outline from p0 to p3 (both on it), going forward."""
    s0, t0 = _locate(segs, p0)
    s1, t1 = _locate(segs, p3)
    out = []
    if s0 == s1 and t1 >= t0:
        out.append(_sub(segs[s0], t0, t1))
    else:
        out.append(_sub(segs[s0], t0, 1.0))
        k = (s0 + 1) % len(segs)
        while k != s1:
            out.append(segs[k]); k = (k + 1) % len(segs)
        out.append(_sub(segs[s1], 0.0, t1))
    out = [sg for sg in out if np.hypot(*(sg[-1] - sg[1])) > 1e-6]
    # start and end exactly at the nodes
    out[0] = (out[0][0], np.asarray(p0, float)) + tuple(out[0][2:])
    out[-1] = tuple(out[-1][:-1]) + (np.asarray(p3, float),)
    return out


def redraw_contour(P: np.ndarray, nodes: list, original=None) -> list:
    snapped = []
    for x, y, kind, span, *angle in nodes:
        i, p = snap(P, x, y, kind)
        snapped.append((i, p, kind, span, angle[0] if angle else None))
    # a node's span runs to the next node in the order written; if they were written against the contour's own
    # direction, each stretch takes the span of the node at its far end instead
    n = len(P)
    m = len(snapped)
    forward = sum((snapped[(k + 1) % m][0] - snapped[k][0]) % n for k in range(m)) == n
    if not forward:
        flip = lambda a: [a[1] + 180, a[0] + 180] if isinstance(a, list) else a
        snapped = [(i, p, kind, snapped[(k - 1) % m][3], flip(ang)) for k, (i, p, kind, _, ang) in enumerate(snapped)]
    snapped.sort(key=lambda s: s[0])
    tans = [tangents(P, i, kind, ang) for i, _, kind, _, ang in snapped]
    # a smooth node next to a straight line takes the line's direction (no kink where curve meets line)
    for k, (i, p, kind, span, ang) in enumerate(snapped):
        if kind in "hHvVs" and ang is None:
            prev = snapped[k - 1]
            if prev[3] == "l":
                t = _unit(p - prev[1]); tans[k] = (t, t)
            if span == "l":
                t = _unit(snapped[(k + 1) % m][1] - p); tans[k] = (t, t)
    segs = []
    for k in range(m):
        i0, p0, _, span, _ = snapped[k]
        i1, p3, _, _, _ = snapped[(k + 1) % m]
        if span == "l":
            segs.append(("line", p0, p3))
            continue
        if span == "r":
            segs.append(("curve",) + tuple(round_span(p0, p3, tans[k][1], tans[(k + 1) % m][0])))
            continue
        if span == "k":
            segs.extend(kept_stretch(original, p0, p3))
            continue
        if span == "s":
            h = float(np.hypot(*(p3 - p0))) / 3
            segs.append(("curve", p0, p0 + h * tans[k][1], p3 - h * tans[(k + 1) % m][0], p3))
            continue
        idx = np.arange(i0 + 1, i1 + (n if i1 <= i0 else 0)) % n
        Q = P[idx] if len(idx) else np.vstack([p0, p3])
        segs.append(("curve",) + tuple(fit_span(Q, p0, p3, tans[k][1], tans[(k + 1) % m][0])))
    return segs


def draw_segs(segs, pen) -> None:
    pen.moveTo(tuple(map(float, segs[0][1])))
    for s in segs:
        if s[0] == "line":
            pen.lineTo(tuple(map(float, s[2])))
        elif s[0] == "quad":
            pen.qCurveTo(tuple(map(float, s[2])), tuple(map(float, s[3])))
        else:
            pen.curveTo(*(tuple(map(float, q)) for q in s[2:5]))
    pen.closePath()


def original_contours(f: TTFont, name: str) -> list[list]:
    rec = RecordingPen()
    f.getGlyphSet()[name].draw(rec)
    out, cur = [], []
    for op, args in rec.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            out.append(cur); cur = []
    return out


def redraw_glyph(f: TTFont, ch: str, spec: dict) -> pathops.Path:
    name = f.getBestCmap()[ord(ch)]
    polys = contours_of(f, name)
    originals = original_contours(f, name)
    oseg = original_segments(f, name)
    path = pathops.Path()
    pen = path.getPen()
    for ci, P in enumerate(polys):
        nodes = spec.get(str(ci))
        if nodes:
            draw_segs(redraw_contour(P, nodes, oseg[ci]), pen)
        else:
            for op, args in originals[ci]:
                getattr(pen, op)(*args)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("spec")
    ap.add_argument("--chars", help="only these characters of the spec")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    f = TTFont(a.src)
    for ch, cs in spec.items():
        if a.chars and ch not in a.chars:
            continue
        write(f, ch, redraw_glyph(f, ch, cs))
    f.save(a.dst)
    print(a.dst, "".join(c for c in spec if not a.chars or c in a.chars))


if __name__ == "__main__":
    main()
