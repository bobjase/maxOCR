"""Section 6.5 cluster derivation (R22/R22b) and R27b reliability curve, on evaluate.run rows."""
import json

import numpy as np
import pandas as pd
from scipy.stats import binom

from .corpus import PRIMARY_ALPHABET

ALPHA = 0.01


def substitution_counts(chars: pd.DataFrame) -> pd.DataFrame:
    """Directed counts truth -> pred over aligned positions; deletions excluded from edges."""
    n = chars.groupby("truth").size().rename("n")
    subs = chars[(chars.pred != chars.truth) & (chars.pred != "")]
    k = subs.groupby(["truth", "pred"]).size().rename("k").reset_index()
    errs = chars[chars.pred != chars.truth].groupby("truth").size().rename("errors")
    k = k.join(n, on="truth").join(errs, on="truth")
    k["rate"] = k.k / k.n
    return k


def significant_edges(counts: pd.DataFrame, alphabet: str = PRIMARY_ALPHABET, alpha: float = ALPHA) -> pd.DataFrame:
    """R22b null: source c's substitutions spread uniformly over the other len(alphabet)-1 classes.
    One-sided binomial test per directed pair, Bonferroni over all directed pairs."""
    m = len(alphabet) * (len(alphabet) - 1)
    p0 = counts.errors / counts.n / (len(alphabet) - 1)
    counts = counts.assign(p_value=binom.sf(counts.k - 1, counts.n, p0))
    return counts[counts.p_value < alpha / m].sort_values("rate", ascending=False)


def components(edges: pd.DataFrame) -> list[list[str]]:
    """Connected components (ignoring direction) with at least two members."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in zip(edges.truth, edges.pred):
        parent[find(a)] = find(b)
    groups = {}
    for x in parent:
        groups.setdefault(find(x), []).append(x)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: (-len(g), g))


def stability(edges: pd.DataFrame) -> dict:
    """R22b: components when the inclusion floor is moved 2x either way around the weakest edge."""
    if edges.empty:
        return {}
    floor = edges.rate.min()
    return {f"{f}x": components(edges[edges.rate >= floor * f]) for f in (0.5, 2.0)} | {
        "baseline": components(edges)}


def within_cluster_rate(chars: pd.DataFrame, clusters: list[list[str]]) -> float:
    """R25: substitutions into another member of the same cluster / cluster-member occurrences."""
    member = {c: i for i, g in enumerate(clusters) for c in g}
    m = chars[chars.truth.isin(member)]
    if m.empty:
        return float("nan")
    hit = m.pred.map(member).eq(m.truth.map(member)) & (m.pred != m.truth)
    return float(hit.mean())


def paddle_margin(chars: pd.DataFrame, classes: list[str], clusters: list[list[str]]) -> pd.Series:
    """R27: log-odds of gt vs strongest in-cluster competitor, from the R11a posterior."""
    idx = {c: i for i, c in enumerate(classes)}
    rivals = {c: [idx[o] for o in g if o != c] for g in clusters for c in g}
    out = np.full(len(chars), np.nan)
    for r, (gt, raw) in enumerate(zip(chars.truth, chars.probs)):
        if gt not in rivals or not raw:
            continue
        p = np.frombuffer(raw, dtype=np.float16).astype(np.float64)
        eps = 1e-9
        out[r] = np.log(p[idx[gt]] + eps) - np.log(p[rivals[gt]].max() + eps)
    return pd.Series(out, index=chars.index)


def reliability_curve(margin: pd.Series, err: pd.Series, bins: int = 20) -> pd.DataFrame:
    """R27b: realized error vs margin, equal-count bins."""
    d = pd.DataFrame({"m": margin, "err": err}).dropna()
    d["bin"] = pd.qcut(d.m, bins, duplicates="drop")
    return d.groupby("bin", observed=True).agg(margin=("m", "median"), error=("err", "mean"), n=("err", "size"))


def cluster_report(chars: pd.DataFrame, engine: str, suite: str = "a") -> dict:
    sub = chars[(chars.engine == engine) & (chars.suite == suite)]
    edges = significant_edges(substitution_counts(sub))
    return {"engine": engine, "suite": suite,
            "edges": edges[["truth", "pred", "k", "n", "rate", "p_value"]].to_dict("records"),
            "clusters": components(edges), "stability": stability(edges)}


def union_table(paddle_edges: pd.DataFrame, tess_edges: pd.DataFrame) -> pd.DataFrame:
    """R22a published table: union of edges, marked shared / paddle-only / tesseract-only."""
    p = set(zip(paddle_edges.truth, paddle_edges.pred))
    t = set(zip(tess_edges.truth, tess_edges.pred))
    rows = [{"truth": a, "pred": b, "source": "shared" if (a, b) in p & t else ("paddle" if (a, b) in p else "tesseract")}
            for a, b in sorted(p | t)]
    return pd.DataFrame(rows)


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

