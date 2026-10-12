"""Which fonts keep their capital S apart from s, 5 and 8? (James: "revisit the 400 fonts and see who rendered
[the S] most reliably".) The 2026-10-08 survey read capitals and digits only, so it measured 5/S but not S/s.

Every installed Windows face with 0-9, A-Z and a-z (measurement only, read in place) plus the open-licence
faces in out/ofl_faces.json (the only ones MaxOCR may borrow from), at equal capital height, on 400 random
0-9A-Za-z lines that oversample S, s, 5, 8 (x8), s=0.5, suite (a). PaddleOCR, Tesseract and EasyOCR read
case-sensitively restricted to 0-9A-Za-z (PARSeq held out). Per face: correct-read rate of S, s, 5, 8 per
engine, what S is misread as, and overall character error. Resumable in batches.

    python scripts/s_survey.py [--max-faces 64]
Writes out/survey_s/batch_*.parquet; python scripts/s_survey.py --report writes out/report/s_survey.csv.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from font_survey import matched_size as survey_size  # noqa: E402
from maxocr.corpus import ALNUM_ALPHABET, make_strings  # noqa: E402
from maxocr.degrade import make_instance  # noqa: E402
from maxocr.evaluate import Job, chunk, run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "survey_s"
FOCUS = "Ss58"
ENGINES = ("paddle", "tesseract", "easyocr")


def faces() -> list[dict]:
    from fontTools.ttLib import TTCollection, TTFont
    out = []
    win = json.loads((ROOT / "out" / "survey" / "faces.json").read_text())
    for f in win:
        path, _, i = f["font"].partition("#")
        try:
            t = TTCollection(path).fonts[int(i or 0)] if path.lower().endswith(".ttc") else TTFont(path)
            if all(ord(c) in (t.getBestCmap() or {}) for c in ALNUM_ALPHABET):
                out.append({"face": f["face"], "font": f["font"], "size_pt": f["size_pt"], "licence": "windows"})
        except Exception:
            continue
    for f in json.loads((ROOT / "out" / "ofl_faces.json").read_text())["faces"]:
        t = TTFont(f["path"])
        if all(ord(c) in (t.getBestCmap() or {}) for c in ALNUM_ALPHABET):
            out.append({"face": f"{f['family']} (OFL)", "font": f["path"], "size_pt": survey_size(t), "licence": "ofl"})
    for name, path in (("MaxOCR F (tall S)", "~/maxocr-work/keep/MaxOCR-Text-v04f.ttf"),
                       ("MaxOCR U (even capitals)", "~/maxocr-work/keep/MaxOCR-Text-v04u.ttf")):
        path = str(Path(path).expanduser())
        out.append({"face": name, "font": path, "size_pt": survey_size(TTFont(path)), "licence": "maxocr"})
    return out


def bank(n: int = 400, seed: int = 5858):
    w = np.array([8.0 if c in FOCUS else 1.0 for c in ALNUM_ALPHABET])
    texts = make_strings(n, seed, alphabet=ALNUM_ALPHABET, weights=w / w.sum())
    return [i for i in (make_instance(k, s, seed) for k, s in enumerate(texts)) if not i.cropped]


def report():
    chars = pd.concat(pd.read_parquet(p) for p in sorted(OUT.glob("batch_*.parquet")))
    idx = {f["font"]: f for f in json.loads((OUT / "faces.json").read_text())}
    rows = []
    for font, g in chars.groupby("font"):
        r = {"face": idx[font]["face"], "licence": idx[font]["licence"], "font": font,
             "char_err": round(100 * float((g.pred != g.truth).mean()), 2)}
        for c in FOCUS:
            h = g[g.truth == c]
            r[f"{c}_acc"] = round(100 * float(np.mean([(h[h.engine == e].pred == c).mean() for e in ENGINES])), 1)
        miss = g[(g.truth == "S") & (g.pred != "S")].pred.value_counts()
        r["S_read_as"] = " ".join(f"{k}:{v}" for k, v in miss.head(3).items())
        rows.append(r)
    df = pd.DataFrame(rows).sort_values("S_acc", ascending=False)
    df.to_csv(ROOT / "out" / "report" / "s_survey.csv", index=False)
    readable = df[df.char_err < 15]
    print(f"{len(df)} faces, {len(readable)} readable (char error < 15%)")
    with pd.option_context("display.width", 200):
        print(readable.drop(columns="font").head(25).to_string(index=False))
        print(readable[readable.licence == "ofl"].drop(columns="font").head(12).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-faces", type=int, default=64)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        return report()
    OUT.mkdir(parents=True, exist_ok=True)
    index = OUT / "faces.json"
    if not index.exists():
        index.write_text(json.dumps(faces(), indent=1))
    all_faces = json.loads(index.read_text())
    done = set()
    for p in OUT.glob("batch_*.parquet"):
        done |= set(pd.read_parquet(p, columns=["font"]).font.unique())
    todo = [f for f in all_faces if f["font"] not in done][:a.max_faces]
    print(f"{len(all_faces)} faces, {len(done)} done, running {len(todo)}", flush=True)
    if not todo:
        return
    from maxocr.engines.easyocr_rec import EasyOCRRec
    paddle, easy = rung0.PaddleRec(alphabet=ALNUM_ALPHABET), EasyOCRRec(alphabet=ALNUM_ALPHABET)
    b = bank()
    jobs = [Job(f["font"], f["font"], rung0.SEVERITY, "a", c, size_pt=f["size_pt"]) for f in todo for c in chunk(b, 50)]
    ch, _, _ = run(jobs, rung0.EVAL_WORKERS, paddle=paddle, progress=False, easy=easy, tess_whitelist=ALNUM_ALPHABET)
    k = len(list(OUT.glob("batch_*.parquet")))
    ch[["font", "engine", "truth", "pred"]].to_parquet(OUT / f"batch_{k:03d}.parquet")
    print(f"batch {k}: {len(todo)} faces", flush=True)


if __name__ == "__main__":
    main()
