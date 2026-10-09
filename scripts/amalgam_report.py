"""Report an amalgam optimization: recipe changes per glyph and a P0 vs elite specimen.

    python scripts/amalgam_report.py [--cluster 08BDEOQ]
Writes out/report/amalgam_opt_<cluster>.md and amalgam_opt_<cluster>.png.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from maxocr.build import WORK
from maxocr.render import render

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cluster", default="08BDEOQ")
    a = ap.parse_args()
    d = ROOT / "out" / "amalgam_opt" / a.cluster
    events = [json.loads(line) for line in (d / "log.jsonl").read_text().splitlines()]
    start = next(e for e in events if e["event"] == "start")
    gens = [e for e in events if e["event"] == "generation"]
    val = next((e for e in events if e["event"] == "validation"), None)
    elite = json.loads((d / "elite.json").read_text()) if (d / "elite.json").exists() else None

    lines = [f"# Amalgam optimization, cluster {a.cluster}", "",
             f"Generations: {len(gens)}; accepted: {sum(g['accepted'] for g in gens)} "
             f"(at {[g['gen'] for g in gens if g['accepted']]})",
             f"Optimization-bank objective: {start['objective']} -> "
             f"{max([start['objective']] + [g['best_objective'] for g in gens if g['accepted']])}", ""]
    if val:
        p, e = val["P0"], val["elite"]
        lines += ["## Validation bank (s=0.5, suite a, 5,000 lines)", "",
                  "| | objective | PaddleOCR within objective % | Tesseract within gate % |", "|---|---|---|---|",
                  f"| P0 (serif top-3 amalgam) | {p['objective']} | {100 * p['within_obj']:.2f} | {100 * p['tess_gate']:.2f} |",
                  f"| elite | {e['objective']} | {100 * e['within_obj']:.2f} | {100 * e['tess_gate']:.2f} |", ""]
    if elite:
        lines += ["## Elite recipe (optimized glyphs)", "",
                  "| Glyph | Ingredients (weight) | Width | Height | Baseline shift | Stroke |", "|---|---|---|---|---|---|"]
        for c, r in elite["recipe"].items():
            ing = ", ".join(f"{k} {v:.2f}" for k, v in sorted(r["ingredients"].items(), key=lambda x: -x[1]))
            lines.append(f"| {c} | {ing} | {r['width']} | {r['height']} | {r['shift']} | {r['bold']} |")
    (ROOT / "out" / "report" / f"amalgam_opt_{a.cluster}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    fdir = WORK / "amalgam_opt" / a.cluster
    rows = []
    text = "0O8BDEQ  B0O8D Q0E8  1I 5S 2Z"
    for label, path in (("P0: serif top-3 amalgam", fdir / "P0.ttf"), ("optimized elite", Path(elite["font"]) if elite else None)):
        if path is None:
            continue
        img = render(str(path), text, 9.0, 500)
        img = cv2.copyMakeBorder(img, 4, 28, 10, 10, cv2.BORDER_CONSTANT, value=255)
        cv2.putText(img, label, (8, img.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 70, 1, cv2.LINE_AA)
        rows.append(img)
        small = render(str(path), "B8O0 DQ0E 80B0", 8.0, 200)
        rows.append(cv2.copyMakeBorder(cv2.resize(small, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST),
                                       2, 8, 10, 10, cv2.BORDER_CONSTANT, value=255))
    W = max(r.shape[1] for r in rows)
    cv2.imwrite(str(ROOT / "out" / "report" / f"amalgam_opt_{a.cluster}.png"),
                np.vstack([cv2.copyMakeBorder(r, 0, 0, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=255) for r in rows]))


if __name__ == "__main__":
    main()
