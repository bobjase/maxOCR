"""R15: EasyOCR recognition model (English, CRNN-style), detection bypassed, output limited to the
corpus alphabet. Used as a third optimizing engine in discovery; PARSeq remains held out."""
import numpy as np

from ..corpus import PRIMARY_ALPHABET


class EasyOCRRec:
    def __init__(self, alphabet: str = PRIMARY_ALPHABET, gpu: bool = True):
        import easyocr
        self.reader = easyocr.Reader(["en"], gpu=gpu, detector=False, recognizer=True, verbose=False)
        self.allow = alphabet

    def text(self, img: np.ndarray) -> str:
        h, w = img.shape[:2]
        out = self.reader.recognize(img, horizontal_list=[[0, w, 0, h]], free_list=[], detail=0,
                                    allowlist=self.allow, decoder="greedy", paragraph=False)
        return "".join(out).replace(" ", "")

    BOX_W = 384   # every line is padded with paper to this width: EasyOCR pads a batch to its widest
                  # item, so equal widths make each line's result independent of its batch-mates

    def texts(self, imgs: list[np.ndarray], gap: int = 8) -> list[str]:
        """Batch: stack lines on one paper-white canvas, each in a box of fixed width BOX_W, and
        recognize all boxes in one call. Use this (not text()) everywhere, so results are comparable."""
        W = max(self.BOX_W, max(im.shape[1] for im in imgs))
        H = sum(im.shape[0] + gap for im in imgs)
        canvas = np.full((H, W), 255, np.uint8)
        boxes, y = [], 0
        for im in imgs:
            h, w = im.shape[:2]
            canvas[y:y + h, :w] = im
            boxes.append([0, W, y, y + h])
            y += h + gap
        out = self.reader.recognize(canvas, horizontal_list=boxes, free_list=[], detail=1,
                                    allowlist=self.allow, decoder="greedy", paragraph=False,
                                    batch_size=len(imgs))
        # detail=1 returns (box, text, conf); map back by the box's top edge.
        by_top = {int(r[0][0][1]): r[1] for r in out}
        return [by_top.get(b[2], "").replace(" ", "") for b in boxes]
