"""Build and inspect Iosevka's built-in variants for the confusable characters (rung-0 shortlist).

Build k sets every listed character to its k-th variant at once (characters are independent), so
one pass of ~15 builds covers every option. One extra build switches to quasi-proportional spacing.
Writes out/report/iosevka_variants.png (specimen) and iosevka_variants.csv (geometry), fonts to
~/maxocr-work/variants/.

    python scripts/iosevka_variants.py
"""
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from fontTools.ttLib import TTFont

from maxocr.render import render

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "report"
FONTS = Path.home() / "maxocr-work" / "variants"
PLAN = (ROOT / "iosevka" / "private-build-plans.toml").read_text()
DPI = 1200

# Character -> (Iosevka variant key, options). Zero: the three bodies x the overlays that matter.
VARIANTS = {
    "0": ("zero", [f"{b}{o}" for b in ("", "oval-", "diamond-") for o in ("unslashed", "slashed", "dotted")]),
    "1": ("one", ["line", "no-base", "base", "no-base-long-top-serif", "base-long-top-serif",
                  "no-base-flat-top-serif", "base-flat-top-serif", "no-base-top-cut", "base-top-cut"]),
    "I": ("capital-i", ["serifless", "serifed", "short-serifed"]),
    "8": ("eight", ["crossing", "two-circles", "crossing-asymmetric"]),
    "B": ("capital-b", ["standard-serifless", "standard-bilateral-serifed", "standard-interrupted-serifless",
                        "more-asymmetric-serifless", "more-asymmetric-bilateral-serifed",
                        "more-asymmetric-interrupted-serifless"]),
    "5": ("five", ["upright-arched-serifless", "upright-flat-serifless", "upright-flat-hook-serifless",
                   "oblique-arched-serifless", "oblique-flat-serifless", "upright-flat-serifed"]),
    "S": ("capital-s", ["serifless", "unilateral-serifed", "bilateral-serifed"]),
    "J": ("capital-j", ["serifless", "serifed-both-sides", "descending-serifless", "descending-serifed-both-sides"]),
    "D": ("capital-d", ["standard-serifless", "more-rounded-serifless", "standard-bilateral-serifed"]),
    "Q": ("capital-q", ["curly-tailed", "straight", "crossing", "horizontal-tailed", "detached-tailed",
                        "vertical-crossing"]),
}


def plan_text(k: int | None, spacing: str = "fixed") -> str:
    text = PLAN.replace('spacing = "fixed"', f'spacing = "{spacing}"', 1)
    if k is None:
        return text
    lines = [f'{key} = "{opts[k]}"' for key, opts in VARIANTS.values() if k < len(opts)]
    return text + "\n[buildPlans.MaxOCRCand.variants.design]\n" + "\n".join(lines) + "\n"


def build(name: str, text: str) -> Path:
    FONTS.mkdir(parents=True, exist_ok=True)
    plan = FONTS / f"{name}.toml"
    plan.write_text(text)
    out = FONTS / f"{name}.ttf"
    if not out.exists():
        subprocess.run(["bash", str(ROOT / "scripts" / "iosevka.sh"), "build", str(plan), "MaxOCRCand", str(out)],
                       check=True, capture_output=True)
    return out


def widths(font: Path, chars: str) -> dict:
    f = TTFont(str(font))
    cmap, gs = f.getBestCmap(), f.getGlyphSet()
    from fontTools.pens.boundsPen import BoundsPen
    out = {}
    for c in chars:
        pen = BoundsPen(gs)
        gs[cmap[ord(c)]].draw(pen)
        x0, y0, x1, y1 = pen.bounds
        out[c] = {"advance": f["hmtx"][cmap[ord(c)]][0], "ink_w": x1 - x0, "ink_h": y1 - y0, "y_min": y0}
    return out


def main():
    n_builds = max(len(o) for _, o in VARIANTS.values())
    fonts = [build(f"v{k:02d}", plan_text(k)) for k in range(n_builds)]
    default = build("default", plan_text(None))
    quasi = build("quasi", plan_text(None, "quasi-proportional"))
    print(f"{n_builds + 2} builds done", flush=True)

    rows = []
    for ch, (key, opts) in VARIANTS.items():
        for k, name in enumerate(opts):
            w = widths(fonts[k], ch + "O")
            rows.append({"char": ch, "key": key, "variant": name, **{f"{ch}_{m}": v for m, v in w[ch].items()},
                         "O_ink_w": w["O"]["ink_w"]})
    geo = pd.DataFrame(rows)
    geo.to_csv(OUT / "iosevka_variants.csv", index=False)

    dw, qw = widths(default, "0O1I8B5S"), widths(quasi, "0O1I8B5SMW")
    print("\ndefault (fixed spacing): " + ", ".join(f"{c} adv {v['advance']} ink {v['ink_w']:.0f}" for c, v in dw.items()))
    print("quasi-proportional:      " + ", ".join(f"{c} adv {v['advance']} ink {v['ink_w']:.0f}" for c, v in qw.items()))
    z = geo[geo.char == "0"]
    print("\nzero variants, ink width relative to O:")
    for r in z.itertuples():
        print(f"  {r.variant:22} 0 ink {r._5:.0f}  O ink {r.O_ink_w:.0f}  O/0 = {r.O_ink_w / r._5:.2f}")

    # Specimen: one row per character, its variants left to right, labelled.
    tiles_rows = []
    for ch, (key, opts) in VARIANTS.items():
        tiles = []
        for k, name in enumerate(opts):
            img = render(str(fonts[k]), ch if ch != "0" else "0O", 8.0, DPI)
            img = cv2.copyMakeBorder(img, 4, 26, 8, 8, cv2.BORDER_CONSTANT, value=255)
            cv2.putText(img, name[:24], (4, img.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, 80, 1, cv2.LINE_AA)
            tiles.append(img)
        H = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=255) for t in tiles]
        head = np.full((H, 90), 255, np.uint8)
        cv2.putText(head, key, (4, H // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 0, 1, cv2.LINE_AA)
        tiles_rows.append(np.hstack([head] + tiles))
    W = max(r.shape[1] for r in tiles_rows)
    sheet = np.vstack([cv2.copyMakeBorder(r, 0, 6, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=255) for r in tiles_rows])
    cv2.imwrite(str(OUT / "iosevka_variants.png"), sheet)


if __name__ == "__main__":
    main()
