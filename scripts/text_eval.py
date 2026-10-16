"""Real-text check (R13c): the Gettysburg Address in capitals, spaces kept, punctuation removed (the
fonts have only 0-9, A-Z and space). Lines of at most 22 characters (PARSeq's limit is 25), rendered at 8 pt / 200 dpi, s=0.5,
suite (a), plus clean. Engines may use language: PaddleOCR, EasyOCR and PARSeq read the general
alphabet with case folded; Tesseract reads without a whitelist and with its dictionaries ON; the
Qwen2.5-VL reader (open vocabulary) is optional. Character error from alignment, spaces ignored.
--story: the grocery story with all its punctuation instead (fonts must have the marks), case-sensitive.

    python scripts/text_eval.py --fonts-json f.json [--vlm] [--out text_eval.csv]
"""
import argparse
import json
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rung0  # noqa: E402
from maxocr.align import align  # noqa: E402
from maxocr.corpus import GENERAL_ALPHABET  # noqa: E402
from maxocr.degrade import clean, degrade, make_instance  # noqa: E402
from maxocr.fonts import matched_size  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GETTYSBURG = """Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived
in Liberty, and dedicated to the proposition that all men are created equal. Now we are engaged in a great
civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure. We are
met on a great battle-field of that war. We have come to dedicate a portion of that field, as a final resting
place for those who here gave their lives that that nation might live. It is altogether fitting and proper
that we should do this. But, in a larger sense, we can not dedicate -- we can not consecrate -- we can not
hallow -- this ground. The brave men, living and dead, who struggled here, have consecrated it, far above
our poor power to add or detract. The world will little note, nor long remember what we say here, but it
can never forget what they did here. It is for us the living, rather, to be dedicated here to the unfinished
work which they who fought here have thus far so nobly advanced. It is rather for us to be here dedicated to
the great task remaining before us -- that from these honored dead we take increased devotion to that cause
for which they gave the last full measure of devotion -- that we here highly resolve that these dead shall
not have died in vain -- that this nation, under God, shall have a new birth of freedom -- and that
government of the people, by the people, for the people, shall not perish from the earth."""


def lines(mixed_case: bool = False) -> list[str]:
    text = GETTYSBURG if mixed_case else GETTYSBURG.upper()
    words = "".join(c if c.isalnum() or c.isspace() else " " for c in text).split()
    return textwrap.wrap(" ".join(words), 22)   # PARSeq reads at most 25 characters


def read_tesseract_dict(imgs, fold: bool = True):
    from tesserocr import OEM, PSM, PyTessBaseAPI
    from PIL import Image
    from maxocr.engines.tesseract import TESSDATA_BEST
    import os
    from concurrent.futures import ThreadPoolExecutor
    # MAXOCR_TESS_PSM=13: "raw line", which skips Tesseract's layout step (it blanked readable ink-bleed lines)
    psm = int(os.environ.get("MAXOCR_TESS_PSM", PSM.SINGLE_LINE))
    # several Tesseract instances in threads (tesserocr releases the GIL while recognising; each thread has its own
    # API object, Tesseract itself limited to one core each): same readings, several times faster
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    k = max(1, min(int(os.environ.get("MAXOCR_TESS_THREADS", "8")), len(imgs)))
    chunks = [list(range(i, len(imgs), k)) for i in range(k)]

    def run(idx):
        res = []
        with PyTessBaseAPI(path=str(TESSDATA_BEST) + "/", lang="eng", oem=OEM.LSTM_ONLY, psm=psm) as api:
            for i in idx:
                api.SetImage(Image.fromarray(imgs[i]))
                res.append((i, api.GetUTF8Text().strip()))
        return res
    out = [""] * len(imgs)
    with ThreadPoolExecutor(k) as ex:
        for res in ex.map(run, chunks):
            for i, t in res:
                out[i] = t.upper() if fold else t
    return out


def char_err(truths, preds) -> float:
    n = k = 0
    for t, p in zip(truths, preds):
        t, p = t.replace(" ", ""), p.replace(" ", "")
        _, mapping, n_ins = align(t, p)
        k += sum(1 for i, j in enumerate(mapping) if j is None or p[j] != t[i]) + n_ins
        n += len(t)
    return 100 * k / max(n, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts-json", required=True)
    ap.add_argument("--vlm", action="store_true")
    ap.add_argument("--vlm-only", action="store_true", help="only the Qwen2.5-VL reader (keeps GPU memory free)")
    ap.add_argument("--repeats", type=int, default=8, help="degraded draws per line")
    ap.add_argument("--out", default="text_eval.csv")
    ap.add_argument("--story", action="store_true",
                    help="the grocery story (maxocr/grocery_story.txt) with its punctuation, read case-sensitively")
    ap.add_argument("--mixed-case", action="store_true",
                    help="the address as written (mixed case, no punctuation), read and scored case-sensitively")
    a = ap.parse_args()
    fonts = json.loads(Path(a.fonts_json).read_text())
    if a.story:
        from maxocr.prose import story_lines
        texts, a.mixed_case = story_lines(22), True
    else:
        texts = lines(a.mixed_case)
    insts = [make_instance(k, t, 1863) for k, t in enumerate(texts * a.repeats)]
    insts = [i for i in insts if not i.cropped]
    eng = dict(alphabet=GENERAL_ALPHABET, casefold=not a.mixed_case)
    if not a.vlm_only:
        from maxocr.engines.easyocr_rec import EasyOCRRec
        from maxocr.engines.parseq import Parseq
        paddle, easy, pq = rung0.PaddleRec(**eng), EasyOCRRec(**eng), Parseq(**eng)
    vlm = None
    if a.vlm or a.vlm_only:
        from maxocr.engines.qwenvl import QwenVL
        vlm = QwenVL(prompt="Transcribe the text in this image exactly. Output only the text.", casefold=not a.mixed_case)
    rows = []
    for cond in ("s=0.5", "clean"):
        for name, path in fonts.items():
            sz = matched_size(path, 8.0)   # equal capital height
            imgs = [clean(path, i.text, sz, 200, True) for i in insts] if cond == "clean" else \
                   [degrade(path, i, rung0.SEVERITY, sz) for i in insts]
            truths = [i.text for i in insts]
            preds = {} if a.vlm_only else {
                "paddle": [paddle.text(im) for im in imgs], "easyocr": easy.texts(imgs),
                "parseq": pq.read(imgs), "tesseract (dictionary)": read_tesseract_dict(imgs, fold=not a.mixed_case)}
            if vlm is not None:
                preds["qwen2.5-vl"] = vlm.read(imgs)
            row = {"font": name, "condition": cond}
            for e, p in preds.items():
                row[e] = round(char_err(truths, p), 2)
            row["mean"] = round(float(np.mean([row[e] for e in preds])), 2)
            rows.append(row)
            print(json.dumps(row), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "out" / "report" / a.out, index=False)
    with pd.option_context("display.width", 200):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
