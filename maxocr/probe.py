"""R40b probe classifier: an achievable-error estimate for a font at a severity.

A small CNN is trained on degraded renders from the degradation model itself and tested on
held-out renders. It is a measurement instrument only: never shown candidates, never used to
score them. Its estimate is optimistic (it trains on the exact test distribution).

Each sample is a 3-character string; the label is the middle character and the input is the
middle glyph cell (with neighbour bleed). Cropped-stratum instances are excluded.
"""
from multiprocessing import get_context

import cv2
import numpy as np

from .corpus import PRIMARY_ALPHABET
from .degrade import clean, degrade, make_instance, params

CELL = 32
MARGIN = 0.25  # of an advance, each side of the middle cell


def _advance_px(font: str, size_pt: float, dpi: int) -> float:
    from fontTools.ttLib import TTFont
    f = TTFont(font)
    adv = f["hmtx"][f.getBestCmap()[ord("0")]][0]
    return adv * size_pt * dpi / 72 / f["head"].unitsPerEm


def _cell(img: np.ndarray, adv: float) -> np.ndarray:
    # Render layout: 6 px degrade pad + 4 px render PAD, glyph 1 starts at round(adv).
    x0 = 10 + int(round(adv))
    lo, hi = int(x0 - MARGIN * adv), int(np.ceil(x0 + adv + MARGIN * adv))
    crop = img[:, max(lo, 0):min(hi, img.shape[1])]
    return cv2.resize(crop, (CELL, CELL), interpolation=cv2.INTER_AREA)


def _make(args):
    font, severity, start, n, seed, binarize = args
    cv2.setNumThreads(1)
    rng = np.random.default_rng([seed, start])
    adv = _advance_px(font, 8.0, 200)
    xs, ys = [], []
    i = start
    while len(ys) < n:
        label = int(rng.integers(len(PRIMARY_ALPHABET)))
        text = "".join(rng.choice(list(PRIMARY_ALPHABET), 1)) + PRIMARY_ALPHABET[label] + \
            "".join(rng.choice(list(PRIMARY_ALPHABET), 1))
        inst = make_instance(i, text, seed)
        i += 1
        if severity is None:
            img = clean(font, text, binarize=binarize)
        else:
            if params(inst, severity)["crop"]:
                continue
            img = degrade(font, inst, severity, binarize=binarize)
        xs.append(_cell(img, adv))
        ys.append(label)
    return np.stack(xs), np.array(ys)


def make_dataset(font: str, severity: float | None, n: int, seed: int, binarize: bool = True,
                 workers: int = 16) -> tuple[np.ndarray, np.ndarray]:
    """severity=None means the R7a clean condition."""
    per = int(np.ceil(n / workers))
    tasks = [(font, severity, k * 10_000_000, per, seed, binarize) for k in range(workers)]
    with get_context("spawn").Pool(workers) as pool:
        parts = pool.map(_make, tasks)
    return np.concatenate([p[0] for p in parts])[:n], np.concatenate([p[1] for p in parts])[:n]


def train_and_eval(xtr, ytr, xte, yte, epochs: int = 12, seed: int = 0) -> tuple[np.ndarray, float]:
    """Returns (predicted test labels, error on a 5,000-sample slice of the training set).
    A training error well above zero means the run diverged (seen occasionally)."""
    import torch
    from torch import nn

    torch.manual_seed(seed)
    dev = "cuda"
    net = nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
        nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Dropout(0.3), nn.Linear(128 * 8 * 8, 256), nn.ReLU(),
        nn.Linear(256, len(PRIMARY_ALPHABET)),
    ).to(dev)

    def tensor(x):
        return torch.tensor(1.0 - x[:, None].astype(np.float32) / 255.0, device=dev)

    Xtr, Ytr = tensor(xtr), torch.tensor(ytr, device=dev)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=epochs * int(np.ceil(len(Xtr) / 256)))
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr), device=dev)
        for b in range(0, len(Xtr), 256):
            idx = perm[b:b + 256]
            opt.zero_grad()
            loss_fn(net(Xtr[idx]), Ytr[idx]).backward()
            opt.step()
            sched.step()
    net.eval()

    def predict(X):
        with torch.no_grad():
            return torch.cat([net(X[b:b + 1024]).argmax(1) for b in range(0, len(X), 1024)]).cpu().numpy()

    train_err = float((predict(Xtr[:5000]) != ytr[:5000]).mean())
    return predict(tensor(xte)), train_err


def best_of_seeds(xtr, ytr, xte, yte, seeds=(0, 1, 2)) -> tuple[np.ndarray, list[dict]]:
    """Train several seeds; keep the one with the lowest TRAINING error (never selects on test)."""
    runs = []
    for sd in seeds:
        pred, tr = train_and_eval(xtr, ytr, xte, yte, seed=sd)
        runs.append({"seed": sd, "train_err_pct": round(100 * tr, 3),
                     "test_err_pct": round(100 * float((pred != yte).mean()), 3),
                     "diverged": tr > 0.01, "_pred": pred})
    best = min(runs, key=lambda r: r["train_err_pct"])
    return best["_pred"], [{k: v for k, v in r.items() if k != "_pred"} for r in runs]
