"""R18-R20 primary-alphabet corpus: random strings, controlled length mix and doubles."""
import numpy as np

PRIMARY_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

P_LENGTH_1 = 0.20   # length-1 stratum gets enough samples per character (R20)
P_DOUBLE = 0.15     # strings of length >= 2 that contain a forced double such as "00" (R19)


def make_strings(n: int, seed: int, alphabet: str = PRIMARY_ALPHABET) -> list[str]:
    rng = np.random.default_rng(seed)
    a = np.array(list(alphabet))
    out = []
    for _ in range(n):
        length = 1 if rng.random() < P_LENGTH_1 else int(rng.integers(2, 13))
        chars = list(rng.choice(a, length))
        if length >= 2 and rng.random() < P_DOUBLE:
            i = int(rng.integers(0, length - 1))
            chars[i + 1] = chars[i]
        out.append("".join(chars))
    return out
