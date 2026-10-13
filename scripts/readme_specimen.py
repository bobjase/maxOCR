"""docs/specimen.png for the README: the full character set of out/fonts/MaxOCR.ttf.
    python scripts/readme_specimen.py        (Windows Python: uses Segoe UI for the labels)
"""
from PIL import Image, ImageDraw, ImageFont

F = "out/fonts/MaxOCR.ttf"
L = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 22)
rows = [("Capitals", "ABCDEFGHIJKLM", 84), ("", "NOPQRSTUVWXYZ", 84),
        ("Lowercase", "abcdefghijklm", 84), ("", "nopqrstuvwxyz", 84),
        ("Digits", "0123456789", 84),
        ("Punctuation", "! \" # $ % & ' ( ) * + , - . / :", 66), ("", "; < = > ? @ [ \ ] ^ _ ` { | } ~", 66),
        ("Look-alikes kept apart", "0 O o   1 I l i   5 S s   2 Z z", 62), ("", "8 B   6 G   rn m   vv w   cl d", 62),
        ("In use", "Greenleaf Market #0217   TOTAL $64.89   VISA ****1157", 44),
        ("", "SKU 0O1-IL5-8B2Z   UPC 0 48500 28843 6   Order 40318", 44),
        ("", "The quick brown fox jumps over the lazy dog.", 44)]


def main():
    H = 40 + sum(int(s * 1.3) + (30 if lab else 0) for lab, _, s in rows) + 20
    img = Image.new("RGB", (1500, H), "white")
    d = ImageDraw.Draw(img)
    y = 30
    for lab, t, s in rows:
        if lab:
            d.text((40, y), lab.upper(), font=L, fill=(181, 70, 31))
            y += 30
        d.text((40, y), t, font=ImageFont.truetype(F, s), fill="black")
        y += int(s * 1.3)
    img.save("docs/specimen.png")
    print("docs/specimen.png", img.size)


if __name__ == "__main__":
    main()
