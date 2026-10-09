"""Glyph genomes for discovery by mutation (constructive representation).

A genome is an ordered list of parts drawn onto a canvas in cap units (y up from the baseline,
cap height = 1):
  - contour parts: closed Catmull-Rom splines, filled (+) or cut out (-). Seeds take them directly
    from a font's outlines (outer contours +, counters -), resampled to a fixed number of control
    points, so a seed reproduces the real glyph;
  - stroke parts: open centerlines with a width profile, added (+: spur, serif, tail, bar) or cut (-:
    gap, notch, opening);
  - a global offset that thickens (+) or thins (-) the whole glyph.
Parts are rasterized in order (later parts paint over earlier ones), then traced to TrueType contours.

Mutation operators act on geometry (move/bend control points, scale, shear, offset, stroke width and
contrast) and structure (add or remove a stroke or a cut, add a dot, split a counter open).
"""
import copy
from dataclasses import dataclass, field

import cv2
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

PX = 300            # pixels per cap unit
CONTOUR_POINTS = 24
# Minimum feature size: at 8 pt / 200 dpi the cap height is ~15.6 px, so 0.10 cap ~ 1.6 px. Added
# strokes, cuts and dots below this were the likely carriers of engine-specific gains (discovery run 2).
MIN_W, MAX_W = 0.10, 0.30
MIN_LEN = 0.15
MIN_DOT = 0.14
MAX_PARTS = 10
# Debris: small ink pieces outside the glyph's main body read as punctuation or touch neighbours, and
# cost nothing under a 0-9A-Z whitelist (discovery run 4). Pieces with at least SUBSTANTIAL x the
# largest piece's area form the body; smaller pieces survive only inside the body's box (+ margin).
SUBSTANTIAL = 0.4         # stencil halves are ~1.0; run 4 debris was 0.05-0.19
DEBRIS_MARGIN = 0.03


@dataclass
class Part:
    kind: str               # "contour" or "stroke"
    sign: int               # +1 add ink, -1 remove ink
    pts: np.ndarray         # (n, 2) control points, cap units
    w0: float = 0.0         # stroke width at start (strokes only)
    w1: float = 0.0


@dataclass
class Genome:
    parts: list[Part]
    offset: float = 0.0     # global thickening (+) / thinning (-), cap units
    sb: float = 0.08        # sidebearing each side, cap units
    meta: dict = field(default_factory=dict)

    def copy(self) -> "Genome":
        return copy.deepcopy(self)


# ---------------------------------------------------------------- geometry
def spline(pts: np.ndarray, closed: bool, per_seg: int = 16) -> np.ndarray:
    p = np.asarray(pts, float)
    if len(p) < 2:
        return p
    p = np.vstack([p[-1], p, p[0], p[1]]) if closed else np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    t = np.linspace(0, 1, per_seg, endpoint=False)[:, None]
    out = [0.5 * ((2 * p[i]) + (-p[i - 1] + p[i + 1]) * t + (2 * p[i - 1] - 5 * p[i] + 4 * p[i + 1] - p[i + 2]) * t ** 2
                  + (-p[i - 1] + 3 * p[i] - 3 * p[i + 1] + p[i + 2]) * t ** 3) for i in range(1, len(p) - 2)]
    out.append((p[1] if closed else p[-2])[None])
    return np.vstack(out)


def _resample(c: np.ndarray, n: int) -> np.ndarray:
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1))]
    t = np.linspace(0, seg[-1], n, endpoint=False)
    cc = np.vstack([c, c[:1]])
    return np.c_[np.interp(t, seg, cc[:, 0]), np.interp(t, seg, cc[:, 1])]


def bounds(g: Genome) -> tuple[float, float, float, float]:
    allp = []
    for p in g.parts:
        if p.sign < 0:
            continue
        c = spline(p.pts, p.kind == "contour")
        r = max(p.w0, p.w1) / 2 if p.kind == "stroke" else 0
        allp.append(np.r_[c.min(0) - r, c.max(0) + r])
    a = np.array(allp)
    pad = max(g.offset, 0)
    return a[:, 0].min() - pad, a[:, 1].min() - pad, a[:, 2].max() + pad, a[:, 3].max() + pad


