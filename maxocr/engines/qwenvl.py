"""Vision-language model reader (Qwen2.5-VL), held out like PARSeq: never used to steer the search.

Reads with an open vocabulary (it cannot be restricted to 0-9A-Z); output has spaces removed and case
folded, matching the general-alphabet reading of the other engines.
"""
import numpy as np
import torch
from PIL import Image

MODEL = "Qwen/Qwen2.5-VL-3B-Instruct"
PROMPT = ("Transcribe the characters in this image exactly, one by one. They are random letters and "
          "digits, not words. Output only the characters, nothing else.")


class QwenVL:
    def __init__(self, model: str = MODEL, device: str = "cuda"):
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model, torch_dtype=torch.bfloat16, device_map=device).eval()
        self.proc = AutoProcessor.from_pretrained(model)
        self.proc.tokenizer.padding_side = "left"

    @torch.no_grad()
    def read(self, imgs: list[np.ndarray], batch: int = 32, max_new_tokens: int = 24) -> list[str]:
        out = []
        msg = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
        text = self.proc.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        for i in range(0, len(imgs), batch):
            ims = [Image.fromarray(im).convert("RGB") for im in imgs[i:i + batch]]
            enc = self.proc(text=[text] * len(ims), images=ims, return_tensors="pt", padding=True).to(self.model.device)
            gen = self.model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False)
            new = gen[:, enc["input_ids"].shape[1]:]
            for s in self.proc.batch_decode(new, skip_special_tokens=True):
                out.append("".join(s.split()).upper())
        return out
