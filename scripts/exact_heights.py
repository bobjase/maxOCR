"""Exactly equal lowercase heights (James: "the u is clearly shorter than the o"). Fonts usually let round letters
overshoot the x-height and baseline slightly; borrowed and blended glyphs also differ by a few units. Here every
lowercase letter is stretched vertically (widths kept) so its ink spans exactly one of four bands:
x-height letters [0, X]; ascenders b d f h k l [0, A]; descenders g j p q y [D, X]; t [0, T].
For i and j the stem top is matched (the dot moves with the stretch). X, A, D, T default to the most common values.
--caps also puts every capital on [0, cap height] (Q: its bowl, estimated from the counter; the tail hangs below);
--uniform-caps scales capitals in both directions (proportions kept) instead of vertically only.

    python scripts/exact_heights.py SRC.ttf DST.ttf [--x 541 --asc 828 --desc -235 --t 668] [--caps]
"""
import argparse
from collections import Counter

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from normalize_xheight import LOWER, body_top

ASC, DESC = "bdfhkl", "gjpqy"
CAPS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def bowl_bottom(f: TTFont, name: str) -> float:
    """Q: bottom of the bowl, not the tail = the counter's bottom minus the stroke at the top."""
    coords, ends, _ = f["glyf"][name].getCoordinates(f["glyf"])
    boxes, start = [], 0
    for e in ends:
        ys = [p[1] for p in coords[start:e + 1]]
        boxes.append((min(ys), max(ys)))
        start = e + 1
    if len(boxes) < 2:
        return f["glyf"][name].yMin
    outer, inner = max(boxes, key=lambda b: b[1] - b[0]), min(boxes, key=lambda b: b[1] - b[0])
    return inner[0] - (outer[1] - inner[1])


def bands(f: TTFont) -> dict[str, float]:
    cm, gl = f.getBestCmap(), f["glyf"]
    tops = {c: body_top(f, cm[ord(c)], c) for c in LOWER}
    bots = {c: gl[cm[ord(c)]].yMin for c in LOWER}
    mode = lambda vals: Counter(round(v) for v in vals).most_common(1)[0][0]
    return {"x": mode(tops[c] for c in LOWER if c not in ASC + "t"), "asc": mode(tops[c] for c in ASC),
            "desc": mode(bots[c] for c in DESC), "t": tops["t"]}


def exact(src: str, dst: str, x=None, asc=None, desc=None, t=None, caps: bool = False,
          uniform_caps: bool = False) -> dict:
    f = TTFont(src)
    for c in LOWER:
        f["glyf"][f.getBestCmap()[ord(c)]].recalcBounds(f["glyf"])
    b = bands(f)
    b.update({k: v for k, v in dict(x=x, asc=asc, desc=desc, t=t).items() if v is not None})
    cm, gs = f.getBestCmap(), f.getGlyphSet()
    if caps:
        for c in CAPS:
            f["glyf"][cm[ord(c)]].recalcBounds(f["glyf"])
        b["cap"] = Counter(f["glyf"][cm[ord(c)]].yMax for c in CAPS).most_common(1)[0][0]
    moves = {}
    for c in LOWER + (CAPS if caps else ""):
        name = cm[ord(c)]
        g = f["glyf"][name]
        if c in CAPS:
            top, bot, ttop, tbot = g.yMax, bowl_bottom(f, name) if c == "Q" else g.yMin, b["cap"], 0
        else:
            top, bot = body_top(f, name, c), g.yMin
            ttop = b["asc"] if c in ASC else b["t"] if c == "t" else b["x"]
            tbot = b["desc"] if c in DESC else 0
        s = (ttop - tbot) / (top - bot)
        dy = tbot - s * bot
        moves[c] = (round(s, 3), round(dy))
        if abs(s - 1) < 0.001 and abs(dy) < 0.5:
            continue
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(rec)
        pen = TTGlyphPen(None)
        sx = s if (uniform_caps and c in CAPS) else 1.0   # default vertical only: widths and sidebearings kept
        x0, x1 = g.xMin, g.xMax
        rec.replay(TransformPen(pen, (sx, 0, 0, s, x0 - sx * x0, dy)))   # about the left ink edge
        f["glyf"][name] = pen.glyph()
        f["glyf"][name].recalcBounds(f["glyf"])
        if sx != 1.0:
            adv, lsb = f["hmtx"][name]
            f["hmtx"][name] = (int(round(adv - (1 - sx) * (x1 - x0))), lsb)
    f.save(dst)
    return {"bands": b, "moves": moves}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    for k in ("x", "asc", "desc", "t"):
        ap.add_argument(f"--{k}", type=float)
    ap.add_argument("--caps", action="store_true", help="also put every capital on [0, cap height]")
    ap.add_argument("--uniform-caps", action="store_true", help="capitals keep their proportions (narrower when shrunk)")
    a = ap.parse_args()
    print(exact(a.src, a.dst, a.x, a.asc, a.desc, a.t, a.caps, a.uniform_caps))


if __name__ == "__main__":
    main()
