"""Faint disambiguation marks built into the digits (James, 2026-10-21: "What are the most common scan errors? ...
add disambiguation indicators", "half underlines which are left/right aligned", "or underlines in the whitespace
after"). MaxOCR's digit-for-digit confusions (out/report/digit_confusions.csv: 8>0, 5>6, 8>3, 6>4, 8>4, 3>2, 6>0, 6>5)
split into two groups with every common pair across them: L = 2 6 8, R = the other digits. Every digit carries a mark
and letters none, so digits read as letters (0>O, 5>S, 1>l) are caught too.

The mark is a stipple: tiny dots covering about 15% of a hairline, which prints and scans as faint grey.
  H1: a half-underline below the digit, left half for L, right half for R.
  H2: a short dash in the gap after the digit, low for L, high for R.

    python scripts/digit_marks.py build SRC_TEXT.ttf OUTDIR     (writes h1t.ttf h2t.ttf, then smart_features -> h1.ttf h2.ttf)
    python scripts/digit_marks.py test                          (four engines, numbers, ten conditions -> out/report/digit_marks.csv)
"""
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

L_DIGITS = "268"
DOT_W, DOT_H, PITCH = 8, 30, 50          # font units: 8 x 30 dots every 50 units -> about 15% of the line covered
UNDER_Y = -70                            # top of the under-mark, below the baseline (digits sit on y = 0)


def stipple(pen, x0, x1, y):
    x = x0
    while x + DOT_W <= x1:
        pen.moveTo((x, y)); pen.lineTo((x, y + DOT_H)); pen.lineTo((x + DOT_W, y + DOT_H)); pen.lineTo((x + DOT_W, y))
        pen.closePath()
        x += PITCH


def build(src, outdir):
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTFont
    os.makedirs(outdir, exist_ok=True)
    for opt in ("h1", "h2"):
        f = TTFont(src); gs = f.getGlyphSet(); cm = f.getBestCmap()
        for d in "0123456789":
            name = cm[ord(d)]
            rec = DecomposingRecordingPen(gs); gs[name].draw(rec)
            b = BoundsPen(gs); gs[name].draw(b); x0, y0, x1, y1 = b.bounds
            adv, lsb = f["hmtx"][name]
            pen = TTGlyphPen(gs); rec.replay(pen)
            mid = (x0 + x1) / 2
            if opt == "h1":
                if d in L_DIGITS:
                    stipple(pen, x0, mid - 10, UNDER_Y)
                else:
                    stipple(pen, mid + 10, x1, UNDER_Y)
            else:
                gx0, gx1 = adv - 10, adv + 50          # just past the digit's own box (the number spacing adds room)
                stipple(pen, max(x1 + 5, adv - 40), adv + 20, 20 if d in L_DIGITS else 620)
            g = pen.glyph(); g.recalcBounds(f["glyf"])
            f["glyf"][name] = g
            f["hmtx"][name] = (adv, g.xMin)
        f.save(os.path.join(outdir, opt + "t.ttf"))
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "smart_features.py"),
                        os.path.join(outdir, opt + "t.ttf"), os.path.join(outdir, opt + ".ttf")], check=True, capture_output=True)
    print("built", outdir)


def blobs(bw):
    """Columns of ink in the black-and-white line: one (x0, x1) per digit (spaces show as wider gaps)."""
    cols = (bw < 128).any(0)
    out, x = [], 0
    while x < len(cols):
        if cols[x]:
            a = x
            while x < len(cols) and cols[x]:
                x += 1
            out.append((a, x - 1))
        x += 1
    return out


