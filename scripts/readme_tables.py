"""Rebuild the README's benchmark chart (docs/benchmark.svg), tables (docs/table_*.svg: best value in each column on
a green background, second best light blue; values equal at one decimal, as shown, count as ties) and the numbers as CSV
(docs/benchmark_summary.csv, docs/benchmark_results.csv) from out/report/readme_bench.csv. SVG (James, 2026-10-13): sharp at any zoom, and each picture switches to dark colours
when the reader's system is in dark mode (its own background either way, so it stays readable if GitHub's theme and
the system's differ). Text uses the reader's fonts (GitHub's system font stack), numbers right-aligned."""
import re
from html import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

FONTS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
# light and dark values of every colour the pictures use
PALETTE = {"bg": ("#ffffff", "#0d1117"), "ink": ("#1f2328", "#e6edf3"), "muted": ("#59636e", "#9198a1"),
           "rule": ("#d1d9e0", "#3d444d"), "head-rule": ("#9198a1", "#59636e"), "best": ("#c6e8c6", "#1f4d2c"),
           "second": ("#d6e6f7", "#1c3350"), "maxrow": ("#fbf1ea", "#2a1f17"), "bar": ("#9a968e", "#6e7681"), "accent": ("#b5461f", "#f0883e"),
           "axis": ("#cfcac0", "#3d444d"), "grid": ("#ebe7df", "#21262d")}


def style_block() -> str:
    light = "".join(f"--{k}:{v[0]};" for k, v in PALETTE.items())
    dark = "".join(f"--{k}:{v[1]};" for k, v in PALETTE.items())
    return (f"<style>svg{{{light}}}@media (prefers-color-scheme: dark){{svg{{{dark}}}}}"
            f"text{{font-family:{FONTS};}}</style>")

CONDS = ["clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "damaged", "heavy"]
HEADS = ["Clean", "Blurry", "Noisy", "Low-res", "JPEG", "Ink bleed", "Smudged", "Damaged", "Heavy", "Average"]
d = pd.read_csv("out/report/readme_bench.csv")
avg = d.groupby(["font", "text"])["mean"].mean().unstack()[["paragraphs", "codes", "numbers"]]
avg["all"] = avg.mean(1)
avg = avg.sort_values("all")
avg.round(2).to_csv("docs/benchmark_summary.csv")

plt.rcParams["svg.fonttype"] = "none"          # text stays text (drawn in the reader's fonts)
fig, axes = plt.subplots(1, 3, figsize=(15, max(6.2, 0.36 * len(avg) + 1.2)))
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
         "300 lines per kind of text per condition.", fontsize=9, color="#6b675f")
fig.tight_layout(rect=(0, 0.04, 1, 0.94))
fig.savefig("docs/benchmark.svg", facecolor="white")
svg = open("docs/benchmark.svg", encoding="utf-8").read()
for hexcol, var in (("#ffffff", "bg"), ("#1d1c1a", "ink"), ("#9a968e", "bar"), ("#b5461f", "accent"),
                    ("#cfcac0", "axis"), ("#6b675f", "muted"), ("#ebe7df", "grid")):
    svg = re.sub(re.escape(hexcol), f"var(--{var})", svg, flags=re.I)
svg = re.sub(r"font-family:[^;\"]*", f"font-family:{FONTS}", svg)
svg = re.sub(r"(<svg[^>]*>)", lambda m: m.group(1) + style_block(), svg, count=1)
open("docs/benchmark.svg", "w", encoding="utf-8", newline="\n").write(svg)

def shown(v: float) -> str:
    """The number exactly as the table prints it. Comparisons use this string: numpy's round() rounds 0.05 down to
    0.0 while the table prints 0.1, which coloured equal-looking cells differently."""
    return f"{v:.1f}"


def same(v: float, ref: float) -> bool:
    """Printed as the same number: a tie (James, 2026-10-16: "if best is 0.1 and we're 0.1, then we're the best.
    Anything less than 1/10th of a % is noise")."""
    return shown(v) == shown(ref)


