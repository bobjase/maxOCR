"""R17: align engine output to ground truth before attributing substitutions.

Equal lengths: positional (mono advance makes position i of the output the glyph at slot i).
Otherwise: Levenshtein alignment with backtrace; the method is recorded per string.
"""


def align(gt: str, out: str) -> tuple[str, list[int | None], int]:
    """Return (method, mapping, n_insertions); mapping[i] is the output index for gt[i] or None."""
    if len(gt) == len(out):
        return "positional", list(range(len(gt))), 0
    n, m = len(gt), len(out)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (gt[i - 1] != out[j - 1]))
    mapping: list[int | None] = [None] * n
    i, j, ins = n, m, 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (gt[i - 1] != out[j - 1]):
            mapping[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            i -= 1                      # deletion: gt[i-1] has no output
        else:
            j -= 1                      # insertion
            ins += 1
    return "edit", mapping, ins