def decode(grey, bw, opt):
    """Per digit blob: 'L', 'R' or None (mark not readable)."""
    ys = np.where((bw < 128).any(1))[0]
    if not len(ys):
        return []
    top, base = ys.min(), ys.max()
    h = base - top + 1
    d = 255 - grey.astype(np.float32)
    res = []
    bl = blobs(bw)
    for i, (a, b) in enumerate(bl):
        if opt in ("h1", "grey"):
            band = d[base + 1:base + 1 + max(4, h // 5)]
            mid = (a + b) // 2
            vl = band[:, a:mid].mean(1).max() if mid > a and band.size else 0     # strongest row, not the strip average
            vr = band[:, mid + 1:b + 1].mean(1).max() if b > mid and band.size else 0
        else:
            nxt = bl[i + 1][0] if i + 1 < len(bl) else b + max(4, h // 3)
            gap = d[:, b + 1:nxt]
            if gap.shape[1] == 0:
                res.append(None); continue
            lo, hi = gap[base - h // 4:base + 1], gap[top:top + h // 4]
            vl, vr = lo.mean() if lo.size else 0, hi.mean() if hi.size else 0
        if max(vl, vr) < 4 or abs(vl - vr) < 2:
            res.append(None)
        else:
            res.append("L" if vl > vr else "R")
    return res


def char_drops(font, text, size_pt, dpi):
    """How far (px) each non-space character reaches below the baseline, ignoring tails (g p q y j: deeper than
    150 units): MaxOCR's digits sit about 105 units low, so their marks must go under them, not on them."""
    import freetype
    from maxocr.render import _load
    ft, _ = _load(font)
    k = size_pt * dpi / 72.0 / ft.units_per_EM
    out = []
    for ch in text:
        if ch == " ":
            continue
        ft.load_char(ch, freetype.FT_LOAD_NO_SCALE)
        ymin = ft.glyph.outline.get_bbox().yMin
        out.append(None if ymin < -150 else 0 if ymin > 0 else -ymin * k)     # None: a tail (g j p q y , ;) crosses the mark row
    return out


def digit_spans(font, text, size_pt, dpi):
    """x range (px, as in maxocr.render's canvas) of each non-space character's ink, from HarfBuzz positions."""
    import freetype
    import uharfbuzz as hb
    from maxocr.render import PAD, _load
    ft, hbf = _load(font)
    upem = ft.units_per_EM
    k = size_pt * dpi / 72.0 / upem
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(hbf, buf, {"liga": False, "calt": os.environ.get("MAXOCR_CALT") == "1"})
    out, pen = [], 0
    for info, pos, ch in zip(buf.glyph_infos, buf.glyph_positions, text):
        ft.load_glyph(info.codepoint, freetype.FT_LOAD_NO_SCALE)
        bb = ft.glyph.outline.get_bbox()
        if ch != " ":
            out.append((ch, 6 + PAD + (pen + pos.x_offset + bb.xMin) * k, 6 + PAD + (pen + pos.x_offset + bb.xMax) * k))   # +6: degrade.clean pads
        pen += pos.x_advance
    return out


def grey_marked(g, spans, level=0.15):
    """g: clean grey line (0 ink). A 1-px grey hairline under the left (L) or right (R) half of each digit, 2 px below
    the digits' bottom."""
    g = np.pad(g, ((0, 6), (0, 0)), constant_values=255).astype(np.float32)
    base = np.where((g < 128).any(1))[0].max()
    v = 255 * (1 - level)
    for ch, a, b in spans:
        if not ch.isdigit():
            continue
        mid = (a + b) / 2
        x0, x1 = (int(round(a)), int(round(mid)) - 1) if ch in L_DIGITS else (int(round(mid)) + 1, int(round(b)))
        g[base + 2, x0:x1 + 1] = np.minimum(g[base + 2, x0:x1 + 1], v)
    return g


def cls(ch):
    return "L" if ch in L_DIGITS else ("R" if ch.isdigit() else None)


def test():
    import pandas as pd
    import readme_bench as rb
    import rung0
    from text_eval import char_err, read_tesseract_dict
    from maxocr.corpus import GENERAL_ALPHABET
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    from maxocr.fonts import matched_size
    W = os.path.expanduser("~/maxocr-work/dmarks/")
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**{**eng, "alphabet": GENERAL_ALPHABET + " "}), Parseq(**eng)
    lines = rb.texts(300)["numbers"]
    conds = ["clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "thermal", "dot-matrix lq", "phone photo"]
    fonts = {"none": rb.FONTS["MaxOCR"], "grey": rb.FONTS["MaxOCR"], "h1": W + "h1.ttf", "h2": W + "h2.ttf"}
    real_clean = rb.clean
    real_otsu = rb.otsu
    rows = []
    for opt, P in fonts.items():
        size = matched_size(P, 8.0)
        for cond in conds:
            greys = []
            for k, t in enumerate(lines):
                rb.otsu = lambda x: x
                if opt == "grey":
                    rb.clean = lambda font, text, sz, dpi, binarize=False, _t=t: grey_marked(
                        real_clean(font, text, sz, dpi, binarize=False).astype(np.float32), digit_spans(font, _t, sz, dpi))
                try:
                    greys.append(np.clip(rb.image(P, t, size, cond, k), 0, 255).astype(np.uint8))
                finally:
                    rb.otsu, rb.clean = real_otsu, real_clean
            bws = [real_otsu(g.astype(np.float32)) for g in greys]
            preds = {"paddle": [paddle.text(im) for im in bws], "easyocr": rb.in_batches(easy.texts, bws),
                     "parseq": rb.read_by_words(pq, bws), "tesseract": read_tesseract_dict(bws, fold=False)}
            row = {"option": opt, "condition": cond,
                   "error": round(float(np.mean([char_err(lines, p) for p in preds.values()])), 2),
                   "extra chars": int(sum(max(0, len(p.replace(" ", "")) - len(t.replace(" ", "")))
                                          for ps in preds.values() for t, p in zip(lines, ps)))}
            if opt != "none":
                marks = [decode(g, bw, opt) for g, bw in zip(greys, bws)]
                tot = ok = 0
                for t, m in zip(lines, marks):
                    digits = t.replace(" ", "")
                    if len(m) != len(digits):
                        continue
                    for ch, mk in zip(digits, m):
                        tot += 1; ok += mk == cls(ch)
                row["marks right %"] = round(100 * ok / max(1, tot), 1)
                row["lines usable %"] = round(100 * np.mean([len(m) == len(t.replace(" ", "")) for t, m in zip(lines, marks)]), 1)
                wrong = caught = 0
                for ps in preds.values():
                    for t, p, m in zip(lines, ps, marks):
                        tt, pp = t.replace(" ", ""), p.replace(" ", "")
                        if tt == pp:
                            continue
                        wrong += 1
                        if len(pp) == len(tt) and len(m) == len(tt):
                            if any(mk is not None and mk != cls(c) for c, mk in zip(pp, m)):
                                caught += 1
                row["misreads"] = wrong; row["caught"] = caught
            rows.append(row); print(json.dumps(row), flush=True)
            pd.DataFrame(rows).to_csv("out/report/digit_marks.csv", index=False)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3])
    else:
        test()


def baseline_row(font, text, size_pt, dpi):
    """Row of the baseline in degrade.clean's image (render's ink crop and the 6-px pad included)."""
    import os as _os
    import freetype  # noqa: F401
    from maxocr.render import CROP_MARGIN, PAD, _cap_px, _load, render
    ft, _ = _load(font)
    ft.set_char_size(int(round(size_pt * 64)), 0, dpi, dpi)
    k = size_pt * dpi / 72.0 / ft.units_per_EM
    base_canvas = PAD + int(np.ceil(ft.ascender * k))
    old = _os.environ.pop("MAXOCR_CROP", None)
    try:
        full = render(font, text, size_pt, dpi)
    finally:
        if old is not None:
            _os.environ["MAXOCR_CROP"] = old
    if old == "ink":
        rows = np.nonzero((255 - full.astype(np.float32)) / 255 > 0.05)[0]
        if len(rows):
            m = int(round(CROP_MARGIN * _cap_px(font, size_pt, dpi)))
            base_canvas -= max(rows[0] - m, 0)
    return base_canvas + 6
