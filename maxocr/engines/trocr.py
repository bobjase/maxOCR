"""TrOCR base, printed (microsoft/trocr-base-printed): Microsoft's transformer line reader, fine-tuned on printed
receipts (SROIE). Added 2026-10-21 after an outside review asked for modern transformer OCR. Reads one line image at a
time (resized to its 384x384 input), greedy decoding, half precision on the GPU. Its output is free text (no alphabet
restriction is possible with its word-piece vocabulary), as a deployed TrOCR would give.
"""
import numpy as np
import torch
from PIL import Image

MODEL = "microsoft/trocr-base-printed"


class TrOCR:
    def __init__(self, device: str = "cuda"):
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        self.proc = TrOCRProcessor.from_pretrained(MODEL)
        self.model = VisionEncoderDecoderModel.from_pretrained(MODEL, torch_dtype=torch.float16).eval().to(device)
        self.device = device

    @torch.no_grad()
    def read(self, imgs: list[np.ndarray], batch: int = 64) -> list[str]:
        out = []
        for i in range(0, len(imgs), batch):
            ims = [Image.fromarray(im).convert("RGB") for im in imgs[i:i + batch]]
            px = self.proc(images=ims, return_tensors="pt").pixel_values.to(self.device, torch.float16)
            ids = self.model.generate(px, max_new_tokens=64, num_beams=1)
            out += [t.strip() for t in self.proc.batch_decode(ids, skip_special_tokens=True)]
        return out
