"""Picture for the README: each print condition applied to its own name (James, 2026-10-13).

Drawn at 4x the test resolution (1200 dpi instead of 300) so clean print looks like print, with each damage scaled to
match, so it looks the way it does relative to the letters in the test: blur 4x wider, noise grains and low-res blocks
4x larger, ink spread 4x thicker. JPEG and the combined damage are made at the test resolution and enlarged smoothly.
Shown in grey, before the black-and-white step the engines also get.

    python scripts/damage_examples.py        (from the repo root; writes scratch/damage/*.png)
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maxocr.degrade import degrade, make_instance  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402
from maxocr.render import render  # noqa: E402
from readme_bench import EXTRA, smear  # noqa: E402

K = 4                       # display scale vs the test's 200 dpi
FONT = "out/fonts/MaxOCR.ttf"
WORDS = {"clean": "Clean", "blurry": "Blurry", "noisy": "Noisy", "low-res": "Low-res", "jpeg": "JPEG",
         "ink bleed": "Ink bleed", "smudged": "Smudged", "damaged": "Damaged", "heavy": "Heavy",
         "thermal": "Thermal", "dot-matrix": "Dot-matrix", "phone photo": "Phone photo"}


def show(cond: str, text: str, size: float, K: int = K) -> np.ndarray:
    """The condition at K times the test resolution (K=1: the actual 300 dpi scan, as the engines receive it before
    the black-and-white step)."""
    def up(img, interp=cv2.INTER_CUBIC):
        return img if K == 1 else cv2.resize(img, (img.shape[1] * K, img.shape[0] * K), interpolation=interp)

    rng = np.random.default_rng(7)
    if cond in EXTRA:                                   # made at the test resolution, then enlarged smoothly
        g = np.pad(render(FONT, text, size, 300), 6, constant_values=255).astype(np.float32)
        g = EXTRA["dot-matrix lq" if cond == "dot-matrix" else cond](g, rng)   # the README's dot-matrix is 24-pin letter quality
        return np.clip(up(g), 0, 255).astype(np.uint8)
    if cond in ("damaged", "heavy", "jpeg"):
        if cond == "jpeg":
            g = np.pad(render(FONT, text, size, 300), 6, constant_values=255)
            ok, enc = cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, 15])
            g = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
        else:
            g = degrade(FONT, make_instance(7, text, 4242), 0.5 if cond == "damaged" else 1.0, size, dpi=300, binarize=False, px_scale=1.5)
        return np.clip(up(g.astype(np.float32)), 0, 255).astype(np.uint8)
    g = np.pad(render(FONT, text, size, 300 * K), 6 * K, constant_values=255).astype(np.float32)
    if cond == "blurry":
        g = cv2.GaussianBlur(g, (0, 0), 1.8 * K)
    elif cond == "noisy":
        h, w = g.shape
        small = (h // K + 1, w // K + 1)
        noise = up(rng.normal(0, 25, small).astype(np.float32), cv2.INTER_NEAREST)[:h, :w]
        m = up(rng.random(small).astype(np.float32), cv2.INTER_NEAREST)[:h, :w]
        g = g + noise
        g[m < 0.005] = 0
        g[m > 0.995] = 255
    elif cond == "low-res":
        h, w = g.shape
        small = cv2.resize(g, (max(1, w // (3 * K)), max(1, h // (3 * K))), interpolation=cv2.INTER_AREA)
        g = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    elif cond == "smudged":
        g = smear(g, 12.0, scale=1.5 * K, seed=5)
    elif cond == "ink bleed":
        r = round(1.5 * K)
        disk = np.ones((3, 3), np.uint8) if K == 1 else cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        g = cv2.erode(g, disk)          # ink is dark: eroding the paper spreads the ink
    return np.clip(np.round(g), 0, 255).astype(np.uint8)


def main():
    size = matched_size(FONT, 8.0)
    out = Path("scratch/damage")
    out.mkdir(parents=True, exist_ok=True)
    for cond, word in WORDS.items():
        for k, tag in ((K, "big"), (1, "actual")):
            img = show(cond, word + " 0O1l $4.89", size, k)
            cv2.imwrite(str(out / f"{cond.replace(' ', '_')}_{tag}.png"), img)
        print(cond, img.shape)


if __name__ == "__main__":
    main()
