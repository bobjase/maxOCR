"""Size-fairness check for the amalgam result: every font at the same capital height
(Source Code Pro at 8 pt), validation bank, s=0.5, suite (a), rung-0 metrics."""
import json
import os
import sys
from pathlib import Path

import pandas as pd
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from font_survey import matched_size  # noqa: E402
from maxocr.build import cand_id  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402
from maxocr.fonts import BASELINES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
D = Path(os.path.expanduser("~/maxocr-work/amalgam"))


def main():
    ofl = {f["family"]: f["path"] for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]}
    fonts = {"serif amalgam top3": str(D / "serif_top3.ttf"), "sans amalgam top3": str(D / "sans_top3.ttf"),
             "Spectral (best single serif)": ofl["spectral"],
             "Source Code Pro": str(BASELINES["Source Code Pro"]), "IBM Plex Mono": str(BASELINES["IBM Plex Mono"])}
    con = rung0.db()
    e = con.execute("SELECT value FROM state WHERE key='elite'").fetchone()
    if e:
        fonts["Iosevka rung-0 elite"] = con.execute("SELECT font FROM cand WHERE id=?", (cand_id(json.loads(e[0])),)).fetchone()[0]
    sizes = {n: matched_size(TTFont(p)) for n, p in fonts.items()}
    print("matched sizes (pt):", {n: round(s, 2) for n, s in sizes.items()}, flush=True)
    insts = rung0.bank("val")
    jobs = [Job(n, p, rung0.SEVERITY, "a", c, size_pt=sizes[n]) for n, p in fonts.items() for c in chunk(insts, 50)]
    chars, _, classes = run(jobs, rung0.EVAL_WORKERS, paddle=rung0.PaddleRec(), progress=False)
    rows = []
    for n, g in chars.groupby("font"):
        m = rung0.metrics(g, classes)
        u = g[~g.cropped]
        z, o = u[(u.engine == "paddle") & (u.truth == "0")], u[(u.engine == "paddle") & (u.truth == "O")]
        rows.append({"font": n, "size_pt": round(sizes[n], 2), "paddle_within_obj_pct": round(100 * m["within_obj"], 2),
                     "tess_within_gate_pct": round(100 * m["tess_k"] / max(m["tess_n"], 1), 2),
                     "paddle_0O_pct": round(100 * ((z.pred == "O").sum() + (o.pred == "0").sum()) / max(len(z) + len(o), 1), 2),
                     "char_error_pct": round(100 * float((u.pred != u.truth).mean()), 2)})
    df = pd.DataFrame(rows).sort_values("paddle_within_obj_pct")
    df.to_csv(ROOT / "out" / "report" / "amalgam_fair.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
