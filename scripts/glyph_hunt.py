"""Try one character from every OFL font in vendor/ofl inside MaxOCR (James, 2026-10-15: "look for the best 3
amongst installed fonts"; it found the 3 from Noto Sans). Each donor glyph is fitted into MaxOCR's glyph box and
grown or shrunk to the same ink area, then the font is built with smart_features.py and read by the engines.

    python scripts/glyph_hunt.py --char e --kind paragraphs --conds "ink bleed,clean" [--engines all|tesseract]
Writes one JSON line per donor font; fonts go to ~/maxocr-work/hunt_<char>/.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np
from fontTools.ttLib import TTFont
from shapely import affinity

sys.path.insert(0, os.path.dirname(__file__))
from glyph_edit import glyph_path, write  # noqa: E402
from inline_lines import to_path, to_shape  # noqa: E402
from readme_bench import image, in_batches, read_by_words, texts  # noqa: E402
from text_eval import char_err, read_tesseract_dict  # noqa: E402

SRC = "out/fonts/MaxOCR-Text.ttf"


def regular(d):
    fs = [p for p in glob.glob(d + "/**/*.[ot]tf", recursive=True) if "italic" not in p.lower()]
    pref = [p for p in fs if "regular" in os.path.basename(p).lower()]
    return (pref or sorted(fs, key=len) or [None])[0]


def fitted(donor: TTFont, ch: str, box, area):
    s = to_shape(glyph_path(donor, ch))
    b = s.bounds
    s = affinity.translate(s, -b[0], -b[1])
    s = affinity.scale(s, (box[2] - box[0]) / (b[2] - b[0]), (box[3] - box[1]) / (b[3] - b[1]), origin=(0, 0))
    s = affinity.translate(s, box[0], box[1])
    lo, hi = -40.0, 40.0                     # same ink weight as ours
    for _ in range(18):
        m = (lo + hi) / 2
        if s.buffer(m, quad_segs=8).area < area:
            lo = m
        else:
            hi = m
    return s.buffer((lo + hi) / 2, quad_segs=16).simplify(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--kind", default="paragraphs", help="comma-separated kinds of text")
    ap.add_argument("--n", type=int, default=300, help="lines per kind")
    ap.add_argument("--conds", default="ink bleed,clean")
    ap.add_argument("--engines", default="all")
    ap.add_argument("--donors", help="comma-separated vendor/ofl folder names (default: all)")
    ap.add_argument("--build-only", action="store_true", help="only build the fonts (rebuild on the current MaxOCR)")
    a = ap.parse_args()
    from maxocr.fonts import matched_size
    if a.engines == "all" and not a.build_only:
        import rung0
        from maxocr.corpus import GENERAL_ALPHABET
        from maxocr.engines.easyocr_rec import EasyOCRRec
        from maxocr.engines.parseq import Parseq
        eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
        paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**{**eng, "alphabet": GENERAL_ALPHABET + " "}), Parseq(**eng)

    def read(imgs):
        if a.engines != "all":
            return {"tesseract": read_tesseract_dict(imgs, fold=False)}
        return {"paddle": [paddle.text(im) for im in imgs], "easyocr": in_batches(easy.texts, imgs),
                "parseq": read_by_words(pq, imgs), "tesseract": read_tesseract_dict(imgs, fold=False)}

    W = os.path.expanduser(f"~/maxocr-work/hunt_{ord(a.char):x}/")
    os.makedirs(W, exist_ok=True)
    sets = texts(a.n)
    kinds = a.kind.split(",")
    base = TTFont(SRC)
    ours = to_shape(glyph_path(base, a.char))
    dirs = sorted(glob.glob("vendor/ofl/*"))
    if a.donors:
        dirs = [d for d in dirs if os.path.basename(d) in a.donors.split(",")]
    for d in ["(ours)"] + dirs:
        name = os.path.basename(d)
        try:
            f = TTFont(SRC)
            if d != "(ours)":
                p = regular(d)
                if not p:
                    continue
                write(f, a.char, to_path(fitted(TTFont(p), a.char, ours.bounds, ours.area)))
            f.save(W + name + "t.ttf")
            subprocess.run([sys.executable, "scripts/smart_features.py", W + name + "t.ttf", W + name + ".ttf"],
                           check=True, capture_output=True)
            if a.build_only:
                print("built", name, flush=True)
                continue
            P = W + name + ".ttf"
            size = matched_size(P, 8.0)
            row = {"font": name}
            for kind in kinds:
                lines = sets[kind][:a.n]
                for cond in a.conds.split(","):
                    preds = read([image(P, t, size, cond, k) for k, t in enumerate(lines)])
                    key = cond if len(kinds) == 1 else f"{kind}/{cond}"
                    for e, ps in preds.items():
                        row[f"{key}/{e}"] = round(char_err(lines, ps), 2)
                    row[key] = round(float(np.mean([char_err(lines, ps) for ps in preds.values()])), 2)
            print(json.dumps(row), flush=True)
        except Exception as e:
            print("skip", name, type(e).__name__, e, flush=True)


if __name__ == "__main__":
    main()
