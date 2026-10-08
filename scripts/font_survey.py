"""Survey of installed Windows fonts: which ones do PaddleOCR and Tesseract read correctly?

Measurement only. Fonts are read in place from C:\\Windows\\Fonts and never copied into the repo;
results (names and numbers) are. PARSeq is deliberately NOT used: it is the held-out engine.

Each face with all 36 primary characters is rendered at the point size that gives it the same
capital height as Source Code Pro at 8 pt, on a 300-line bank that oversamples the objective-
cluster characters, suite (a), under the R7a clean condition (recorded as severity -1) and at the
operating point. Resumable: faces already in
out/survey/ are skipped, so the run can be split across capped invocations.

    python scripts/font_survey.py --max-faces 60          # one capped batch
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTCollection, TTFont

from maxocr.corpus import PRIMARY_ALPHABET, make_strings
from maxocr.degrade import make_instance
from maxocr.evaluate import Job, chunk, run
from maxocr.fonts import BASELINES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "survey"
WIN_FONTS = Path("/mnt/c/Windows/Fonts")
SURVEY_SEED = 606
N_LINES = 300
REF_FONT, REF_SIZE = BASELINES["Source Code Pro"], 8.0


def cap_height(f: TTFont) -> float:
    """Capital height in font units, measured from the outline of H (OS/2 values are unreliable)."""
    gs = f.getGlyphSet()
    pen = BoundsPen(gs)
    gs[f.getBestCmap()[ord("H")]].draw(pen)
    return pen.bounds[3] - pen.bounds[1]


def ref_cap() -> float:
    ref = TTFont(str(REF_FONT))
    return cap_height(ref) / ref["head"].unitsPerEm


def matched_size(f: TTFont) -> float:
    """Point size giving this face the reference capital height."""
    return round(REF_SIZE * ref_cap() / (cap_height(f) / f["head"].unitsPerEm), 3)


def faces() -> list[dict]:
    out = []
    for p in sorted(WIN_FONTS.iterdir()):
        if p.suffix.lower() not in (".ttf", ".otf", ".ttc"):
            continue
        try:
            members = TTCollection(str(p)).fonts if p.suffix.lower() == ".ttc" else [TTFont(str(p))]
        except Exception:
            continue
        for i, f in enumerate(members):
            try:
                # Symbol fonts (Webdings, Wingdings, ...) map letter codes to pictures.
                if f["cmap"].getcmap(3, 0) is not None:
                    continue
                cmap = f.getBestCmap() or {}
                if not all(ord(c) in cmap for c in PRIMARY_ALPHABET):
                    continue
                adv = {f["hmtx"][cmap[ord(c)]][0] for c in PRIMARY_ALPHABET}
                out.append({"face": f["name"].getDebugName(4) or p.stem, "font": f"{p}#{i}",
                            "monospaced": len(adv) == 1,
                            "size_pt": matched_size(f) if cap_height(f) > 0 else None})
            except Exception:
                continue
    return [f for f in out if f["size_pt"] and 4 <= f["size_pt"] <= 20]


def survey_strings(n: int = N_LINES, seed: int = SURVEY_SEED) -> list[str]:
    clusters = json.loads((ROOT / "out" / "report" / "clusters.json").read_text())["objective"]
    members = {c for g in clusters for c in g}
    w = np.array([3.0 if c in members else 1.0 for c in PRIMARY_ALPHABET])
    return make_strings(n, seed, weights=w / w.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-faces", type=int, default=60)
    ap.add_argument("--severity", type=float, default=0.5, help="operating point; clean is always included")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", type=Path, default=OUT, help="output folder (resumable per folder)")
    ap.add_argument("--seed", type=int, default=SURVEY_SEED)
    ap.add_argument("--lines", type=int, default=N_LINES)
    ap.add_argument("--faces-json", type=Path, help="explicit face list instead of all Windows fonts")
    a = ap.parse_args()
    out_dir = a.out
    out_dir.mkdir(parents=True, exist_ok=True)

    index_file = out_dir / "faces.json"
    if not index_file.exists():
        index_file.write_text(json.dumps(json.loads(a.faces_json.read_text()) if a.faces_json else faces(), indent=1))
    all_faces = json.loads(index_file.read_text())
    done_fonts = set()
    for p in out_dir.glob("batch_*_strings.parquet"):
        done_fonts |= set(pd.read_parquet(p, columns=["font"]).font.unique())
    todo = [f for f in all_faces if f["font"] not in done_fonts][:a.max_faces]
    print(f"{len(all_faces)} faces, {len(done_fonts)} done, running {len(todo)}", flush=True)
    if not todo:
        return

    insts = [make_instance(i, s, a.seed) for i, s in enumerate(survey_strings(a.lines, a.seed))]
    conditions = [(-1.0, True), (a.severity, False)]   # (severity label, R7a clean)
    jobs = [Job(f["font"], f["font"], sev, "a", c, size_pt=f["size_pt"], clean=clean)
            for f in todo for sev, clean in conditions for c in chunk(insts, 50)]
    st = {}
    chars, strings, _ = run(jobs, a.workers, progress=False, stats=st)
    for df in (chars, strings):
        df["face"] = df.font.map({f["font"]: f["face"] for f in todo})
    k = len(list(out_dir.glob("batch_*_chars.parquet")))
    chars.drop(columns=["probs"]).to_parquet(out_dir / f"batch_{k:03d}_chars.parquet")
    strings.to_parquet(out_dir / f"batch_{k:03d}_strings.parquet")
    print(f"batch {k}: {len(todo)} faces, {sum(len(j.instances) for j in jobs)} images in {st['wall']:.0f}s", flush=True)


if __name__ == "__main__":
    main()
