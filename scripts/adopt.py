"""Adoption rule for a pair-discovery run: choose which of the run's top designs (if any) replaces the
current font, from the checks written by scratch/check_run.sh (case-folded reading throughout).

A candidate passes if, against the control (the base font the run evolved in):
  - the pair's confusion in ordinary lines (mean of four engines) is lower;
  - overall character error (mean of four engines) is not higher by more than 0.05 points;
  - the held-out PARSeq's character error is not higher by more than 0.2 points;
  - neither glyph is read correctly less often (mean of four engines) by more than 2 points;
  - unrestricted PARSeq shows no extra-character pattern: in every glyph x context cell, wrong-length
    reads are at most the control's + 3 (of 30);
  - unrestricted PARSeq loses at most 5 (of 30) correct reads in any glyph x context cell (1/I run 2 #1:
    a lone slanted 1 fell from 25 to 13).
PARSeq is used here only as a veto on finished candidates, never to steer the search.
Among passing candidates, the lowest overall character error wins (then the lowest pair confusion).
If none passes, the current font stays.

    python scripts/adopt.py RUN PAIR
Prints the table and the decision; writes out/discover/<RUN>/adopt.json.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ENG = ["paddle", "tesseract", "easyocr", "parseq"]


def main():
    run, pair = sys.argv[1], sys.argv[2]
    a, b = pair[0], pair[1]
    val = pd.read_csv(ROOT / "out" / "report" / f"validation_{run}.csv").set_index("font")
    low = pd.read_csv(ROOT / "out" / "report" / f"lowercase_{run}.csv")
    fonts = json.loads((ROOT / "out" / "discover" / run / "fonts.json").read_text())
    ctrl = "control (base font)"
    m = pd.DataFrame({
        "pair": val[[f"{e}_pair_pct" for e in ENG]].mean(1),
        "char_err": val[[f"{e}_char_err_pct" for e in ENG]].mean(1),
        "parseq_err": val["parseq_char_err_pct"],
        f"acc_{a}": val[[f"{e}_acc_{a}_pct" for e in ENG]].mean(1),
        f"acc_{b}": val[[f"{e}_acc_{b}_pct" for e in ENG]].mean(1),
    })
    wl = low.pivot_table(index="font", columns=["glyph", "kind"], values="wrong_len")
    excess = (wl.sub(wl.loc[ctrl], axis=1)).max(axis=1)
    m["extra_chars"] = excess.reindex(m.index)
    ok_reads = low.pivot_table(index="font", columns=["glyph", "kind"], values="correct")
    m["lost_correct"] = (-(ok_reads.sub(ok_reads.loc[ctrl], axis=1))).max(axis=1).reindex(m.index)
    c = m.loc[ctrl]
    m["pass"] = ((m["pair"] < c["pair"]) & (m["char_err"] <= c["char_err"] + 0.05)
                 & (m["parseq_err"] <= c["parseq_err"] + 0.2)
                 & (m[f"acc_{a}"] >= c[f"acc_{a}"] - 2) & (m[f"acc_{b}"] >= c[f"acc_{b}"] - 2)
                 & (m["extra_chars"] <= 3) & (m["lost_correct"] <= 5))
    m.loc[ctrl, "pass"] = False
    with pd.option_context("display.width", 200):
        print(m.round(2).to_string())
    ok = m[m["pass"]].sort_values(["char_err", "pair"])
    choice = None if ok.empty else ok.index[0]
    decision = {"run": run, "pair": pair, "adopted": choice, "font": fonts.get(choice) if choice else None,
                "control": c.round(3).to_dict(), "chosen": m.loc[choice].drop("pass").astype(float).round(3).to_dict() if choice else None}
    (ROOT / "out" / "discover" / run / "adopt.json").write_text(json.dumps(decision, indent=1))
    print("\nADOPT:", choice or "none (current font stays)")


if __name__ == "__main__":
    main()
