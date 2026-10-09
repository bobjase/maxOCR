"""Summarize the rung-0 run: accepted changes, validation trajectory, comparison with baselines.

Validation numbers come from the same bank (5,000 lines, seed 202, s=0.5, suite a, uncropped) and
the same definitions as out/report/baseline_table.csv: PaddleOCR within-objective-cluster rate and
Tesseract within-gate-cluster rate.

    python scripts/rung0_report.py
Writes out/report/rung0_summary.md and out/report/rung0_specimen.png.
"""
import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from maxocr.build import cand_id
from maxocr.render import render

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "out" / "rung0" / "run.db"
REPORT = ROOT / "out" / "report"


def main():
    con = sqlite3.connect(DB)
    events = pd.read_sql("SELECT * FROM log ORDER BY ts", con)
    final = con.execute("SELECT value FROM state WHERE key='final'").fetchone()
    elite = json.loads(con.execute("SELECT value FROM state WHERE key='elite'").fetchone()[0]) if \
        con.execute("SELECT value FROM state WHERE key='elite'").fetchone() else {}
    final = json.loads(final[0]) if final else None

    lines = ["# Rung 0 summary", ""]
    acc = events[events.event == "accepted"]
    lines.append(f"Accepted changes: {len(acc)}")
    for r in acc.itertuples():
        d = json.loads(r.detail)
        lines.append(f"- sweep {r.sweep}, cluster {r.cluster}: objective {d['objective']}")
    lines.append("")
    lines.append(f"Final variant overrides: `{json.dumps(final['elite'] if final else elite)}`"
                 + (f", weight {final['weight']}" if final else ""))
    lines.append("")

    val = events[events.event == "validation"]
    rows = []
    for r in val.itertuples():
        d = json.loads(r.detail)
        rows.append({"step": f"{r.cluster} (sweep {r.sweep})", "id": d["id"], "objective": d["objective"],
                     "paddle_within_obj_pct": round(100 * d["within_obj"], 2),
                     "tess_within_gate_pct": round(100 * d["tess_gate"], 2)})
    v = pd.DataFrame(rows)
    base = pd.read_csv(REPORT / "baseline_table.csv")
    base = base[(base.suite == "a") & (base.stratum == "all_uncropped")]
    b = base.pivot_table(index="font", columns="engine", values="within_own_clusters_pct").round(2)
    lines += ["## Validation bank (s=0.5, suite a, uncropped)", "",
              "| Font | PaddleOCR within objective clusters % | Tesseract within gate clusters % |", "|---|---|---|"]
    for r in v.itertuples():
        lines.append(f"| MaxOCR rung 0: {r.step} `{r.id}` | {r.paddle_within_obj_pct} | {r.tess_within_gate_pct} |")
    for font, r in b.iterrows():
        lines.append(f"| {font} (baseline) | {r.paddle} | {r.tesseract} |")
    lines.append("")
    rej = events[events.event == "gate"]
    if len(rej):
        lines += ["## Gate decisions", ""]
        for r in rej.itertuples():
            d = json.loads(r.detail)
            lines.append(f"- sweep {r.sweep} {r.cluster}: {d.get('overrides')} p_improve={d.get('p_improve')} "
                         f"passed={d.get('passed')} tess_a={d.get('tess_a')} tess_b={d.get('tess_b')} "
                         f"clean_failures={len(d.get('clean_failures', []))}")
    (REPORT / "rung0_summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    # Specimen: parent vs final for the objective-cluster characters.
    font_of = dict(con.execute("SELECT id, font FROM cand").fetchall())
    final_id = final["id"] if final else cand_id(elite)
    text = "0O8BDEQ 6GL HMN 1I 2Z 5S 9A UW"
    rows_img = []
    for label, cid in (("parent (Iosevka default)", cand_id({})), ("MaxOCR rung 0", final_id)):
        img = render(font_of[cid], text, 8.0, 900)
        img = cv2.copyMakeBorder(img, 6, 30, 12, 12, cv2.BORDER_CONSTANT, value=255)
        cv2.putText(img, label, (8, img.shape[0] - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 70, 1, cv2.LINE_AA)
        rows_img.append(img)
    W = max(r.shape[1] for r in rows_img)
    sheet = np.vstack([cv2.copyMakeBorder(r, 0, 0, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=255) for r in rows_img])
    cv2.imwrite(str(REPORT / "rung0_specimen.png"), sheet)


if __name__ == "__main__":
    main()
