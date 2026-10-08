"""Evaluate all baseline fonts on one bank at one severity.

    python scripts/sweep.py --severity 1.0                      # M1a sweep bank (2,000 lines)
    python scripts/sweep.py --bank validation --severity 0.5    # R7 frozen validation bank (5,000)

Writes out/<bank>/sev_<s>_chars.parquet and _strings.parquet, timing, and the bank's hash,
then prints a per-font character error table. A bank's instances do not depend on severity (CRN).
"""
import hashlib
import argparse
import json
import time
from pathlib import Path

from maxocr.corpus import make_strings
from maxocr.degrade import make_instance
from maxocr.evaluate import Job, chunk, run
from maxocr.fonts import BASELINES

BANKS = {"sweep": (101, 2000), "validation": (202, 5000)}  # name: (seed, size)
OUT_ROOT = Path(__file__).resolve().parents[1] / "out"


def bank_hash(insts) -> str:
    """Hash of the full instance list; recorded so a frozen bank is verifiable (R7)."""
    payload = json.dumps([[i.index, i.text, i.u, i.seed] for i in insts]).encode()
    return hashlib.sha256(payload).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--severity", type=float, required=True)
    ap.add_argument("--bank", choices=BANKS, default="sweep")
    ap.add_argument("--clean", action="store_true", help="R7a clean renders (severity ignored)")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()

    seed, size = BANKS[a.bank]
    insts = [make_instance(i, s, seed) for i, s in enumerate(make_strings(size, seed))]
    jobs = [Job(name, str(path), a.severity, suite, c, clean=a.clean)
            for name, path in BASELINES.items() for suite in "ab" for c in chunk(insts, 50)]
    n_img = sum(len(j.instances) for j in jobs)
    print(f"{a.bank} bank, {'clean' if a.clean else f'severity {a.severity}'}: {n_img} images", flush=True)

    st = {}
    t = time.perf_counter()
    chars, strings, classes = run(jobs, a.workers, progress=False, stats=st)
    wall = time.perf_counter() - t

    OUT = OUT_ROOT / a.bank
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bank.json").write_text(json.dumps({"seed": seed, "size": size, "sha256": bank_hash(insts)}))
    tag = "clean" if a.clean else f"sev_{a.severity:.2f}"
    chars.to_parquet(OUT / f"{tag}_chars.parquet")
    strings.to_parquet(OUT / f"{tag}_strings.parquet")
    (OUT / "classes.json").write_text(json.dumps(classes))
    (OUT / f"{tag}_timing.json").write_text(json.dumps({**st, "images": n_img}))

    chars["err"] = chars.pred != chars.truth
    table = chars.groupby(["engine", "suite", "font"]).err.mean().unstack("font").mul(100).round(2)
    print(f"done in {wall:.0f}s ({n_img / wall:.0f} img/s). Character error %:")
    print(table.to_string())


if __name__ == "__main__":
    main()
