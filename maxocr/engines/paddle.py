"""R11/R11a: PP-OCRv6 recognition via ONNX Runtime, detection bypassed."""
from dataclasses import dataclass
from math import ceil
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import yaml

from ..corpus import PRIMARY_ALPHABET

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "vendor" / "ppocrv6_medium_rec"
IMG_H, MIN_W = 48, 320  # from inference.yml RecResizeImg


@dataclass
class Char:
    text: str
    frame: int            # max-confidence frame within the run
    probs: np.ndarray     # distribution over self.classes at that frame


class PaddleRec:
    def __init__(self, model_dir: Path = MODEL_DIR, alphabet: str | None = PRIMARY_ALPHABET,
                 providers=("CUDAExecutionProvider", "CPUExecutionProvider"), casefold: bool = False):
        """casefold: report lowercase output as uppercase (use with GENERAL_ALPHABET)."""
        cfg = yaml.safe_load(open(model_dir / "inference.yml"))
        # PaddleOCR CTC convention: index 0 is blank, space appended last.
        self.vocab = ["<blank>"] + [str(c) for c in cfg["PostProcess"]["character_dict"]] + [" "]
        # The GPU does the work; ORT's default CPU thread pool (one spinning thread per core)
        # would otherwise fight the Tesseract workers for every core.
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")
        so.add_session_config_entry("session.inter_op.allow_spinning", "0")
        self.sess = ort.InferenceSession(str(model_dir / "inference.onnx"), so, providers=list(providers))
        self.input_name = self.sess.get_inputs()[0].name
        # Restricting to the corpus alphabet mirrors Tesseract's whitelist (R12).
        if alphabet is None:
            self.keep = np.arange(len(self.vocab))
        else:
            index = {c: i for i, c in enumerate(self.vocab)}
            self.keep = np.array([0] + [index[c] for c in alphabet if c in index])
        self.classes = [self.vocab[i] for i in self.keep]
        self.casefold = casefold

    @staticmethod
    def preprocess(img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        target_w = int(IMG_H * max(MIN_W / IMG_H, w / h))
        resized_w = min(target_w, ceil(IMG_H * w / h))
        x = cv2.resize(img, (resized_w, IMG_H)).astype(np.float32)
        x = (x / 255.0 - 0.5) / 0.5
        out = np.zeros((3, IMG_H, target_w), np.float32)
        out[:, :, :resized_w] = x[None]  # grayscale -> 3 identical channels
        return out[None]

    def frame_probs(self, img: np.ndarray) -> np.ndarray:
        """(T, len(self.classes)) per-frame softmax, renormalized over kept classes."""
        p = self.sess.run(None, {self.input_name: self.preprocess(img)})[0][0]
        p = p[:, self.keep]
        return p / p.sum(axis=1, keepdims=True)

    def read(self, img: np.ndarray) -> list[Char]:
        """Greedy CTC decode. A run is a maximal span of frames with the same non-blank argmax."""
        p = self.frame_probs(img)
        best = p.argmax(axis=1)
        out, t = [], 0
        while t < len(best):
            if best[t] == 0:
                t += 1
                continue
            end = t
            while end + 1 < len(best) and best[end + 1] == best[t]:
                end += 1
            f = t + int(p[t:end + 1, best[t]].argmax())
            c = self.classes[best[t]]
            out.append(Char(c.upper() if self.casefold else c, f, p[f]))
            t = end + 1
        return out

    def text(self, img: np.ndarray) -> str:
        return "".join(c.text for c in self.read(img))
