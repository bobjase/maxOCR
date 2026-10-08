"""R37/R37b timing sheet: one synthetic generation under different build/Tesseract worker splits.

A generation = 32 candidate builds (Iosevka subset plan, weight shape 380..411 so every build is a
real rebuild of every glyph) evaluated on a 500-line optimization bank, suite (a): PaddleOCR on all
images (parent process, GPU) and the Tesseract gate on all 32 candidates (worst case). Builds run
in B threads, each in its own Iosevka working copy (R33c); evaluation runs in a pool of T Tesseract
workers that starts on each candidate as soon as it is built, so the two compete for cores as they
would in the real loop.

    python scripts/timing.py [--splits 4x16 8x12 12x8 16x4] [--pop 32] [--bank 500]
Writes out/report/timing.json. Run inside the pixi env from WSL.
"""
import argparse
import json
import os
import queue
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from maxocr.corpus import make_strings
from maxocr.degrade import make_instance
from maxocr.evaluate import SINGLE_THREAD_ENV, Job, _run_job, _worker_init, chunk

ROOT = Path(__file__).resolve().parents[1]
WORK = Path.home() / "maxocr-work"
BASE = WORK / "iosevka"
OPT_BANK_SEED = 909
PLAN_TEMPLATE = (ROOT / "iosevka" / "private-build-plans.toml").read_text()


def working_copy(i: int) -> Path:
    """Per-worker Iosevka checkout (R33c). Only node_modules is hard-linked: a build compiles the
    glyph code into packages/*/lib, so sharing anything else by hard link lets parallel builds
    overwrite each other's files (seen: corrupted latin.mjs)."""
    w = WORK / f"iosevka-w{i}"
    if not w.exists():
        w.mkdir()
        for entry in BASE.iterdir():
            if entry.name in (".build", "dist", "private-build-plans.toml"):
                continue
            flag = "-al" if entry.name == "node_modules" else "-a"
            subprocess.run(["cp", flag, str(entry), str(w / entry.name)], check=True)
        for lib in w.glob("packages/*/lib"):
            shutil.rmtree(lib)  # compiled per copy
    return w


def plan_for(weight: int) -> str:
    key = "[buildPlans.MaxOCRCand.weights.Regular]\nshape = 400"
    assert key in PLAN_TEMPLATE, "build plan layout changed; update timing.plan_for"
    return PLAN_TEMPLATE.replace(key, f"[buildPlans.MaxOCRCand.weights.Regular]\nshape = {weight}")


def build(w: Path, weight: int, out: Path) -> float:
    t = time.perf_counter()
    plan = w / "private-build-plans.toml"
    plan.unlink(missing_ok=True)          # never write through a hard link
    plan.write_text(plan_for(weight))
    r = subprocess.run(["npm", "run", "build", "--", "ttf-unhinted::MaxOCRCand"], cwd=w,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stdout[-2000:] + r.stderr[-2000:])
    shutil.copy(w / "dist" / "MaxOCRCand" / "TTF-Unhinted" / "MaxOCRCand-Regular.ttf", out)
    return time.perf_counter() - t


def generation(n_build: int, n_tess: int, pop: int, insts, paddle, copies, outdir: Path) -> dict:
    os.environ.update(SINGLE_THREAD_ENV)
    done_q: queue.Queue = queue.Queue()
    build_times = []
    free = queue.Queue()
    for w in copies[:n_build]:
        free.put(w)

    errors = []

    def build_one(k):
        w = free.get()
        try:
            out = outdir / f"cand_{n_build}x{n_tess}_{k}.ttf"
            build_times.append(build(w, 380 + k, out))
            done_q.put(out)
        except Exception as e:  # report instead of hanging the generation loop
            errors.append(f"candidate {k}: {e}")
            done_q.put(None)
        finally:
            free.put(w)

    t0 = time.perf_counter()
    paddle_s, n_img = 0.0, 0
    with get_context("spawn").Pool(n_tess, initializer=_worker_init) as pool, \
            ThreadPoolExecutor(n_build) as builders:
        for k in range(pop):
            builders.submit(build_one, k)
        pending, built = [], 0
        while built < pop or pending:
            try:
                font = done_q.get(timeout=0.05)
                built += 1
                if font is None:
                    continue
                pending += [pool.apply_async(_run_job, (Job(font.stem, str(font), 0.5, "a", c),))
                            for c in chunk(insts, 50)]
            except queue.Empty:
                pass
            still = []
            for r in pending:
                if r.ready():
                    _, results, _ = r.get()
                    for _, img, _ in results:
                        t = time.perf_counter()
                        paddle.read(img)
                        paddle_s += time.perf_counter() - t
                        n_img += 1
                else:
                    still.append(r)
            pending = still
    wall = time.perf_counter() - t0
    if errors:
        raise RuntimeError("builds failed:\n" + "\n".join(errors[:3]))
    return {"build_workers": n_build, "tesseract_workers": n_tess, "wall_s": round(wall, 1),
            "builds": len(build_times), "build_s_mean": round(sum(build_times) / len(build_times), 2),
            "images": n_img, "paddle_s": round(paddle_s, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", nargs="+", default=["4x16", "8x12", "12x8", "16x4"])
    ap.add_argument("--pop", type=int, default=32)
    ap.add_argument("--bank", type=int, default=500)
    a = ap.parse_args()
    splits = [tuple(int(x) for x in s.split("x")) for s in a.splits]

    from maxocr.engines.paddle import PaddleRec
    paddle = PaddleRec()
    insts = [make_instance(i, s, OPT_BANK_SEED) for i, s in enumerate(make_strings(a.bank, OPT_BANK_SEED))]
    outdir = WORK / "timing"
    outdir.mkdir(exist_ok=True)

    n_copies = max(b for b, _ in splits)
    t = time.perf_counter()
    copies = [working_copy(i) for i in range(n_copies)]
    print(f"{n_copies} working copies ready in {time.perf_counter() - t:.1f}s", flush=True)

    # One-time compile per copy (R37), measured separately from the generation.
    t = time.perf_counter()
    with ThreadPoolExecutor(n_copies) as ex:
        warm = list(ex.map(lambda w: build(w, 400, outdir / f"warm_{w.name}.ttf"), copies))
    print(f"warm-up: {n_copies} parallel first builds, wall {time.perf_counter() - t:.1f}s, "
          f"per build mean {sum(warm) / len(warm):.1f}s", flush=True)

    results = []
    for b, tw in splits:
        r = generation(b, tw, a.pop, insts, paddle, copies, outdir)
        print(json.dumps(r), flush=True)
        results.append(r)
    OUT = ROOT / "out" / "report"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timing.json").write_text(json.dumps({"pop": a.pop, "bank": a.bank, "results": results,
                                                 "warmup_build_mean_s": round(sum(warm) / len(warm), 2)}, indent=1))


if __name__ == "__main__":
    main()
