"""R13: PARSeq base, held-out engine. Pinned repository commit; non-autoregressive decode, no refinement.

Never used to select or optimize anything; evaluation only. Output restricted to the corpus alphabet
(plus end-of-sequence), mirroring the other engines. Each image is resized to the model's 32x128 input
independently, so batching does not change results.
"""
import numpy as np
import torch
from PIL import Image

from ..corpus import PRIMARY_ALPHABET

REPO = "baudm/parseq:1902db043c029a7e03a3818c616c06600af574be"


class Parseq:
    def __init__(self, alphabet: str = PRIMARY_ALPHABET, device: str = "cuda"):
        self.model = torch.hub.load(REPO, "parseq", pretrained=True, decode_ar=False, refine_iters=0,
                                    trust_repo=True).eval().to(device)
        self.device = device
        tok = self.model.tokenizer
        self.itos = tok._itos
        self.eos = tok.eos_id
        allowed = [self.eos] + [tok._stoi[c] for c in alphabet if c in tok._stoi]
        # The head predicts EOS + charset only; BOS and PAD (last two tokenizer entries) are never output.
        n_out = len(self.itos) - 2
        self.mask = torch.full((n_out,), float("-inf"), device=device)
        self.mask[allowed] = 0.0
        h, w = self.model.hparams.img_size

        def prep(img: np.ndarray) -> torch.Tensor:
            im = Image.fromarray(img).convert("RGB").resize((w, h), Image.BICUBIC)
            t = torch.from_numpy(np.asarray(im, dtype=np.float32) / 255.0).permute(2, 0, 1)
            return (t - 0.5) / 0.5
        self.prep = prep

    @torch.no_grad()
    def read(self, imgs: list[np.ndarray], batch: int = 256) -> list[str]:
        out = []
        for i in range(0, len(imgs), batch):
            x = torch.stack([self.prep(im) for im in imgs[i:i + batch]]).to(self.device)
            logits = self.model(x) + self.mask
            ids = logits.argmax(-1).cpu().numpy()
            for row in ids:
                s = []
                for t in row:
                    if t == self.eos:
                        break
                    s.append(self.itos[t])
                out.append("".join(s))
        return out
