"""Weight variant of a font: every glyph's outline grown (bold > 0) or shrunk (< 0) by a fixed offset in
font units, via the SDF of a raster of the outline (MaxOCR builds use straight segments only). Spacing kept: each glyph's
advance grows by twice the offset so sidebearings stay the same. Features (calt/kern) are copied unchanged.

    python scripts/weight_variant.py SRC.ttf DST.ttf OFFSET_UNITS
"""
import sys

import cv2
import numpy as np
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from scipy.ndimage import distance_transform_edt

SCALE = 0.5    # px per font unit for the working raster (cap 700 units -> 350 px)


def main():
    src, dst, off = sys.argv[1], sys.argv[2], float(sys.argv[3])
    f = TTFont(src)
    cm = f.getBestCmap()
    for code, name in cm.items():
        g = f["glyf"][name]
        if g.numberOfContours <= 0:
            continue
        g.recalcBounds(f["glyf"])
        x0, y0, x1, y1 = g.xMin, g.yMin, g.xMax, g.yMax
        pad = int(abs(off) * SCALE) + 4
        W, H = int((x1 - x0) * SCALE) + 2 * pad, int((y1 - y0) * SCALE) + 2 * pad
        mask = np.zeros((H, W), np.uint8)
        coords, ends, _ = g.getCoordinates(f["glyf"])
        start = 0
        polys = []
        for e in ends:
            pts = np.array(coords[start:e + 1], float)
            polys.append(np.c_[(pts[:, 0] - x0) * SCALE + pad, (y1 - pts[:, 1]) * SCALE + pad].round().astype(np.int32))
            start = e + 1
        cv2.fillPoly(mask, polys, 1)   # even-odd fill: outer contours and counters
        ink = mask.astype(bool)
        sdf = distance_transform_edt(~ink) - distance_transform_edt(ink)
        grown = (sdf < off * SCALE).astype(np.uint8)
        cnts, hier = cv2.findContours(grown, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        pen = TTGlyphPen(None)
        for c, h in zip(cnts, hier[0]):
            c = cv2.approxPolyDP(c, 0.7, True)[:, 0, :]
            if len(c) < 3:
                continue
            # +off keeps the left sidebearing: the grown ink starts where the old ink did.
            pts = [(int(round((px - pad) / SCALE + x0 + off)), int(round(y1 - (py - pad) / SCALE))) for px, py in c]
            area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2
            hole = h[3] != -1
            if (not hole and area > 0) or (hole and area < 0):
                pts = pts[::-1]
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
        f["glyf"][name] = pen.glyph()
        f["glyf"][name].recalcBounds(f["glyf"])
        adv, lsb = f["hmtx"][name]
        f["hmtx"][name] = (int(round(adv + 2 * off)), lsb)
    f.save(dst)
    print(dst)


if __name__ == "__main__":
    main()
