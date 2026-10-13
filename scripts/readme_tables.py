"""Rebuild the README's benchmark chart (docs/benchmark.png), table pictures (docs/table_*.png: best value in each
column on a green background, readable in light and dark mode) and the numbers as CSV (docs/benchmark_summary.csv,
docs/benchmark_results.csv) from out/report/readme_bench.csv."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

CONDS = ["clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "damaged", "heavy"]
HEADS = ["Clean", "Blurry", "Noisy", "Low-res", "JPEG", "Ink bleed", "Smudged", "Damaged", "Heavy", "Average"]
d = pd.read_csv("out/report/readme_bench.csv")
avg = d.groupby(["font", "text"])["mean"].mean().unstack()[["paragraphs", "codes", "numbers"]]
avg["all"] = avg.mean(1)
avg = avg.sort_values("all")
avg.round(2).to_csv("docs/benchmark_summary.csv")

fig, axes = plt.subplots(1, 3, figsize=(15, 6.2))
ink, muted, accent = "#1d1c1a", "#9a968e", "#b5461f"
for ax, kind, title in zip(axes, ["paragraphs", "codes", "numbers"], ["Paragraphs", "Codes", "Numbers"]):
    s = avg[kind].sort_values(ascending=False)
    ax.barh(range(len(s)), s.values, color=[accent if f == "MaxOCR" else muted for f in s.index], height=0.62)
    ax.set_yticks(range(len(s)), s.index, fontsize=10.5, color=ink)
    for i, (f, v) in enumerate(s.items()):
        ax.text(v + 0.25, i, f"{v:.1f}", va="center", fontsize=9.5, color=ink, fontweight="bold" if f == "MaxOCR" else "normal")
    ax.set_title(title, fontsize=13, color=ink, loc="left", pad=8)
    ax.set_xlim(0, s.max() * 1.18)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#cfcac0")
    ax.tick_params(axis="x", colors="#6b675f", labelsize=9)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#ebe7df", linewidth=0.8); ax.set_axisbelow(True)
fig.suptitle(f"Character error %, averaged over {len(CONDS)} print conditions (lower is better)", x=0.01, ha="left",
             fontsize=14, color=ink)
fig.text(0.01, 0.01, "Four OCR engines (PaddleOCR, EasyOCR, PARSeq, Tesseract); 8 pt at 200 dpi, equal capital height; "
         "100 lines per kind of text per condition.", fontsize=9, color="#6b675f")
fig.tight_layout(rect=(0, 0.04, 1, 0.94))
fig.savefig("docs/benchmark.png", dpi=110, facecolor="white")

from PIL import Image, ImageDraw, ImageFont

BOLD = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 21)
REG = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 21)
HEAD = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 19)
BEST_BG, MAX_BG, RULE, INK, MUTED = (198, 232, 198), (250, 241, 235), (226, 222, 214), (29, 28, 26), (95, 91, 84)


def table_png(path: str, cols: list[str], rows: list[tuple[str, list[float]]], note: str):
    """A table picture: best (lowest) value in each column on a green background, the MaxOCR row tinted."""
    best = [min(r[1][j] for r in rows) for j in range(len(cols))]
    fw, cw, rh = 230, 104, 40
    W, H = 30 + fw + cw * len(cols) + 30, 30 + 54 + rh * len(rows) + 50
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    y = 30
    d.text((30, y + 14), "Font", font=HEAD, fill=MUTED)
    for j, c in enumerate(cols):
        x = 30 + fw + cw * j
        d.text((x + cw - 12 - d.textlength(c, font=HEAD), y + 14), c, font=HEAD, fill=MUTED)
    y += 54
    d.line([(30, y - 2), (W - 30, y - 2)], fill=(180, 175, 166), width=2)
    for name, vals in rows:
        if name == "MaxOCR":
            d.rectangle((30, y, W - 30, y + rh - 1), fill=MAX_BG)
        d.text((40, y + 7), name, font=BOLD if name == "MaxOCR" else REG, fill=INK)
        for j, v in enumerate(vals):
            x = 30 + fw + cw * j
            is_best = abs(v - best[j]) < 1e-9
            if is_best:
                d.rectangle((x + 8, y + 3, x + cw - 4, y + rh - 4), fill=BEST_BG)
            t = f"{v:.1f}"
            d.text((x + cw - 12 - d.textlength(t, font=BOLD), y + 7), t, font=BOLD if (is_best or name == "MaxOCR") else REG, fill=INK)
        y += rh
        d.line([(30, y - 1), (W - 30, y - 1)], fill=RULE, width=1)
    d.text((30, y + 14), note, font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18), fill=MUTED)
    img.save(path)


NOTE = "Character error %, lower is better. Green: best in the column."
table_png("docs/table_summary.png", ["Paragraphs", "Codes", "Numbers", "All three"],
          [(f, [r.paragraphs, r.codes, r.numbers, r["all"]]) for f, r in avg.iterrows()], NOTE)
notbest = []
for kind in ("paragraphs", "codes", "numbers"):
    p = d[d.text == kind].pivot(index="font", columns="condition", values="mean")[CONDS]
    p["avg"] = p.mean(1)
    p = p.sort_values("avg")
    table_png(f"docs/table_{kind}.png", HEADS[:-1] + ["Average"], [(f, list(r.values)) for f, r in p.iterrows()], NOTE)
    others = p.drop("MaxOCR")
    notbest += [(kind, c, others[c].idxmin(), round(others[c].min(), 2), round(p.loc["MaxOCR", c], 2))
                for c in CONDS if others[c].min() < p.loc["MaxOCR", c]]
d.to_csv("docs/benchmark_results.csv", index=False)
print(avg.round(2).to_string())
print("not best:", notbest)
