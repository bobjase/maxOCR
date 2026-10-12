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
rounding (an elliptical quarter in the corner where the two tangents meet: brackets, rounded ends).
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


def redraw_contour(P: np.ndarray, nodes: list) -> list:
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
        idx = np.arange(i0 + 1, i1 + (n if i1 <= i0 else 0)) % n
        Q = P[idx] if len(idx) else np.vstack([p0, p3])
        segs.append(("curve",) + tuple(fit_span(Q, p0, p3, tans[k][1], tans[(k + 1) % m][0])))
    return segs


def draw_segs(segs, pen) -> None:
    pen.moveTo(tuple(map(float, segs[0][1])))
    for s in segs:
        if s[0] == "line":
            pen.lineTo(tuple(map(float, s[2])))
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
    path = pathops.Path()
    pen = path.getPen()
    for ci, P in enumerate(polys):
        nodes = spec.get(str(ci))
        if nodes:
            draw_segs(redraw_contour(P, nodes), pen)
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