def ranks(col: list[float]) -> list[int]:
    """1 = best (lowest as printed, all ties), 2 = second best (the next value as printed, all ties), else 0."""
    levels = sorted({float(shown(v)) for v in col})
    return [1 if float(shown(v)) == levels[0] else 2 if len(levels) > 1 and float(shown(v)) == levels[1] else 0
            for v in col]


def table_svg(path: str, cols: list[str], rows: list[tuple[str, list[float]]], note: str):
    """A table: best (lowest) value in each column on a green background, second best light blue, the MaxOCR row
    tinted, numbers right-aligned."""
    rank = [ranks([r[1][j] for r in rows]) for j in range(len(cols))]
    m, fw, cw, rh, hh = 16, 170, 84, 30, 40
    W, H = max(m + fw + cw * len(cols) + m, 7 * len(note) + 2 * m), m + hh + rh * len(rows) + 44   # room for the note
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', style_block(),
           f'<rect width="{W}" height="{H}" rx="6" fill="var(--bg)"/>',
           f'<text x="{m + 8}" y="{m + 26}" font-size="14" font-weight="600" fill="var(--muted)">Font</text>']
    for j, c in enumerate(cols):
        x = m + fw + cw * (j + 1) - 10
        out.append(f'<text x="{x}" y="{m + 26}" font-size="14" font-weight="600" fill="var(--muted)" '
                   f'text-anchor="end">{escape(c)}</text>')
    y = m + hh
    out.append(f'<line x1="{m}" y1="{y - 1}" x2="{W - m}" y2="{y - 1}" stroke="var(--head-rule)" stroke-width="1.5"/>')
    for name, vals in rows:
        if name == "MaxOCR":
            out.append(f'<rect x="{m}" y="{y}" width="{W - 2 * m}" height="{rh}" fill="var(--maxrow)"/>')
        weight = ' font-weight="700"' if name == "MaxOCR" else ""
        out.append(f'<text x="{m + 8}" y="{y + 20}" font-size="15" fill="var(--ink)"{weight}>{escape(name)}</text>')
        for j, v in enumerate(vals):
            x = m + fw + cw * j
            r = rank[j][[n for n, _ in rows].index(name)]
            is_best = r == 1
            if r:
                fill = "var(--best)" if r == 1 else "var(--second)"
                out.append(f'<rect x="{x + 8}" y="{y + 3}" width="{cw - 10}" height="{rh - 6}" rx="3" fill="{fill}"/>')
            bold = ' font-weight="700"' if (is_best or name == "MaxOCR") else ""
            out.append(f'<text x="{x + cw - 10}" y="{y + 20}" font-size="15" fill="var(--ink)" text-anchor="end"'
                       f'{bold}>{v:.1f}</text>')
        y += rh
        out.append(f'<line x1="{m}" y1="{y - 0.5}" x2="{W - m}" y2="{y - 0.5}" stroke="var(--rule)" stroke-width="1"/>')
    out.append(f'<text x="{m}" y="{y + 28}" font-size="13" fill="var(--muted)">{escape(note)}</text>')
    out.append("</svg>")
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")


NOTE = "Character error %, lower is better. Green: best in the column; blue: second best. Equal values are ties."
table_svg("docs/table_summary.svg", ["Paragraphs", "Codes", "Numbers", "All three"],
          [(f, [r.paragraphs, r.codes, r.numbers, r["all"]]) for f, r in avg.iterrows()], NOTE)
notbest = []
for kind in ("paragraphs", "codes", "numbers"):
    p = d[d.text == kind].pivot(index="font", columns="condition", values="mean")[CONDS]
    p["avg"] = p.mean(1)
    p = p.sort_values("avg")
    table_svg(f"docs/table_{kind}.svg", HEADS[:-1] + ["Average"], [(f, list(r.values)) for f, r in p.iterrows()], NOTE)
    others = p.drop("MaxOCR")
    notbest += [(kind, c, others[c].idxmin(), round(others[c].min(), 2), round(p.loc["MaxOCR", c], 2))
                for c in CONDS if not same(p.loc["MaxOCR", c], others[c].min()) and others[c].min() < p.loc["MaxOCR", c]]
d.to_csv("docs/benchmark_results.csv", index=False)
print(avg.round(2).to_string())
print("not best:", notbest)
