"""Every number the README's prose quotes, from out/report/readme_bench.csv (so the text matches the tables).
    python scripts/readme_numbers.py [results.csv]
"""
import pandas as pd

ENGINES = ["paddle", "easyocr", "parseq", "tesseract"]
CONDS = ["clean", "blurry", "noisy", "low-res", "jpeg", "ink bleed", "smudged", "damaged", "heavy"]
KINDS = ["paragraphs", "codes", "numbers"]

import sys
d = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "out/report/readme_bench.csv")
avg = d.groupby(["font", "text"])["mean"].mean().unstack()
avg["all"] = d.groupby("font")["mean"].mean()
avg = avg.sort_values("all")
print("Averages over the nine conditions:\n", avg.round(2).to_string(), "\n")
m = avg.loc["MaxOCR"]
others = avg.drop("MaxOCR")
nxt = others["all"].idxmin()
print(f"All text: {100 * (1 - m['all'] / others.loc[nxt, 'all']):.0f}% fewer errors than the next best font ({nxt}, "
      f"{others.loc[nxt, 'all']:.2f} vs {m['all']:.2f})")
for f in ("Arial", "Times New Roman"):
    print(f"  vs {f}: {m['all'] / avg.loc[f, 'all']:.2f} of its errors")
for k in KINDS:
    b = others[k].idxmin()
    print(f"{k}: MaxOCR {m[k]:.2f}, next best {b} {others.loc[b, k]:.2f}")

print("\nLead over the best other font per cell (% fewer errors; negative = that font is ahead):")
rows, behind, agree = [], [], 0
for k in KINDS:
    row = {"text": k}
    for c in CONDS:
        cell = d[(d.text == k) & (d.condition == c)].set_index("font")
        o = cell.drop("MaxOCR")
        best = o["mean"].idxmin()
        lead = 100 * (1 - cell.loc["MaxOCR", "mean"] / o.loc[best, "mean"])
        row[c] = round(lead)
        if lead < 0:
            behind.append((k, c, best, o.loc[best, "mean"], cell.loc["MaxOCR", "mean"]))
        if all(cell.loc["MaxOCR", e] <= o.loc[best, e] for e in ENGINES):
            agree += 1
        if c == "clean":
            everyday = cell.loc[["Arial", "Times New Roman", "Calibri"], "mean"].mean()
            row["clean_best"] = f"{best} {o.loc[best, 'mean']:.2f}"
            row["clean_vs_everyday"] = round(100 * (1 - cell.loc["MaxOCR", "mean"] / everyday))
    rows.append(row)
t = pd.DataFrame(rows).set_index("text")
print(t[CONDS].to_string())
print("\nClean: best other font and MaxOCR's lead over the Arial / Times New Roman / Calibri average:")
print(t[["clean_best", "clean_vs_everyday"]].to_string())
print("\nBehind:", [(k, c, b, round(v, 2), round(mx, 2)) for k, c, b, v, mx in behind])
print(f"Engine agreement: all four engines at least as good as the best other font in {agree} of 27 cells")
