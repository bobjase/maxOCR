"""Windows' built-in OCR engine (Windows.Media.Ocr, the reader behind the Snipping Tool's text actions) on Windows
Python (2026-10-21, after an outside review asked for commercial engines). Reads a page image and returns its lines
with their vertical centres, so lines stacked on one page can be matched back to their slots.

    python scripts/winocr.py page.png
"""
import asyncio
import sys

from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage import FileAccessMode, StorageFile

ENGINE = OcrEngine.try_create_from_user_profile_languages()


async def _read(path: str):
    f = await StorageFile.get_file_from_path_async(path)
    stream = await f.open_async(FileAccessMode.READ)
    bmp = await (await BitmapDecoder.create_async(stream)).get_software_bitmap_async()
    res = await ENGINE.recognize_async(bmp)
    out = []
    for line in res.lines:
        ws = list(line.words)
        ys = [w.bounding_rect.y + w.bounding_rect.height / 2 for w in ws]
        out.append((" ".join(w.text for w in ws), sum(ys) / len(ys)))
    return out


def read(path: str):
    return asyncio.run(_read(path))


if __name__ == "__main__":
    for t, y in read(sys.argv[1]):
        print(round(y), t)
