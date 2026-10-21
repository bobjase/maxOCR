"""Read the benchmark pages (scripts/dump_pages.py) with Windows' built-in OCR or Google Cloud Vision and score them
(2026-10-21: two commercial engines next to the four open ones). Every recognised word is put on the line whose
vertical span holds its centre, words on a line are joined left to right, and the character error is computed exactly
as for the other engines (spaces ignored). Runs on Windows Python.

    python scripts/page_engines.py --engine windows|google [--pages out/pages] [--max-calls 950]
Writes out/report/page_<engine>.csv (resumable) and saves each page's readings next to it.
"""
import argparse
import base64
import csv
import glob
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from maxocr.align import align  # noqa: E402


def char_err(truths, preds) -> float:
    n = k = 0
    for t, p in zip(truths, preds):
        t, p = t.replace(" ", ""), p.replace(" ", "")
        _, mapping, n_ins = align(t, p)
        k += sum(1 for i, j in enumerate(mapping) if j is None or p[j] != t[i]) + n_ins
        n += len(t)
    return 100 * k / max(n, 1)


def words_windows(path, spans=None):
    """Windows OCR takes images up to 10,000 px a side, so tall pages are read in pieces cut between lines."""
    from PIL import Image
    im = Image.open(path)
    if im.height > 9500 and spans:
        out, top, cut_at = [], 0, []
        for s in spans:
            if s["y1"] - top > 9000:
                cut_at.append(s["y0"] - 10); top = s["y0"] - 10
        edges = [0] + cut_at + [im.height]
        for y0, y1 in zip(edges, edges[1:]):
            tile = path[:-4] + f".tile{y0}.png"; im.crop((0, y0, im.width, y1)).save(tile)
            out += [(t, x, yc + y0) for t, x, yc in words_windows(tile)]
            os.remove(tile)
        return out
    import asyncio
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage import FileAccessMode, StorageFile

    async def run():
        eng = OcrEngine.try_create_from_user_profile_languages()
        f = await StorageFile.get_file_from_path_async(os.path.abspath(path))
        bmp = await (await BitmapDecoder.create_async(await f.open_async(FileAccessMode.READ))).get_software_bitmap_async()
        res = await eng.recognize_async(bmp)
        return [(w.text, w.bounding_rect.x, w.bounding_rect.y + w.bounding_rect.height / 2) for ln in res.lines for w in ln.words]
    return asyncio.run(run())


def words_google(path, key):
    body = json.dumps({"requests": [{"image": {"content": base64.b64encode(open(path, "rb").read()).decode()},
                                     "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                                     "imageContext": {"languageHints": ["en"]}}]}).encode()
    req = urllib.request.Request("https://vision.googleapis.com/v1/images:annotate?key=" + key, data=body,
                                 headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120))["responses"][0]
    out = []
    for page in r.get("fullTextAnnotation", {}).get("pages", []):
        for b in page["blocks"]:
            for p in b["paragraphs"]:
                for w in p["words"]:
                    v = w["boundingBox"]["vertices"]
                    xs = [q.get("x", 0) for q in v]; ys = [q.get("y", 0) for q in v]
                    out.append(("".join(s["text"] for s in w["symbols"]), min(xs), sum(ys) / len(ys)))
    return out


def lines_from_words(words, spans):
    got = [[] for _ in spans]
    for text, x, yc in words:
        for i, s in enumerate(spans):
            if s["y0"] - 18 <= yc <= s["y1"] + 18:
                got[i].append((x, text)); break
    return [" ".join(t for _, t in sorted(g)) for g in got]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["windows", "google"], required=True)
    ap.add_argument("--pages", default="out/pages")
    ap.add_argument("--max-calls", type=int, default=950, help="Google: stop before this many requests (free tier 1,000/month)")
    a = ap.parse_args()
    out = f"out/report/page_{a.engine}.csv"
    done = set()
    if os.path.exists(out):
        done = {(r["font"], r["text"], r["condition"]) for r in csv.DictReader(open(out, encoding="utf-8"))}
    key = open(".google-key").read().strip() if a.engine == "google" else None
    calls = 0
    with open(out, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if not done:
            w.writerow(["font", "text", "condition", a.engine])
        for png in sorted(glob.glob(os.path.join(a.pages, "*", "*.png"))):
            font = os.path.basename(os.path.dirname(png)).replace("_", " ")
            kind, cond = os.path.basename(png)[:-4].split("_", 1)
            cond = {"ink-bleed": "ink bleed", "phone-photo": "phone photo", "dot-matrix-lq": "dot-matrix lq"}.get(cond, cond)
            if (font, kind, cond) in done:
                continue
            if a.engine == "google" and calls >= a.max_calls:
                print("stopped at the call limit", calls); break
            spans = json.load(open(png[:-4] + ".json"))
            words = words_windows(png, spans) if a.engine == "windows" else words_google(png, key)
            calls += 1
            reads = lines_from_words(words, spans)
            json.dump(reads, open(png[:-4] + f".{a.engine}.json", "w"))
            err = round(char_err([s["truth"] for s in spans], reads), 2)
            w.writerow([font, kind, cond, err]); fh.flush()
            print(font, kind, cond, err, flush=True)
    print("requests", calls)


if __name__ == "__main__":
    main()
