"""Section 11 baseline fonts. Paths are produced by scripts/fetch_vendor.sh and scripts/iosevka.sh."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "fonts"

BASELINES = {
    "OCR-A": VENDOR / "OCRA.ttf",
    "OCR-B": VENDOR / "ocrb10.otf",
    "Iosevka": ROOT / "out" / "fonts" / "Iosevka-Regular.ttf",
    "JetBrains Mono": VENDOR / "JetBrainsMono-Regular.ttf",
    "IBM Plex Mono": VENDOR / "IBMPlexMono-Regular.ttf",
    "Source Code Pro": VENDOR / "SourceCodePro-Regular.ttf",
}

# Best Windows fonts in the 414-face survey (lowest character error, PaddleOCR + Tesseract, s=0.5,
# matched capital height). Proprietary: measurement only, read in place, never redistributed.
SURVEY_BEST = {
    "Bookman Old Style": "/mnt/c/Windows/Fonts/BOOKOS.TTF",
    "Sitka Text": "/mnt/c/Windows/Fonts/SitkaVF.ttf",
    "Courier New": "/mnt/c/Windows/Fonts/cour.ttf",
    "Georgia": "/mnt/c/Windows/Fonts/georgia.ttf",
    "Verdana": "/mnt/c/Windows/Fonts/verdana.ttf",
}

MAXOCR_CAP = 0.7   # capital height / em of every MaxOCR build (blend.CAP / blend.UPEM)


def matched_size(font: str, size_pt: float = 8.0) -> float:
    """Point size giving `font` the same capital height as a MaxOCR font at size_pt (fonts differ in
    cap height per em, so equal point sizes would favour fonts with taller capitals)."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTFont
    path, _, idx = str(font).partition("#")
    f = TTFont(path, fontNumber=int(idx or 0)) if path.lower().endswith(".ttc") else TTFont(path)
    gs, cm = f.getGlyphSet(), f.getBestCmap()
    p = BoundsPen(gs)
    gs[cm[ord("H")]].draw(p)
    cap = (p.bounds[3] - p.bounds[1]) / f["head"].unitsPerEm
    return round(size_pt * MAXOCR_CAP / cap, 3)