def rasterize(g: Genome) -> tuple[np.ndarray, tuple[float, float]]:
    """Ink mask (rows top->bottom) and the cap-unit (x, y) of its top-left corner."""
    x0, y0, x1, y1 = bounds(g)
    pad = 0.05
    ox, oy = x0 - pad, y1 + pad
    W, H = int(np.ceil((x1 - x0 + 2 * pad) * PX)), int(np.ceil((y1 - y0 + 2 * pad) * PX))
    m = np.zeros((H, W), np.uint8)

    def px(c):
        return np.c_[(c[:, 0] - ox) * PX, (oy - c[:, 1]) * PX].round().astype(np.int32)

    for p in g.parts:
        val = 255 if p.sign > 0 else 0
        if p.kind == "contour":
            cv2.fillPoly(m, [px(spline(p.pts, True))], val, lineType=cv2.LINE_8)
        else:
            c = spline(p.pts, False, per_seg=32)
            seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))]
            w = p.w0 + (p.w1 - p.w0) * seg / max(seg[-1], 1e-9)
            for q, wi in zip(px(c), w):
                cv2.circle(m, tuple(int(v) for v in q), max(1, int(round(wi * PX / 2))), val, -1)
    if g.offset:
        k = int(round(abs(g.offset) * PX))
        if k:
            ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
            m = cv2.dilate(m, ker) if g.offset > 0 else cv2.erode(m, ker)
    return drop_debris(m > 0), (ox, oy)


def drop_debris(m: np.ndarray) -> np.ndarray:
    """Remove small ink pieces lying outside the box around the glyph's substantial pieces. Inner dots,
    bars and slashes stay; so do the halves of a split (stencil) glyph."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    if n <= 2:
        return m
    area = st[1:, cv2.CC_STAT_AREA]
    body = 1 + np.flatnonzero(area >= SUBSTANTIAL * area.max())
    x0, y0 = st[body, 0].min(), st[body, 1].min()
    x1, y1 = (st[body, 0] + st[body, 2]).max(), (st[body, 1] + st[body, 3]).max()
    pad = int(round(DEBRIS_MARGIN * PX))
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        keep[i] = x >= x0 - pad and y >= y0 - pad and x + w <= x1 + pad and y + h <= y1 + pad
    return m & keep[lab]


# ---------------------------------------------------------------- seeds
class _Flatten(BasePen):
    def __init__(self, gs):
        super().__init__(gs)
        self.contours, self.cur = [], []

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, a, b, c):
        p0 = np.array(self.cur[-1])
        for t in np.linspace(0, 1, 9)[1:]:
            u = 1 - t
            self.cur.append(tuple(u ** 3 * p0 + 3 * u * u * t * np.array(a) + 3 * u * t * t * np.array(b) + t ** 3 * np.array(c)))

    def _qCurveToOne(self, a, b):
        p0 = np.array(self.cur[-1])
        for t in np.linspace(0, 1, 9)[1:]:
            u = 1 - t
            self.cur.append(tuple(u * u * p0 + 2 * u * t * np.array(a) + t * t * np.array(b)))

    def _closePath(self):
        if len(self.cur) > 2:
            self.contours.append(np.array(self.cur))
        self.cur = []

    _endPath = _closePath


def from_glyph(font: str, ch: str, n_points: int = CONTOUR_POINTS) -> Genome:
    """Seed genome reproducing a font's glyph: outer contours as + parts, counters as - parts."""
    f = TTFont(font)
    gs, cmap = f.getGlyphSet(), f.getBestCmap()
    from fontTools.pens.boundsPen import BoundsPen
    bp = BoundsPen(gs)
    gs[cmap[ord("H")]].draw(bp)
    cap = bp.bounds[3] - bp.bounds[1]
    pen = _Flatten(gs)
    gs[cmap[ord(ch)]].draw(pen)
    parts = []
    for c in pen.contours:
        c = c / cap
        area = 0.5 * np.sum(c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1])
        # TrueType: outer contours clockwise (negative area in y-up); counters counter-clockwise.
        sign = 1 if area < 0 else -1
        n = max(8, int(n_points * min(1.0, abs(area) * 8)))      # small contours get fewer points
        parts.append(Part("contour", sign, _resample(c, n)))
    parts.sort(key=lambda p: -p.sign)                             # fills first, then counters
    return Genome(parts, meta={"seed": f"{font.split('/')[-1]}:{ch}"})


