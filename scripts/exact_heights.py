"""Exactly equal lowercase heights (James: "the u is clearly shorter than the o"). Fonts usually let round letters
overshoot the x-height and baseline slightly; borrowed and blended glyphs also differ by a few units. Here every
lowercase letter is stretched vertically (widths kept) so its ink spans exactly one of four bands:
x-height letters [0, X]; ascenders b d f h k l [0, A]; descenders g j p q y [D, X]; t [0, T].
For i and j the stem top is matched (the dot moves with the stretch). X, A, D, T default to the most common values.

    python scripts/exact_heights.py SRC.ttf DST.ttf [--x 541 --asc 828 --desc -235 --t 668]
"""
import argparse
from collections import Counter

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from normalize_xheight import LOWER, body_top

ASC, DESC = "bdfhkl", "gjpqy"


def bands(f: TTFont) -> dict[str, float]:
    cm, gl = f.getBestCmap(), f["glyf"]
    tops = {c: body_top(f, cm[ord(c)], c) for c in LOWER}
    bots = {c: gl[cm[ord(c)]].yMin for c in LOWER}
    mode = lambda vals: Counter(round(v) for v in vals).most_common(1)[0][0]
    return {"x": mode(tops[c] for c in LOWER if c not in ASC + "t"), "asc": mode(tops[c] for c in ASC),
            "desc": mode(bots[c] for c in DESC), "t": tops["t"]}


def exact(src: str, dst: str, x=None, asc=None, desc=None, t=None) -> dict:
    f = TTFont(src)
    for c in LOWER:
        f["glyf"][f.getBestCmap()[ord(c)]].recalcBounds(f["glyf"])
    b = bands(f)
    b.update({k: v for k, v in dict(x=x, asc=asc, desc=desc, t=t).items() if v is not None})
    cm, gs = f.getBestCmap(), f.getGlyphSet()
    moves = {}
    for c in LOWER:
        name = cm[ord(c)]
        g = f["glyf"][name]
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
        rec.replay(TransformPen(pen, (1, 0, 0, s, 0, dy)))   # vertical only: widths and sidebearings kept
        f["glyf"][name] = pen.glyph()
        f["glyf"][name].recalcBounds(f["glyf"])
    f.save(dst)
    return {"bands": b, "moves": moves}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    for k in ("x", "asc", "desc", "t"):
        ap.add_argument(f"--{k}", type=float)
    a = ap.parse_args()
    print(exact(a.src, a.dst, a.x, a.asc, a.desc, a.t))


if __name__ == "__main__":
    main()
