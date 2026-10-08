import pandas as pd

from maxocr.analysis import components, significant_edges, substitution_counts, within_cluster_rate


def rows(pairs):
    """pairs: list of (truth, pred, count)."""
    return pd.DataFrame([{"truth": t, "pred": p} for t, p, n in pairs for _ in range(n)])


def test_components_ignore_direction_and_singletons():
    e = pd.DataFrame({"truth": ["0", "O", "8"], "pred": ["O", "D", "B"]})
    assert components(e) == [["0", "D", "O"], ["8", "B"]]


def test_share_floor_drops_weak_chaining_edge():
    # 0 is mostly misread as O; a small but consistent 0->8 tail would chain {0,O} to {8,B}.
    chars = rows([("0", "0", 9000), ("0", "O", 900), ("0", "8", 100),
                  ("8", "8", 9000), ("8", "B", 1000), ("O", "O", 10000), ("B", "B", 10000)])
    counts = substitution_counts(chars)
    assert components(significant_edges(counts)) == [["0", "8", "B", "O"]]
    assert components(significant_edges(counts, min_share=0.25)) == [["0", "O"], ["8", "B"]]


def test_within_cluster_rate_counts_only_in_cluster_substitutions():
    chars = rows([("0", "0", 8), ("0", "O", 1), ("0", "8", 1)])
    assert within_cluster_rate(chars, [["0", "O"]]) == 0.1
