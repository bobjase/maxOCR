"""Benchmark for the README (James, 2026-10-13): MaxOCR against the fonts people use most (Windows; Android, Linux
and the web: Roboto, Open Sans, Noto Sans, DejaVu Sans, Inter, Ubuntu Mono, Source Code Pro; Apple: Helvetica, Helvetica Neue) and the best fonts
we found, on three kinds of text and nine print conditions, read by four OCR engines.

Text (case-sensitive, scored by character error with spaces ignored; 300 lines per kind since v0.98, the first 100
being the lines used before):
  paragraphs  lines of the grocery story (maxocr/grocery_story.txt): words, prices, codes, all 32 ASCII marks
              (wrapped at 22 characters; beyond its 198 lines, wrapped again at 26)
  codes       random mixed-case letters and digits, 6-12 characters (like order numbers, serials, passwords)
  numbers     digits only, in groups separated by spaces (like UPCs, card and phone numbers)
Conditions (8 pt at 300 dpi since v0.98's re-run (200 before); pixel sizes below are at 200 dpi, scaled 1.5x, every font at the same capital height; one damage at a time, then combined):
  clean       crisp print
  blurry      out-of-focus scan or photo (Gaussian blur, sigma 1.2 px)
  noisy       speckled scan (Gaussian noise, std 25 grey levels, plus 1% salt-and-pepper)
  low-res     faxed or downsampled (half resolution, scaled back with nearest neighbour)
  jpeg        heavy compression (JPEG quality 15)
  ink bleed   ink spreads into the paper (strokes 1 px heavier on every side)
  smudged     a finger dragged through wet ink: the whole line smeared along the drag, unevenly
  damaged     several kinds at once, mild (the project's standard test, severity 0.5: blur, ink spread, tilt,
              perspective, uneven light, noise, JPEG, thresholding)
  heavy       the same combination, severe (severity 1.0)
Engines: PaddleOCR, EasyOCR, PARSeq, Tesseract (with its dictionaries). Every image is binarised (Otsu).

    python scripts/readme_bench.py [--n 300] [--out readme_bench.csv]
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from text_eval import char_err, read_tesseract_dict  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.degrade import clean, degrade, make_instance  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402
from maxocr.prose import story_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WIN = "/mnt/c/Windows/Fonts/"
USER_FONTS = "/mnt/c/Users/james.JAMESWORK2025/AppData/Local/Microsoft/Windows/Fonts/"
FONTS = {
    "MaxOCR": str(ROOT / "out" / "fonts" / "MaxOCR.ttf"),
    # the fonts people use most
    "Arial": WIN + "arial.ttf", "Times New Roman": WIN + "times.ttf", "Calibri": WIN + "calibri.ttf",
    "Segoe UI": WIN + "segoeui.ttf", "Verdana": WIN + "verdana.ttf", "Georgia": WIN + "georgia.ttf",
    "Consolas": WIN + "consola.ttf", "Courier New": WIN + "cour.ttf",
    # the best we found: survey leaders, the classic OCR font, the best open-licence face for punctuation
    "Bookman Old Style": WIN + "BOOKOS.TTF", "Sitka Text": WIN + "SitkaVF.ttf", "OCR-A Extended": WIN + "OCRAEXT.TTF",
    "Courier Prime": str(ROOT / "vendor" / "ofl" / "courierprime" / "CourierPrime-Regular.ttf"),
    # phones, Linux and the web (open licences; Apple's own fonts may only be used on Apple devices)
    "Roboto": str(ROOT / "vendor" / "ofl" / "roboto" / "Roboto[wdth,wght].ttf"),
    "Open Sans": str(ROOT / "vendor" / "ofl" / "opensans" / "OpenSans[wdth,wght].ttf"),
    "Noto Sans": str(ROOT / "vendor" / "ofl" / "notosans" / "NotoSans[wdth,wght].ttf"),
    "DejaVu Sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "Inter": str(ROOT / "vendor" / "ofl" / "inter" / "Inter[opsz,wght].ttf"),
    "Ubuntu Mono": USER_FONTS + "UbuntuMono[wght].ttf",                      # Ubuntu Font Licence; default weight 400
    # its variable font defaults to ExtraLight (200): the Regular (400) instance, made with fontTools' instancer
    "Source Code Pro": str(ROOT / "vendor" / "ofl" / "sourcecodepro" / "SourceCodePro-Regular-400.ttf"),
    # Apple: Helvetica and Helvetica Neue (James's licensed copies, installed for his Windows user); San Francisco and
    # New York are licensed only for mock-ups of apps for Apple devices, so they are not measured
    "Helvetica": USER_FONTS + "HelveticaLTStd-Roman.otf",
    "Helvetica Neue": USER_FONTS + "HelveticaNeueLTStd-Roman.otf",
}
DPI = 300               # the standard scan resolution (James); damage sizes below are defined at 200 dpi
PX = DPI / 200          # and scaled by this, so every condition is physically the same as before
CONDITIONS = ("clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "damaged", "heavy")


def texts(n: int) -> dict[str, list[str]]:
    rng = np.random.default_rng(2026)
    alnum = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    codes = ["".join(rng.choice(list(alnum), rng.integers(6, 13))) for _ in range(n)]
    numbers = []
    for _ in range(n):
        groups = [str(rng.integers(0, 10 ** k)).zfill(int(k)) for k in rng.integers(2, 6, rng.integers(2, 4))]
        numbers.append(" ".join(groups))
    story = story_lines(22)
    if n > len(story):          # more lines than the story has at 22: add it wrapped at 26 (new line breaks)
        story = story + story_lines(26)
    step = max(1, len(story) // n)
    return {"paragraphs": story[::step][:n], "codes": codes, "numbers": numbers}


def smear(g: np.ndarray, angle_deg: float, scale: float = 1.0, seed: int = 0) -> np.ndarray:
    """A finger dragged through wet ink along the whole line: the ink is smeared both ways along the drag (strokes
    blur into grey streaks about 11 px long at 200 dpi and slightly darken), heavier in some places than others.
    scale > 1 for larger renders."""
    rng = np.random.default_rng(seed)
    d = 255.0 - g
    h, w = d.shape
    n = int(round(11 * scale)) | 1
    k = np.zeros((n, n), np.float32)
    c, s = np.cos(np.radians(angle_deg)), np.sin(np.radians(angle_deg))
    for t in np.linspace(-(n // 2), n // 2, 4 * n):
        k[int(round(n // 2 - t * s)), int(round(n // 2 + t * c))] = 1.0
    smeared = cv2.filter2D(d, -1, k / k.sum())
    lo = rng.random((h // int(25 * scale) + 2, w // int(25 * scale) + 2)).astype(np.float32)   # varies letter to letter
    patchy = cv2.resize(lo, (w, h), interpolation=cv2.INTER_CUBIC)
    mask = np.clip(0.45 + 0.55 * patchy, 0, 1)    # the whole line, heavier in some places than others
    a = 0.65 * mask                        # part of the ink stays where it was
    out = (1 - a) * d + a * np.clip(1.3 * smeared, 0, 255)
    return 255.0 - out


def in_batches(read, imgs: list, n: int = 100) -> list:
    """Read images n at a time (one batch of 300 large images ran the GPU out of memory, 2026-10-13)."""
    out = []
    for i in range(0, len(imgs), n):
        out += list(read(imgs[i:i + n]))
    return out


def words(line: np.ndarray) -> list[np.ndarray]:
    """A line image cut into words (PARSeq reads one word at a time, as in a real OCR pipeline: it is trained on at
    most 25 characters and squeezes every image to 32x128). A cut is made only at a real word space: a gap clearly
    wider than the gaps between letters (at least twice the typical one and a fifth of the line's height). A code
    has none and stays whole; a period, comma or narrow letter is never cut off on its own (a piece narrower than
    a third of the line's height joins its neighbour)."""
    ink = line < 128
    cols = np.where(ink.any(0))[0]
    if len(cols) < 2:
        return [line]
    rows = np.where(ink.any(1))[0]
    h = rows[-1] - rows[0] + 1
    gaps = np.diff(cols) - 1
    letter = np.median(gaps[gaps > 0]) if (gaps > 0).any() else 0
    cut_at = max(2 * letter, 0.2 * h)
    pieces, start = [], cols[0]
    for a, b, g in zip(cols[:-1], cols[1:], gaps):
        if g > cut_at:
            pieces.append([start, a + 1]); start = b
    pieces.append([start, cols[-1] + 1])
    merged = []
    for p in pieces:
        if merged and (p[1] - p[0] < h / 3 or merged[-1][1] - merged[-1][0] < h / 3):
            merged[-1][1] = p[1]
        else:
            merged.append(p)
    return [np.pad(line[:, max(0, x0 - 4): x1 + 4], ((0, 0), (4, 4)), constant_values=255) for x0, x1 in merged]


def read_by_words(pq, imgs: list[np.ndarray]) -> list[str]:
    pieces = [words(im) for im in imgs]
    flat = in_batches(pq.read, [w for ws in pieces for w in ws])
    out, i = [], 0
    for ws in pieces:
        out.append(" ".join(flat[i:i + len(ws)])); i += len(ws)
    return out


def otsu(img: np.ndarray) -> np.ndarray:
    img = np.clip(np.round(img), 0, 255).astype(np.uint8)
    _, out = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


def image(font: str, text: str, size: float, cond: str, k: int) -> np.ndarray:
    if cond in ("damaged", "heavy"):
        inst = make_instance(k, text, 4242)
        return degrade(font, inst, 0.5 if cond == "damaged" else 1.0, size, dpi=DPI, px_scale=PX)
    g = clean(font, text, size, DPI, binarize=False).astype(np.float32)
    rng = np.random.default_rng([4242, k])
    if cond == "blurry":
        g = cv2.GaussianBlur(g, (0, 0), 1.2 * PX)
    elif cond == "noisy":
        g = g + rng.normal(0, 25, g.shape)
        m = rng.random(g.shape)
        g[m < 0.005] = 0
        g[m > 0.995] = 255
    elif cond == "low-res":
        h, w = g.shape
        f = int(round(2 * PX))                         # down to 100 dpi, as before
        small = cv2.resize(g, (max(1, w // f), max(1, h // f)), interpolation=cv2.INTER_AREA)
        g = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    elif cond == "jpeg":
        ok, enc = cv2.imencode(".jpg", np.clip(g, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 15])
        g = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE).astype(np.float32)
    elif cond == "ink bleed":
        from maxocr.degrade import _ink_spread
        g = _ink_spread(g, 1.0 * PX, False)            # ink 1 px (at 200 dpi) heavier on every side
    elif cond == "smudged":
        g = smear(g, float(rng.uniform(-30, 30)), scale=PX, seed=k)
    elif cond in EXTRA:
        g = EXTRA[cond](g, rng)
    return otsu(g)


# Real-world capture, added 2026-10-21 after an outside review ("thermal-printer receipts, dot-matrix ... photographed
# at an angle on a crumpled receipt are harsher than modeled"). Each takes the clean grey line (0 ink, 255 paper, 300 dpi).
def _thermal(g, rng):
    """Thermal receipt printer: 203-dpi head (each dot on or off), faded and uneven heat across the line, one or two
    dead heating elements (white streaks), grey paper."""
    h, w = g.shape
    f = DPI / 203
    small = cv2.resize(g, (max(1, int(w / f)), max(1, int(h / f))), interpolation=cv2.INTER_AREA)
    dots = (small < 128).astype(np.float32)
    for _ in range(int(rng.integers(1, 3))):                     # dead elements: whole columns of the head (rows of text)
        dots[int(rng.integers(0, dots.shape[0])), :] = 0
    heat = 0.35 + 0.5 * (0.5 + 0.5 * np.sin(np.linspace(0, rng.uniform(2, 6), dots.shape[1]) + rng.uniform(0, 6)))
    dots *= heat[None, :] * rng.uniform(0.45, 1.0, dots.shape)          # weak dots print too light to count
    big = cv2.resize(dots, (w, h), interpolation=cv2.INTER_NEAREST)
    big = cv2.GaussianBlur(big, (0, 0), 0.6)
    return 238 - 220 * big + rng.normal(0, 6, g.shape)


def _dot_matrix(g, rng, dpi_y=72, dpi_x=120):
    """Dot-matrix printer in graphics mode: each letter rebuilt from round dots on the head's grid, a worn ribbon (faint,
    uneven dots). Default 9-pin (1/72 inch down, 1/120 across); 24-pin printers (Epson LQ class), the ones a TrueType
    font actually reaches through a Windows driver, print 180 x 180 dpi (James, 2026-10-21: "9 pin typically uses
    built-in printer fonts")."""
    h, w = g.shape
    py, px = DPI / dpi_y, DPI / dpi_x
    out = np.full(g.shape, 255.0, np.float32)
    r = 0.47 * py
    wear = rng.uniform(0.55, 0.9)
    for yc in np.arange(py / 2, h, py):
        for xc in np.arange(px / 2, w, px):
            y0, x0 = int(yc), int(xc)
            if g[min(y0, h - 1), min(x0, w - 1)] < 128:
                cv2.circle(out, (int(round(xc)), int(round(yc))), int(round(r)), float(255 * (1 - wear * rng.uniform(0.7, 1.0))), -1, lineType=cv2.LINE_AA)
    return cv2.GaussianBlur(out, (0, 0), 0.7)


def _phone(g, rng):
    """Phone photo of a curled receipt, then what a phone OCR app does before reading (James, 2026-10-21: real apps
    such as Google Lens or Microsoft Lens find the page, flatten it and even out the light). Capture: strong perspective,
    a page curl, shadow and uneven light, defocus and hand shake, camera noise and JPEG. App: the page corners are found
    with a small error and the perspective undone, the curl flattened to within a third of its depth, and the light
    evened out by dividing by the blurred background."""
    g = np.pad(g, 40, constant_values=255)
    h, w = g.shape
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    j = lambda a: rng.uniform(-a, a)
    dst = src + np.float32([[j(0.02 * w), j(0.12 * h)], [j(0.02 * w), j(0.12 * h)], [j(0.02 * w), j(0.12 * h)], [j(0.02 * w), j(0.12 * h)]])
    g = cv2.warpPerspective(g, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=255)
    xx = np.arange(w, dtype=np.float32); amp = rng.uniform(2, 5) * PX; freq = rng.uniform(1, 2.5)
    curl = amp * np.sin(xx / w * np.pi * freq)
    mapy = (np.arange(h, dtype=np.float32)[:, None] + curl[None, :]).astype(np.float32)
    g = cv2.remap(g, np.tile(xx, (h, 1)), mapy, cv2.INTER_LINEAR, borderValue=255)
    light = 1 - rng.uniform(0.1, 0.3) * np.linspace(0, 1, w)[None, :] ** rng.uniform(0.5, 2)
    g = 255 - (255 - g) * rng.uniform(0.75, 1.0)
    g = g * light
    g = cv2.GaussianBlur(g, (0, 0), rng.uniform(0.6, 1.4) * PX)
    k = int(rng.integers(2, 5)); kern = np.zeros((k, k), np.float32); kern[k // 2, :] = 1 / k
    g = cv2.filter2D(g, -1, kern) + rng.normal(0, 7, g.shape)
    ok, enc = cv2.imencode(".jpg", np.clip(g, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 60])
    g = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE).astype(np.float32)
    # the app: flatten the curl (to within a third), undo the perspective from slightly misplaced corners, even the light
    mapy = (np.arange(h, dtype=np.float32)[:, None] - 0.67 * curl[None, :]).astype(np.float32)
    g = cv2.remap(g, np.tile(xx, (h, 1)), mapy, cv2.INTER_LINEAR, borderValue=255)
    found = dst + np.float32([[j(0.005 * w), j(0.03 * h)] for _ in range(4)])
    g = cv2.warpPerspective(g, cv2.getPerspectiveTransform(found, src), (w, h), borderValue=255)
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    return np.clip(g / np.maximum(bg, 1) * 255, 0, 255)


def _dot_matrix_lq(g, rng, passes=2):
    """24-pin dot-matrix in letter-quality graphics mode (Epson LQ class; Kimi review, 2026-10-21): dots addressed on a
    1/360-inch grid across and 1/180 inch down, round pin dots 0.2 mm across so neighbours overlap; a second pass with
    the paper moved half a row (1/360 inch) fills between rows (360 x 360, the printer's finest mode); the ribbon's ink
    varies slowly along the line and the whole line is lightened by wear."""
    h, w = g.shape
    px, py = DPI / 360, DPI / 180
    r = 0.5 * (0.2 / 25.4) * DPI                                  # pin 0.2 mm across
    ink = (g < 128)
    out = np.zeros(g.shape, np.float32)
    density = 0.55 + 0.35 * (0.5 + 0.5 * np.sin(np.linspace(0, rng.uniform(1, 3), w) * np.pi + rng.uniform(0, 6)))
    density *= rng.uniform(0.75, 1.0)                              # ribbon wear, whole line
    for p in range(passes):
        for yc in np.arange(py / 2 + p * py / 2, h, py):
            for xc in np.arange(px / 2, w, px):
                yi, xi = min(int(yc), h - 1), min(int(xc), w - 1)
                if ink[yi, xi]:
                    cv2.circle(out, (int(round(xc * 4)), int(round(yc * 4))), int(round(r * 4)),
                               float(density[xi] * rng.uniform(0.8, 1.0)), -1, lineType=cv2.LINE_AA, shift=2)
    return 255 - 255 * np.clip(cv2.GaussianBlur(out, (0, 0), 0.5), 0, 1)


EXTRA = {"thermal": _thermal, "dot-matrix": _dot_matrix, "phone photo": _phone,
         "dot-matrix lq": _dot_matrix_lq,
         "dot-matrix 24": lambda g, rng: _dot_matrix(g, rng, 180, 180)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="lines per kind of text")
    ap.add_argument("--out", default="readme_bench.csv")
    ap.add_argument("--fonts", help="comma-separated subset of the font names")
    ap.add_argument("--conds", help="comma-separated conditions (default: the nine README conditions; also thermal, dot-matrix, phone photo)")
    a = ap.parse_args()
    fonts = {k: v for k, v in FONTS.items() if not a.fonts or k in a.fonts.split(",")}
    sets = texts(a.n)
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    # EasyOCR may output a space (without it, gaps came out as invented dots)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**{**eng, "alphabet": GENERAL_ALPHABET + " "}), Parseq(**eng)
    out = ROOT / "out" / "report" / a.out
    rows = pd.read_csv(out).to_dict("records") if out.exists() else []
    done = {(r["font"], r["text"], r["condition"]) for r in rows}
    for name, path in fonts.items():
        size = matched_size(path, 8.0)
        for cond in (a.conds.split(",") if a.conds else CONDITIONS):
            for kind, lines in sets.items():
                if (name, kind, cond) in done:
                    continue
                imgs = [image(path, t, size, cond, k) for k, t in enumerate(lines)]
                preds = {"paddle": [paddle.text(im) for im in imgs], "easyocr": in_batches(easy.texts, imgs),
                         "parseq": read_by_words(pq, imgs), "tesseract": read_tesseract_dict(imgs, fold=False)}
                row = {"font": name, "text": kind, "condition": cond}
                for e, p in preds.items():
                    row[e] = round(char_err(lines, p), 2)
                row["mean"] = round(float(np.mean([row[e] for e in preds])), 2)
                rows.append(row)
                print(json.dumps(row), flush=True)
                pd.DataFrame(rows).to_csv(out, index=False)     # resumable
    print("README BENCH DONE", flush=True)


if __name__ == "__main__":
    main()
