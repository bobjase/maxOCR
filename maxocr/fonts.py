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
