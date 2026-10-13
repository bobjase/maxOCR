"""Each README print condition applied to its own name, exactly as the benchmark renders it (8 pt, 200 dpi)."""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, "scripts")  # run from the repo root; writes scratch/damage/*.png
from readme_bench import CONDITIONS, image  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402

font = "out/fonts/MaxOCR.ttf"
size = matched_size(font, 8.0)
out = Path("scratch/damage")
out.mkdir(exist_ok=True)
words = {"clean": "Clean", "blurry": "Blurry", "noisy": "Noisy", "low-res": "Low-res", "jpeg": "JPEG",
         "smudged": "Smudged", "damaged": "Damaged", "heavy": "Heavy"}
for k, cond in enumerate(CONDITIONS):
    img = image(font, words[cond] + " 0O1l $4.89", size, cond, 7)
    cv2.imwrite(str(out / f"{cond}.png"), img)
    print(cond, img.shape)
