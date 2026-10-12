"""Un-average blended letters. Most of the lowercase is an equal SDF blend of IBM Plex Serif, Spectral and Gelasio
(add_lowercase.py), and where their joins and serifs differ the average has notches and lumps. For each letter, each
source's real outline is fitted to our glyph's ink box (independent x and y scale, then position), rasterized, and
compared with ours (overlap / union of ink); the closest one replaces ours. The result keeps our letter's size,
width and position with a clean, curved outline.

    python scripts/unblend.py SRC.ttf DST.ttf --chars qrnmdbphk [--sources ibmplexserif,spectral,gelasio]
"""
import argparse
import json
from pathlib import Path

import freetype
import numpy as np
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]


def raster(path: str, c: str, upem: int) -> tuple[np.ndarray, int, int]:
    face = freetype.Face(path)
    face.set_pixel_sizes(0, upem)
    face.load_glyph(face.get_char_index(ord(c)), freetype.FT_LOAD_NO_HINTING | freetype.FT_LOAD_RENDER)
    b = face.glyph.bitmap
    img = np.array(b.buffer, dtype=np.uint8).reshape(b.rows, b.pitch)[:, :b.width] >= 128
    return img, face.glyph.bitmap_left, face.glyph.bitmap_top


def fitted_glyph(donor: TTFont, c: str, box: tuple, uniform: bool = False) -> object:
    """Donor's outline for c, scaled and moved so its ink box equals box = (xMin, yMin, xMax, yMax); uniform: scale by
    the height only (the donor keeps its own width, centred on the box)."""
    gs, cm = donor.getGlyphSet(), donor.getBestCmap()
    rec = DecomposingRecordingPen(gs)
    gs[cm[ord(c)]].draw(rec)
    from fontTools.pens.boundsPen import BoundsPen
    bp = BoundsPen(None)
    rec.replay(bp)
    x0, y0, x1, y1 = bp.bounds
    X0, Y0, X1, Y1 = box
    sx, sy = (X1 - X0) / (x1 - x0), (Y1 - Y0) / (y1 - y0)
    dx = X0 - sx * x0
    if uniform:
        sx = sy
        dx = (X0 + X1) / 2 - sx * (x0 + x1) / 2
    tt = TTGlyphPen(None)
    rec.replay(TransformPen(Cu2QuPen(tt, max_err=0.8, reverse_direction="CFF " in donor),
                            (sx, 0, 0, sy, dx, Y0 - sy * y0)))
    return tt.glyph()


def iou(a, b) -> float:
    (ia, la, ta), (ib, lb, tb) = a, b
    x0, x1 = min(la, lb), max(la + ia.shape[1], lb + ib.shape[1])
    y0, y1 = min(ta - ia.shape[0], tb - ib.shape[0]), max(ta, tb)
    A = np.zeros((y1 - y0, x1 - x0), bool)
    B = np.zeros_like(A)
    A[y1 - ta:y1 - ta + ia.shape[0], la - x0:la - x0 + ia.shape[1]] = ia
    B[y1 - tb:y1 - tb + ib.shape[0], lb - x0:lb - x0 + ib.shape[1]] = ib
    return float((A & B).sum() / max((A | B).sum(), 1))


def unblend(src: str, dst: str, chars: str, sources: list[str], tmp_dir: Path, uniform: str = "") -> dict:
    path_of = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    base = TTFont(src)
    upem = base["head"].unitsPerEm
    cm = base.getBestCmap()
    picks = {}
    for c in chars:
        name = cm[ord(c)]
        g = base["glyf"][name]
        g.recalcBounds(base["glyf"])
        box = (g.xMin, g.yMin, g.xMax, g.yMax)
        ours = raster(src, c, upem)
        best = None
        for s in sources:
            trial = TTFont(src)
            ng = fitted_glyph(TTFont(path_of[s]), c, box, uniform=c in uniform)
            trial["glyf"][name] = ng
            p = str(tmp_dir / f"unblend_{ord(c):04X}_{s}.ttf")
            trial.save(p)
            score = iou(ours, raster(p, c, upem))
            if best is None or score > best[0]:
                best = (score, s, ng)
        base["glyf"][name] = best[2]
        base["glyf"][name].recalcBounds(base["glyf"])
        adv, _ = base["hmtx"][name]
        if c in uniform:   # keep the old sidebearings around the new width
            old_w = box[2] - box[0]
            adv = int(round(adv + (base["glyf"][name].xMax - base["glyf"][name].xMin) - old_w))
            shift = box[0] - base["glyf"][name].xMin
            coords, _, _ = base["glyf"][name].getCoordinates(base["glyf"])
            coords.translate((shift, 0))
            base["glyf"][name].coordinates = coords
            base["glyf"][name].recalcBounds(base["glyf"])
        base["hmtx"][name] = (adv, base["glyf"][name].xMin)
        picks[c] = (best[1], round(best[0], 3))
    base.save(dst)
    return picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--chars", required=True)
    ap.add_argument("--sources", default="ibmplexserif,spectral,gelasio")
    ap.add_argument("--uniform", default="", help="letters fitted by height only (keep the source's own width)")
    a = ap.parse_args()
    tmp = Path(a.dst).parent / "unblend_tmp"
    tmp.mkdir(exist_ok=True)
    print(unblend(a.src, a.dst, a.chars, a.sources.split(","), tmp, a.uniform))


if __name__ == "__main__":
    main()