def primitive(kind: str) -> Genome:
    t = np.linspace(0, 2 * np.pi, 16, endpoint=False)

    def ring(cx, rx, ry, w):
        outer = np.c_[cx + rx * np.cos(t), 0.5 + ry * np.sin(t)]
        inner = np.c_[cx + (rx - w) * np.cos(t), 0.5 + (ry - w) * np.sin(t)]
        return [Part("contour", 1, outer), Part("contour", -1, inner)]

    if kind == "ellipse":
        return Genome(ring(0.45, 0.45, 0.51, 0.12))
    if kind == "capsule":
        return Genome(ring(0.30, 0.30, 0.51, 0.11))
    if kind == "diamond":
        o = np.array([[0.32, 1.0], [0.64, 0.5], [0.32, 0.0], [0.0, 0.5]])
        i = np.array([[0.32, 0.80], [0.50, 0.5], [0.32, 0.20], [0.14, 0.5]])
        return Genome([Part("contour", 1, _resample(o, 16)), Part("contour", -1, _resample(i, 16))])
    raise ValueError(kind)


# ---------------------------------------------------------------- mutation
OPS = ["jitter", "bend", "scale", "shear", "offset", "stroke_add", "cut_add", "dot", "remove", "width", "smooth",
       "stress", "contrast"]
OP_P = np.array([.16, .12, .11, .06, .07, .11, .07, .04, .05, .05, .04, .06, .06])


def _point_on(g: Genome, rng) -> np.ndarray:
    p = [q for q in g.parts if q.sign > 0][int(rng.integers(len([q for q in g.parts if q.sign > 0])))]
    c = spline(p.pts, p.kind == "contour")
    return c[int(rng.integers(len(c)))]


