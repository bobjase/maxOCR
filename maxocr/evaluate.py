"""Run fonts x severities x suites x bank instances through PaddleOCR and Tesseract.

Output: one row per ground-truth character per engine (R46 granularity), plus one row per string.
Workers render, degrade and run Tesseract (CPU); the parent runs PaddleOCR (GPU).
"""
import os
import time
from dataclasses import dataclass
from multiprocessing import get_context

import numpy as np
import pandas as pd

from .align import align
from .degrade import Instance, clean, degrade

_tess = None

# One thread per worker: parallelism comes from the pool. These must be in the environment
# before a worker starts, because OpenMP (loaded by numpy at import, before any initializer
# runs) reads its limit once at load. Setting them inside the worker left 24 threads each.
# Tesseract's LSTM asks for exactly 4 OpenMP threads; Intel's OpenMP (pulled in with PyTorch)
# warns on every call when the limit caps that at 1, so its warnings are silenced.
SINGLE_THREAD_ENV = {"OMP_NUM_THREADS": "1", "OMP_THREAD_LIMIT": "1", "KMP_WARNINGS": "0",
                     "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


@dataclass(frozen=True)
class Job:
    font: str
    font_path: str
    severity: float
    suite: str            # "a" = pre-binarized, "b" = grayscale (R10)
    instances: tuple[Instance, ...]
    size_pt: float = 8.0
    dpi: int = 200
    clean: bool = False   # R7a: ignore severity and instance draws, render undegraded


def _worker_init():
    global _tess
    import cv2
    cv2.setNumThreads(1)
    from .engines.tesseract import Tesseract
    _tess = Tesseract()


def _run_job(job: Job):
    t = {"degrade": 0.0, "tesseract": 0.0}
    out = []
    for inst in job.instances:
        t0 = time.perf_counter()
        if job.clean:
            img = clean(job.font_path, inst.text, job.size_pt, job.dpi, binarize=job.suite == "a")
        else:
            img = degrade(job.font_path, inst, job.severity, job.size_pt, job.dpi, binarize=job.suite == "a")
        t1 = time.perf_counter()
        syms = _tess.read(img)
        t["degrade"] += t1 - t0
        t["tesseract"] += time.perf_counter() - t1
        out.append((inst, img, [(s.text, s.alternatives) for s in syms]))
    return job, out, t


def _tess_rank(gt: str, alts: list[tuple[str, float]]) -> tuple[int, int]:
    """R12b: 1-based rank of gt among confidence-sorted alternatives; K+1 if absent."""
    names = [a for a, _ in alts]
    return (names.index(gt) + 1 if gt in names else len(names) + 1), len(names)


def run(jobs: list[Job], n_workers: int, paddle=None, progress=True, stats: dict | None = None):
    """stats, if given, is filled with seconds: worker degrade/tesseract (summed over workers),
    main wait (blocked on workers), main paddle, main bookkeeping, and wall."""
    if paddle is None:
        from .engines.paddle import PaddleRec
        paddle = PaddleRec()
    cls_index = {c: i for i, c in enumerate(paddle.classes)}
    char_rows, string_rows = [], []
    st = {"degrade": 0.0, "tesseract": 0.0, "wait": 0.0, "paddle": 0.0, "main_other": 0.0}
    t_start = time.perf_counter()
    os.environ.update(SINGLE_THREAD_ENV)  # inherited by the spawned workers
    ctx = get_context("spawn")
    with ctx.Pool(n_workers, initializer=_worker_init) as pool:
        it = pool.imap_unordered(_run_job, jobs)
        for k in range(len(jobs)):
            t0 = time.perf_counter()
            job, results, wt = next(it)
            t1 = time.perf_counter()
            st["wait"] += t1 - t0
            st["degrade"] += wt["degrade"]
            st["tesseract"] += wt["tesseract"]
            t_paddle = 0.0
            key = dict(font=job.font, severity=job.severity, suite=job.suite)
            for inst, img, tsyms in results:
                gt = inst.text
                tp = time.perf_counter()
                pchars = paddle.read(img)
                t_paddle += time.perf_counter() - tp
                for engine, pred in (("paddle", "".join(c.text for c in pchars)),
                                     ("tesseract", "".join(t for t, _ in tsyms))):
                    method, mapping, n_ins = align(gt, pred)
                    string_rows.append({**key, "engine": engine, "inst": inst.index, "truth": gt, "pred": pred,
                                        "length": len(gt), "cropped": inst.cropped,
                                        "method": method, "n_ins": n_ins})
                    for i, j in enumerate(mapping):
                        row = {**key, "engine": engine, "inst": inst.index, "pos": i, "truth": gt[i],
                               "pred": pred[j] if j is not None else "", "length": len(gt),
                               "cropped": inst.cropped}
                        if engine == "paddle":
                            probs = pchars[j].probs if j is not None else None
                            row["p_gt"] = float(probs[cls_index[gt[i]]]) if probs is not None else np.nan
                            row["probs"] = probs.astype(np.float16).tobytes() if probs is not None else b""
                        else:
                            rank, K = _tess_rank(gt[i], tsyms[j][1]) if j is not None else (-1, 0)
                            row["rank"], row["K"] = rank, K
                            row["alts"] = "".join(a for a, _ in tsyms[j][1]) if j is not None else ""
                        char_rows.append(row)
            st["paddle"] += t_paddle
            st["main_other"] += time.perf_counter() - t1 - t_paddle
            if progress and (k + 1) % max(1, len(jobs) // 20) == 0:
                print(f"  {k + 1}/{len(jobs)} jobs", flush=True)
    st["wall"] = time.perf_counter() - t_start
    if stats is not None:
        stats.update(st)
    return pd.DataFrame(char_rows), pd.DataFrame(string_rows), paddle.classes


def chunk(instances: list[Instance], size: int) -> list[tuple[Instance, ...]]:
    return [tuple(instances[i:i + size]) for i in range(0, len(instances), size)]
