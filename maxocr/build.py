"""Candidate font builds: Iosevka subset plans with variant overrides, parallel worker copies (R33c).

A candidate is identified by the hash of its overrides and weight; builds are cached on disk.
Worker copies live in ~/maxocr-work/iosevka-w<i> (see scripts/timing.py: only node_modules is shared).
"""
import hashlib
import json
import queue
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path.home() / "maxocr-work"
BASE = WORK / "iosevka"
PLAN = (ROOT / "iosevka" / "private-build-plans.toml").read_text()
WEIGHT_KEY = "[buildPlans.MaxOCRCand.weights.Regular]\nshape = 400"


def cand_id(overrides: dict[str, str], weight: int = 400, metric: dict | None = None) -> str:
    """Stable id. `metric` (metricOverride) is only hashed when given, so the ids of
    variant-only candidates do not change."""
    d = {"v": dict(sorted(overrides.items())), "w": weight}
    if metric:
        d["m"] = dict(sorted(metric.items()))
    return hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:12]


def plan_text(overrides: dict[str, str], weight: int = 400, metric: dict | None = None) -> str:
    assert WEIGHT_KEY in PLAN, "build plan layout changed; update maxocr.build"
    text = PLAN.replace(WEIGHT_KEY, WEIGHT_KEY.replace("400", str(weight)))
    if overrides:
        text += "\n[buildPlans.MaxOCRCand.variants.design]\n" + "".join(
            f'{k} = "{v}"\n' for k, v in sorted(overrides.items()))
    if metric:
        text += "\n[buildPlans.MaxOCRCand.metricOverride]\n" + "".join(
            f"{k} = {v}\n" for k, v in sorted(metric.items()))
    return text


def working_copy(i: int) -> Path:
    w = WORK / f"iosevka-w{i}"
    if not w.exists():
        w.mkdir()
        for entry in BASE.iterdir():
            if entry.name in (".build", "dist", "private-build-plans.toml"):
                continue
            flag = "-al" if entry.name == "node_modules" else "-a"
            subprocess.run(["cp", flag, str(entry), str(w / entry.name)], check=True)
        for lib in w.glob("packages/*/lib"):
            shutil.rmtree(lib)
    return w


class BuildPool:
    def __init__(self, n_workers: int, out_dir: Path):
        self.out = out_dir
        self.out.mkdir(parents=True, exist_ok=True)
        self.free: queue.Queue = queue.Queue()
        for i in range(n_workers):
            self.free.put(working_copy(i))
        self.n = n_workers

    def path(self, overrides: dict[str, str], weight: int = 400, metric: dict | None = None) -> Path:
        return self.out / f"{cand_id(overrides, weight, metric)}.ttf"

    def _build(self, overrides: dict[str, str], weight: int, metric: dict | None = None) -> tuple[Path, str | None]:
        out = self.path(overrides, weight, metric)
        if out.exists():
            return out, None
        w = self.free.get()
        try:
            plan = w / "private-build-plans.toml"
            plan.unlink(missing_ok=True)
            plan.write_text(plan_text(overrides, weight, metric))
            r = subprocess.run(["npm", "run", "build", "--", "ttf-unhinted::MaxOCRCand"], cwd=w,
                               capture_output=True, text=True)
            if r.returncode != 0:
                return out, (r.stdout[-1500:] + r.stderr[-1500:])
            tmp = out.with_suffix(".tmp")
            shutil.copy(w / "dist" / "MaxOCRCand" / "TTF-Unhinted" / "MaxOCRCand-Regular.ttf", tmp)
            tmp.rename(out)   # atomic: a cached file is always complete
            return out, None
        finally:
            self.free.put(w)

    def build_many(self, specs: list[tuple]) -> list[tuple[Path, str | None]]:
        """specs: (overrides, weight) or (overrides, weight, metric)."""
        with ThreadPoolExecutor(self.n) as ex:
            return list(ex.map(lambda s: self._build(*s), specs))
