"""R32a blast-radius map: which glyphs does each candidate rung-2 parameter change?

Each parameter is built at a low and a high value with everything else at default, and every
primary-alphabet glyph (outline and advance) is diffed against the default build. A parameter
that changes glyphs in more than one objective cluster couples those clusters, which must then
be optimized as one block (R33).

Parameters: Iosevka metricOverride values that reach digits or capitals, the weight axis, and the
MaxOCR fork parameters (iosevka/maxocr-params.patch, built in ~/maxocr-work/iosevka-fork).

    python scripts/blast_radius.py
Writes out/report/blast_radius.csv and blast_radius.md.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from maxocr.build import WORK, BuildPool, plan_text
from maxocr.corpus import PRIMARY_ALPHABET

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "out" / "report"
FORK = WORK / "iosevka-fork"
OUTF = WORK / "blast"

METRIC = {   # parameter -> (low, high) metricOverride values
    "cap": (705, 765),
    "sb": ("'default_sb - 15'", "'default_sb + 15'"),
    "archDepth": ("'default_archDepth * 0.85'", "'default_archDepth * 1.15'"),
    "essRatioUpper": ("'default_essRatioUpper * 0.9'", "'default_essRatioUpper * 1.1'"),
    "onumZeroHeightRatio": (1.0, 1.3),
}
WEIGHT = (360, 440)
FORK_PARAMS = {"maxocrZeroInset": (20, 60), "maxocrOOutset": (15, 45)}


def glyphs(path: Path) -> dict:
    f = TTFont(str(path))
    cmap, gs = f.getBestCmap(), f.getGlyphSet()
    out = {}
    for c in PRIMARY_ALPHABET:
        pen = RecordingPen()
        gs[cmap[ord(c)]].draw(pen)
        out[c] = (f["hmtx"][cmap[ord(c)]][0], pen.value)
    return out


def fork_build(name: str, params: dict[str, int]) -> Path:
    out = OUTF / f"{name}.ttf"
    if out.exists():
        return out
    p = FORK / "params" / "parameters.toml"
    text = p.read_text()
    for k in FORK_PARAMS:
        text = re.sub(rf"^{k} = .*$", f"{k} = {params.get(k, 0)}", text, flags=re.M)
    p.write_text(text)
    (FORK / "private-build-plans.toml").unlink(missing_ok=True)
    (FORK / "private-build-plans.toml").write_text(plan_text({}))
    r = subprocess.run(["npm", "run", "build", "--", "ttf-unhinted::MaxOCRCand"], cwd=FORK, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stdout[-1500:] + r.stderr[-1500:])
    shutil.copy(FORK / "dist" / "MaxOCRCand" / "TTF-Unhinted" / "MaxOCRCand-Regular.ttf", out)
    return out


def main():
    OUTF.mkdir(parents=True, exist_ok=True)
    objective = json.loads((REPORT / "clusters.json").read_text())["objective"]
    cluster_of = {c: "".join(g) for g in objective for c in g}

    pool = BuildPool(8, WORK / "rung0" / "fonts")
    specs = {"default": ({}, 400, None)}
    for k, (lo, hi) in METRIC.items():
        specs[f"{k}=low"] = ({}, 400, {k: lo})
        specs[f"{k}=high"] = ({}, 400, {k: hi})
    specs["weight=low"] = ({}, WEIGHT[0], None)
    specs["weight=high"] = ({}, WEIGHT[1], None)
    built = dict(zip(specs, pool.build_many(list(specs.values()))))
    paths = {}
    for name, (path, err) in built.items():
        if err:
            print(f"{name}: build failed: {err[-300:]}")
        else:
            paths[name] = path
    for k, (lo, hi) in FORK_PARAMS.items():
        paths[f"{k}=low"] = fork_build(f"{k}_{lo}", {k: lo})
        paths[f"{k}=high"] = fork_build(f"{k}_{hi}", {k: hi})
    paths["fork default"] = fork_build("fork_default", {})

    base = glyphs(paths["default"])
    rows = []
    for name, p in paths.items():
        if name == "default":
            continue
        g = glyphs(p)
        changed = [c for c in PRIMARY_ALPHABET if g[c] != base[c]]
        adv = [c for c in PRIMARY_ALPHABET if g[c][0] != base[c][0]]
        clusters = sorted({cluster_of[c] for c in changed if c in cluster_of})
        rows.append({"parameter": name, "glyphs_changed": "".join(changed), "n_changed": len(changed),
                     "advance_changed": "".join(adv), "objective_clusters": " ".join(clusters),
                     "n_clusters": len(clusters)})
    df = pd.DataFrame(rows)
    df.to_csv(REPORT / "blast_radius.csv", index=False)

    lines = ["# R32a blast-radius map", "",
             "| Parameter | Glyphs changed | Advance changed | Objective clusters touched |", "|---|---|---|---|"]
    for r in df.itertuples():
        lines.append(f"| {r.parameter} | {r.glyphs_changed or '-'} | {r.advance_changed or '-'} | "
                     f"{r.objective_clusters or '-'} ({r.n_clusters}) |")
    local = sorted({r.parameter.split('=')[0] for r in df.itertuples() if r.n_clusters <= 1 and r.parameter != 'fork default'})
    coupled = sorted({r.parameter.split('=')[0] for r in df.itertuples() if r.n_clusters > 1})
    lines += ["", f"Local (at most one objective cluster): {', '.join(local) or '-'}",
              f"Coupling (several objective clusters, must join one block): {', '.join(coupled) or '-'}"]
    (REPORT / "blast_radius.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
