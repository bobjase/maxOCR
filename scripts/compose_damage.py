"""Compose docs/damage.png from scratch/damage/*_actual.png and *_big.png (scripts/damage_examples.py)."""
from PIL import Image, ImageDraw, ImageFont
conds = [("clean", "Clean", "crisp print"), ("blurry", "Blurry", "out-of-focus scan or photo"),
         ("noisy", "Noisy", "speckled, grainy scan"), ("low-res", "Low-res", "fax, or shrunk and blown back up"),
         ("jpeg", "JPEG", "heavy compression"), ("ink_bleed", "Ink bleed", "ink spreads into the paper, strokes heavier"),
         ("smudged", "Smudged", "a finger dragged through wet ink"), ("damaged", "Damaged", "blur, ink spread, tilt, noise, uneven light and JPEG together, mild"),
         ("heavy", "Heavy", "blur, ink spread, tilt, noise, uneven light and JPEG together, severe"),
         ("thermal", "Thermal", "receipt printer: coarse dots, faded and uneven heat"),
         ("dot-matrix", "Dot-matrix", "24-pin, letter quality: overlapping pin dots, uneven ribbon"),
         ("phone_photo", "Phone photo", "curled receipt: angle, curl, shadow, blur")]
S = 0.75
B = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
R = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
H2 = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 20)
rows = []
for c, n, d in conds:
    a = Image.open(f"scratch/damage/{c}_actual.png").convert("L")
    b = Image.open(f"scratch/damage/{c}_big.png").convert("L")
    b = b.resize((int(b.width * S), int(b.height * S)), Image.LANCZOS)
    rows.append((n, d, a, b))
aw = max(r[2].width for r in rows); bw = max(r[3].width for r in rows)
heights = [r[3].height + 52 for r in rows]           # each row only as tall as its own picture
W = 40 + aw + 60 + bw + 40
H = 70 + sum(heights) + 10
img = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(img)
xa, xb = 40, 40 + aw + 60
dr.text((xa, 20), "ACTUAL SIZE (8 pt, 300 dpi scan)", font=H2, fill=(110, 110, 110))
dr.text((xb, 20), "ENLARGED 3x", font=H2, fill=(110, 110, 110))
for k, (name, desc, a, b) in enumerate(rows):
    y = 62 + sum(heights[:k])
    dr.text((xa, y), name, font=B, fill=(181, 70, 31))
    dr.text((xa + dr.textlength(name, font=B) + 12, y + 4), desc, font=R, fill=(90, 90, 90))
    img.paste(a.convert("RGB"), (xa, y + 40 + (b.height - a.height) // 2))
    img.paste(b.convert("RGB"), (xb, y + 40))
    dr.rectangle((xb - 1, y + 39, xb + b.width, y + 40 + b.height), outline=(225, 222, 215))
img.save("docs/damage.png"); print(img.size)