def mutate(g: Genome, rng: np.random.Generator, n_ops: int | None = None) -> tuple[Genome, list[str]]:
    g = g.copy()
    done = []
    for _ in range(n_ops or int(rng.integers(1, 4))):
        op = str(rng.choice(OPS, p=OP_P / OP_P.sum()))
        p = g.parts[int(rng.integers(len(g.parts)))]
        n = len(p.pts)
        if op == "jitter":
            p.pts[int(rng.integers(n))] += rng.normal(0, 0.025, 2)
        elif op == "bend" and n >= 3:
            i = int(rng.integers(n))
            k = int(rng.integers(2, max(3, n // 3)))
            idx = [(i + j) % n for j in range(-k, k + 1)] if p.kind == "contour" else \
                [j for j in range(max(0, i - k), min(n, i + k + 1))]
            w = np.hanning(len(idx) + 2)[1:-1]
            d = rng.normal(0, 0.04, 2)
            p.pts[idx] += w[:, None] * d
        elif op == "scale":
            kx, ky = np.exp(rng.normal(0, 0.06, 2))
            cx = np.mean(np.vstack([q.pts for q in g.parts])[:, 0])
            for q in g.parts:
                q.pts[:, 0] = cx + (q.pts[:, 0] - cx) * kx
                q.pts[:, 1] = q.pts[:, 1] * ky
                q.w0 *= np.sqrt(kx * ky)
                q.w1 *= np.sqrt(kx * ky)
        elif op == "shear":
            k = rng.normal(0, 0.05)
            for q in g.parts:
                q.pts[:, 0] += k * (q.pts[:, 1] - 0.5)
        elif op == "offset":
            g.offset = float(np.clip(g.offset + rng.normal(0, 0.008), -0.03, 0.04))
        elif op in ("stroke_add", "cut_add") and len(g.parts) < MAX_PARTS:
            a = _point_on(g, rng)
            ang = rng.uniform(0, 2 * np.pi)
            L = rng.uniform(MIN_LEN, 0.35 if op == "stroke_add" else 0.25)
            b = a + L * np.array([np.cos(ang), np.sin(ang)])
            mid = (a + b) / 2 + rng.normal(0, 0.02, 2)
            w = rng.uniform(MIN_W, 0.16)
            g.parts.append(Part("stroke", 1 if op == "stroke_add" else -1, np.vstack([a, mid, b]), w, w * rng.uniform(0.6, 1.1)))
        elif op == "dot" and len(g.parts) < MAX_PARTS:
            a = _point_on(g, rng) * 0.5 + np.array([0.3, 0.5]) * 0.5
            r = rng.uniform(MIN_DOT / 2, 0.11)
            g.parts.append(Part("stroke", 1, np.vstack([a, a + [1e-3, 0], a + [2e-3, 0]]), 2 * r, 2 * r))
        elif op == "remove":
            extra = [i for i, q in enumerate(g.parts) if q.kind == "stroke"]
            if extra:
                g.parts.pop(extra[int(rng.integers(len(extra)))])
            else:
                continue
        elif op == "width" and p.kind == "stroke":
            k = float(np.exp(rng.normal(0, 0.2)))
            p.w0, p.w1 = p.w0 * k, p.w1 * k
        elif op == "smooth" and p.kind == "contour" and n >= 6:
            p.pts = 0.5 * p.pts + 0.25 * (np.roll(p.pts, 1, 0) + np.roll(p.pts, -1, 0))
        elif op in ("stress", "contrast"):
            # Act on a counter (inner contour): rotating it moves the thick parts of the stroke to a
            # diagonal (stress); stretching it unevenly trades side thickness for top/bottom (contrast).
            counters = [q for q in g.parts if q.kind == "contour" and q.sign < 0]
            if not counters:
                continue
            q = counters[int(rng.integers(len(counters)))]
            c = q.pts.mean(0)
            if op == "stress":
                a = np.deg2rad(rng.normal(0, 8))
                R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
                q.pts = c + (q.pts - c) @ R.T
            else:
                q.pts = c + (q.pts - c) * np.exp(rng.normal(0, 0.06, 2))
        else:
            continue
        done.append(op)
    for q in g.parts:
        if q.kind == "stroke":
            q.w0, q.w1 = float(np.clip(q.w0, MIN_W, MAX_W)), float(np.clip(q.w1, MIN_W, MAX_W))
        q.pts[:, 1] = np.clip(q.pts[:, 1], -0.35, 1.2)
    return g, done


# ---------------------------------------------------------------- font assembly
def trace(g: Genome, cap_units: int = 700):
    m, (ox, oy) = rasterize(g)
    cnts, hier = cv2.findContours(m.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out, xs = [], []
    if hier is None:
        return out, 0, 0
    for c, h in zip(cnts, hier[0]):
        c = cv2.approxPolyDP(c, 0.8, True)[:, 0, :]
        if len(c) < 3:
            continue
        pts = [(int(round((ox + x / PX) * cap_units)), int(round((oy - y / PX) * cap_units))) for x, y in c]
        area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2
        hole = h[3] != -1
        if (not hole and area > 0) or (hole and area < 0):
            pts = pts[::-1]
        out.append(pts)
        xs += [p[0] for p in pts]
    return out, (min(xs) if xs else 0), (max(xs) if xs else 0)


def with_glyphs(base: str, genomes: dict[str, Genome], path: str, cap_units: int = 700) -> str:
    """Copy `base` (cap height = cap_units) with the given characters' glyphs replaced by genomes."""
    f = TTFont(base)
    cmap = f.getBestCmap()
    for ch, g in genomes.items():
        name = cmap[ord(ch)]
        contours, x0, x1 = trace(g, cap_units)
        sb = int(round(g.sb * cap_units))
        pen = TTGlyphPen(None)
        for pts in contours:
            pen.moveTo((pts[0][0] - x0 + sb, pts[0][1]))
            for x, y in pts[1:]:
                pen.lineTo((x - x0 + sb, y))
            pen.closePath()
        f["glyf"][name] = pen.glyph()
        f["glyf"][name].recalcBounds(f["glyf"])
        f["hmtx"][name] = (int(x1 - x0 + 2 * sb), sb)
    f.save(path)
    return path
