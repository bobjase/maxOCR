"""R12/R12b/R15b: Tesseract wrappers, one persistent API object per process."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from tesserocr import OEM, PSM, RIL, PyTessBaseAPI, iterate_level

from ..corpus import PRIMARY_ALPHABET

ROOT = Path(__file__).resolve().parents[2]
TESSDATA_BEST = ROOT / "vendor" / "tessdata_best"
TESSDATA_LEGACY = ROOT / "vendor" / "tessdata_legacy"


@dataclass
class Symbol:
    text: str
    conf: float
    alternatives: list[tuple[str, float]]  # ChoiceIterator, chosen path only (R12b)


class Tesseract:
    def __init__(self, legacy: bool = False, whitelist: str = PRIMARY_ALPHABET):
        path = TESSDATA_LEGACY if legacy else TESSDATA_BEST
        oem = OEM.TESSERACT_ONLY if legacy else OEM.LSTM_ONLY
        self.api = PyTessBaseAPI(
            path=str(path) + "/", lang="eng", oem=oem, psm=PSM.SINGLE_LINE,
            variables={"load_system_dawg": "0", "load_freq_dawg": "0"},
        )
        self.api.SetVariable("tessedit_char_whitelist", whitelist)
        if not legacy:
            self.api.SetVariable("lstm_choice_mode", "2")

    def read(self, img: np.ndarray) -> list[Symbol]:
        self.api.SetImage(Image.fromarray(img))
        self.api.Recognize()
        out = []
        ri = self.api.GetIterator()
        if ri is None:
            return out
        for r in iterate_level(ri, RIL.SYMBOL):
            try:
                text = r.GetUTF8Text(RIL.SYMBOL)
            except RuntimeError:  # tesserocr raises on empty symbols
                continue
            # ChoiceIterator order is ~2% non-monotonic in confidence; rank must use sorted order.
            # On heavily degraded input some choices carry no text; they are not classes.
            alts = sorted(((c.GetUTF8Text(), c.Confidence()) for c in r.GetChoiceIterator()),
                          key=lambda a: -a[1])
            alts = [a for a in alts if a[0]]
            out.append(Symbol(text, r.Confidence(RIL.SYMBOL), alts))
        return out

    def text(self, img: np.ndarray) -> str:
        return "".join(s.text for s in self.read(img))

    def close(self):
        self.api.End()
