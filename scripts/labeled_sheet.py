"""Comparison sheet with the numbers inside the image: each option gets a title line, its sample text and a
line of measured numbers (James decides from the picture; every option shows its accuracy).

    python scripts/labeled_sheet.py spec.json out.png
spec.json: {"texts": ["...", ...], "options": [{"title": "...", "font": "path", "numbers": "errors 9.8% | ..."}]}
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

from maxocr.render import render


def main():
    spec = json.load(open(sys.argv[1]))
    try:
        big, small = ImageFont.load_default(size=30), ImageFont.load_default(size=26)
    except TypeError:
        big = small = ImageFont.load_default()
    blocks = [(o["title"], [render(o["font"], t, 22, 200) for t in spec["texts"]], o.get("numbers", "not measured yet"))
              for o in spec["options"]]
    W = max(max(s.shape[1] for s in b[1]) for b in blocks) + 60
    H = sum(44 + sum(s.shape[0] + 6 for s in b[1]) + 60 for b in blocks)
    c = Image.new("L", (max(W, 900), H), 255)
    d = ImageDraw.Draw(c)
    y = 8
    for title, samples, numbers in blocks:
        d.text((16, y), title, fill=0, font=big)
        y += 44
        for s in samples:
            c.paste(Image.fromarray(s), (28, y))
            y += s.shape[0] + 6
        d.text((36, y + 4), numbers, fill=40, font=small)
        y += 60
    c.save(sys.argv[2])


if __name__ == "__main__":
    main()
