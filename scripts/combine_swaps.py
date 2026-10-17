"""Put several sweep swaps into the current font at once (each glyph and its width from the donor-fitted font that
glyph_hunt.py built), then the context features. For near misses that are each too small to keep alone.

    python scripts/combine_swaps.py DST_NAME s:carlito S:literata d:arvo ...   -> ~/maxocr-work/hunt_2b/DST_NAME.ttf
"""
import os
import subprocess
import sys

from fontTools.ttLib import TTFont

SRC = "out/fonts/MaxOCR-Text.ttf"


def main():
    name, swaps = sys.argv[1], [s.split(":") for s in sys.argv[2:]]
    W = os.path.expanduser("~/maxocr-work/hunt_2b/")
    os.makedirs(W, exist_ok=True)
    f = TTFont(SRC)
    cm = f.getBestCmap()
    for ch, donor in swaps:
        d = TTFont(os.path.expanduser(f"~/maxocr-work/hunt_{ord(ch):x}/{donor}t.ttf"))
        g = cm[ord(ch)]
        f["glyf"][g] = d["glyf"][d.getBestCmap()[ord(ch)]]
        f["hmtx"][g] = d["hmtx"][d.getBestCmap()[ord(ch)]]
    f.save(W + name + "t.ttf")
    subprocess.run([sys.executable, "scripts/smart_features.py", W + name + "t.ttf", W + name + ".ttf"], check=True)


if __name__ == "__main__":
    main()
