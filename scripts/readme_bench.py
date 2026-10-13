"""Benchmark for the README (James, 2026-10-13): MaxOCR against the fonts people use most (Windows; Android, Linux
and the web: Roboto, Open Sans, Noto Sans, DejaVu Sans, Inter, Ubuntu Mono, Source Code Pro; Apple: Helvetica, Helvetica Neue) and the best fonts
we found, on three kinds of text and nine print conditions, read by four OCR engines.

Text (case-sensitive, scored by character error with spaces ignored; 300 lines per kind since v0.98, the first 100
being the lines used before):
  paragraphs  lines of the grocery story (maxocr/grocery_story.txt): words, prices, codes, all 32 ASCII marks
              (wrapped at 22 characters; beyond its 198 lines, wrapped again at 26)
  codes       random mixed-case letters and digits, 6-12 characters (like order numbers, serials, passwords)
  numbers     digits only, in groups separated by spaces (like UPCs, card and phone numbers)
Conditions (8 pt at 200 dpi, every font at the same capital height; one damage at a time, then combined):
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


def otsu(img: np.ndarray) -> np.ndarray:
    img = np.clip(np.round(img), 0, 255).astype(np.uint8)
    _, out = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


def image(font: str, text: str, size: float, cond: str, k: int) -> np.ndarray:
    if cond in ("damaged", "heavy"):
        inst = make_instance(k, text, 4242)
        return degrade(font, inst, 0.5 if cond == "damaged" else 1.0, size)
    g = clean(font, text, size, 200, binarize=False).astype(np.float32)
    rng = np.random.default_rng([4242, k])
    if cond == "blurry":
        g = cv2.GaussianBlur(g, (0, 0), 1.2)
    elif cond == "noisy":
        g = g + rng.normal(0, 25, g.shape)
        m = rng.random(g.shape)
        g[m < 0.005] = 0
        g[m > 0.995] = 255
    elif cond == "low-res":
        h, w = g.shape
        small = cv2.resize(g, (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA)
        g = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    elif cond == "jpeg":
        ok, enc = cv2.imencode(".jpg", np.clip(g, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 15])
        g = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE).astype(np.float32)
    elif cond == "ink bleed":
        g = cv2.erode(g, np.ones((3, 3), np.uint8))      # ink is dark: eroding the paper spreads the ink
    elif cond == "smudged":
        g = smear(g, float(rng.uniform(-30, 30)), seed=k)
    return otsu(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="lines per kind of text")
    ap.add_argument("--out", default="readme_bench.csv")
    ap.add_argument("--fonts", help="comma-separated subset of the font names")
    a = ap.parse_args()
    fonts = {k: v for k, v in FONTS.items() if not a.fonts or k in a.fonts.split(",")}
    sets = texts(a.n)
    from maxocr.engines.easyocr_rec import EasyOCRRec
    from maxocr.engines.parseq import Parseq
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=False)
    paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    out = ROOT / "out" / "report" / a.out
    rows = pd.read_csv(out).to_dict("records") if out.exists() else []
    done = {(r["font"], r["text"], r["condition"]) for r in rows}
    for name, path in fonts.items():
        size = matched_size(path, 8.0)
        for cond in CONDITIONS:
            for kind, lines in sets.items():
                if (name, kind, cond) in done:
                    continue
                imgs = [image(path, t, size, cond, k) for k, t in enumerate(lines)]
                preds = {"paddle": [paddle.text(im) for im in imgs], "easyocr": in_batches(easy.texts, imgs),
                         "parseq": in_batches(pq.read, imgs), "tesseract": read_tesseract_dict(imgs, fold=False)}
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
