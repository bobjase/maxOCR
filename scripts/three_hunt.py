"""Every OFL font's 3, fitted into MaxOCR's 3 (same box, same ink weight), then Tesseract on numbers."""
import glob, os, sys, subprocess, json
sys.path.insert(0, "scripts")
from fontTools.ttLib import TTFont
from shapely import affinity
from readme_bench import image, texts
from text_eval import char_err, read_tesseract_dict
from maxocr.fonts import matched_size
from glyph_edit import glyph_path, write
from inline_lines import to_shape, to_path
W = os.path.expanduser("~/maxocr-work/three/"); os.makedirs(W, exist_ok=True)
SRC = "out/fonts/MaxOCR-Text.ttf"
lines = texts(300)["numbers"]
base = TTFont(SRC); ours = to_shape(glyph_path(base, "3")); bx = ours.bounds; area = ours.area
def regular(d):
    fs = [p for p in glob.glob(d + "/**/*.[ot]tf", recursive=True) if "italic" not in p.lower()]
    pref = [p for p in fs if "regular" in os.path.basename(p).lower()]
    return (pref or sorted(fs, key=len) or [None])[0]
res = []
for d in sorted(glob.glob("vendor/ofl/*")):
    p = regular(d)
    if not p: continue
    try:
        donor = TTFont(p); s = to_shape(glyph_path(donor, "3"))
        b = s.bounds
        s = affinity.translate(s, -b[0], -b[1])
        s = affinity.scale(s, (bx[2] - bx[0]) / (b[2] - b[0]), (bx[3] - bx[1]) / (b[3] - b[1]), origin=(0, 0))
        s = affinity.translate(s, bx[0], bx[1])
        lo, hi = -40.0, 40.0                     # match ink weight by growing/shrinking the outline
        for _ in range(18):
            m = (lo + hi) / 2
            if s.buffer(m, quad_segs=8).area < area: lo = m
            else: hi = m
        s = s.buffer((lo + hi) / 2, quad_segs=16).simplify(0.5)
        f = TTFont(SRC); write(f, "3", to_path(s)); name = os.path.basename(d)
        f.save(W + name + "t.ttf")
        subprocess.run([sys.executable, "scripts/smart_features.py", W + name + "t.ttf", W + name + ".ttf"], check=True, capture_output=True)
        P = W + name + ".ttf"; size = matched_size(P, 8.0); row = {"font": name}
        for cond in ("ink bleed", "damaged", "low-res"):
            r = read_tesseract_dict([image(P, t, size, cond, k) for k, t in enumerate(lines)], fold=False)
            row[cond] = round(char_err(lines, r), 2)
        row["sum"] = round(row["ink bleed"] + row["damaged"] + row["low-res"], 2)
        res.append(row); print(json.dumps(row), flush=True)
    except Exception as e:
        print("skip", d, type(e).__name__, e, flush=True)
