"""Benchmark results for the README tables and numbers: nine conditions plus the three real-world ones."""
import pandas as pd

def load_bench(path="out/report/readme_bench.csv"):
    """The nine README conditions plus the three real-world ones (thermal, 24-pin letter-quality dot-matrix, phone photo
    straightened as a phone app would), all read by the same four engines (James, 2026-10-21: "shouldn't the new
    deformations go into those tables?")."""
    import os
    d = pd.read_csv(path)
    if os.path.exists("out/report/readme_bench_extra.csv"):
        x = pd.read_csv("out/report/readme_bench_extra.csv")
        x = x[x.condition.isin(["thermal", "dot-matrix lq", "phone photo"])].replace({"condition": {"dot-matrix lq": "dot-matrix"}})
        d = pd.concat([d, x], ignore_index=True)
    return d
