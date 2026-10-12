"""Which fonts' punctuation do the engines read most reliably? (James: "as before, let's look at open source fonts to
see who does punctuation best".) MaxOCR has no punctuation yet; this picks the shapes to borrow.

Every open-licence face in out/ofl_faces.json (the only ones MaxOCR may borrow from) plus the installed Windows
faces (measurement only, read in place) that have 0-9, A-Z, a-z and all 32 ASCII punctuation marks, at equal
capital height, on 400 random lines over 0-9A-Za-z and punctuation with each mark oversampled (x6), s=0.5,
suite (a). PaddleOCR and EasyOCR read the general alphabet (0-9A-Za-z + punctuation) case-sensitively, Tesseract
with that whitelist (PARSeq held out). Per face and mark: correct-read rate (mean over engines) and what the mark is
misread as; overall punctuation accuracy and character error. Resumable in batches.

    python scripts/punct_survey.py [--max-faces 64] [--ofl-only]
    python scripts/punct_survey.py --report      -> out/report/punct_survey.csv, punct_survey_marks.csv
"""
import argparse
import json
import string
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from font_survey import matched_size as survey_size  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET, make_strings  # noqa: E402
from maxocr.degrade import make_instance  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "survey_punct"
PUNCT = string.punctuation
ENGINES = ("paddle", "tesseract", "easyocr")


def faces(ofl_only: bool = False) -> list[dict]:
    from fontTools.ttLib import TTCollection, TTFont
    out = []
    for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]:
        t = TTFont(f["path"])
        if all(ord(c) in (t.getBestCmap() or {}) for c in GENERAL_ALPHABET):
            out.append({"face": f"{f['family']} (OFL)", "font": f["path"], "size_pt": survey_size(t), "licence": "ofl"})
    if ofl_only:
        return out
    for f in json.loads((ROOT / "out" / "survey" / "faces.json").read_text()):
        path, _, i = f["font"].partition("#")
        try:
            t = TTCollection(path).fonts[int(i or 0)] if path.lower().endswith(".ttc") else TTFont(path)
            if all(ord(c) in (t.getBestCmap() or {}) for c in GENERAL_ALPHABET):
                out.append({"face": f["face"], "font": f["font"], "size_pt": f["size_pt"], "licence": "windows"})
        except Exception:
            continue
    return out


def bank(n: int = 400, seed: int = 3232):
    w = np.array([6.0 if c in PUNCT else 1.0 for c in GENERAL_ALPHABET])
    texts = make_strings(n, seed, alphabet=GENERAL_ALPHABET, weights=w / w.sum())
    return [i for i in (make_instance(k, s, seed) for k, s in enumerate(texts)) if not i.cropped]


def report():
    chars = pd.concat(pd.read_parquet(p) for p in sorted(OUT.glob("batch_*.parquet")))
    idx = {f["font"]: f for f in json.loads((OUT / "faces.json").read_text())}
    rows, marks = [], []
    for font, g in chars.groupby("font"):
        acc = {}
        for c in PUNCT:
            h = g[g.truth == c]
            acc[c] = float(np.mean([(h[h.engine == e].pred == c).mean() for e in ENGINES]))
            miss = h[h.pred != c].pred.value_counts()
            marks.append({"face": idx[font]["face"], "licence": idx[font]["licence"], "mark": c,
                          "acc": round(100 * acc[c], 1), "read_as": " ".join(f"{k}:{v}" for k, v in miss.head(3).items())})
        rows.append({"face": idx[font]["face"], "licence": idx[font]["licence"], "font": font,
                     "char_err": round(100 * float((g.pred != g.truth).mean()), 2),
                     "punct_acc": round(100 * float(np.mean(list(acc.values()))), 1),
                     "alnum_err": round(100 * float((g[~g.truth.isin(list(PUNCT))].pred != g[~g.truth.isin(list(PUNCT))].truth).mean()), 2)})
    df = pd.DataFrame(rows).sort_values("punct_acc", ascending=False)
    df.to_csv(ROOT / "out" / "report" / "punct_survey.csv", index=False)
    m = pd.DataFrame(marks)
    m.to_csv(ROOT / "out" / "report" / "punct_survey_marks.csv", index=False)
    with pd.option_context("display.width", 200):
        print(df.drop(columns="font").head(20).to_string(index=False))
        print(df[df.licence == "ofl"].drop(columns="font").to_string(index=False))
        best = m[m.licence == "ofl"].sort_values("acc", ascending=False).groupby("mark").head(1)
        print("best open-licence face per mark:")
        print(best.sort_values("mark").to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-faces", type=int, default=64)
    ap.add_argument("--ofl-only", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        return report()
    OUT.mkdir(parents=True, exist_ok=True)
    index = OUT / "faces.json"
    if not index.exists():
        index.write_text(json.dumps(faces(a.ofl_only), indent=1))
    all_faces = json.loads(index.read_text())
    done = set()
    for p in OUT.glob("batch_*.parquet"):
        done |= set(pd.read_parquet(p, columns=["font"]).font.unique())
    todo = [f for f in all_faces if f["font"] not in done][:a.max_faces]
    print(f"{len(all_faces)} faces, {len(done)} done, running {len(todo)}", flush=True)
    if not todo:
        return
    from maxocr.engines.easyocr_rec import EasyOCRRec
    paddle = rung0.PaddleRec(alphabet=GENERAL_ALPHABET, casefold=False)
    easy = EasyOCRRec(alphabet=GENERAL_ALPHABET, casefold=False)
    b = bank()
    jobs = [Job(f["font"], f["font"], rung0.SEVERITY, "a", c, size_pt=f["size_pt"]) for f in todo for c in chunk(b, 50)]
    ch, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_whitelist=GENERAL_ALPHABET)
    k = len(list(OUT.glob("batch_*.parquet")))
    ch[["font", "engine", "truth", "pred"]].to_parquet(OUT / f"batch_{k:03d}.parquet")
    print(f"batch {k}: {len(todo)} faces", flush=True)


if __name__ == "__main__":
    main()
