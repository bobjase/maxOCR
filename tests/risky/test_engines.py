"""M1a risky checks: engine behaviours the rest of the harness depends on."""
import random

import numpy as np
import pytest

from maxocr.degrade import placeholder_chain
from maxocr.corpus import PRIMARY_ALPHABET
from maxocr.engines.tesseract import Tesseract
from maxocr.render import render

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def degraded_lines(n=30, severity=1.0, seed=0):
    rng = random.Random(seed)
    for _ in range(n):
        s = "".join(rng.choice(PRIMARY_ALPHABET) for _ in range(8))
        yield s, placeholder_chain(render(FONT, s), severity)


def test_oem0_loads_with_legacy_tessdata():
    """R15b: legacy engine initialises from the vendored legacy traineddata and reads text."""
    t = Tesseract(legacy=True)
    assert len(t.text(render(FONT, "AB12CD34"))) == 8


def test_lstm_choice_mode_returns_alternatives_on_degraded_input():
    """R12b: lstm_choice_mode=2 yields ranked multi-class alternatives, not just the top-1."""
    t = Tesseract()
    syms = [s for _, img in degraded_lines() for s in t.read(img)]
    multi = [s for s in syms if len(s.alternatives) > 1]
    assert len(multi) / len(syms) > 0.5
    # Chosen symbol is (almost always) the top-confidence alternative.
    top_is_chosen = sum(s.alternatives[0][0] == s.text for s in multi)
    assert top_is_chosen / len(multi) > 0.98


@pytest.fixture(scope="module")
def paddle():
    from maxocr.engines.paddle import PaddleRec
    return PaddleRec()


def test_paddle_runs_on_gpu(paddle):
    assert paddle.sess.get_providers()[0] == "CUDAExecutionProvider"


def test_paddle_per_char_posterior(paddle):
    """R11a: each decoded char carries a normalized distribution whose argmax is that char."""
    for _, img in degraded_lines(n=10):
        for c in paddle.read(img):
            assert np.isclose(c.probs.sum(), 1.0, atol=1e-4)
            assert paddle.classes[int(c.probs.argmax())] == c.text


def test_paddle_doubles_not_collapsed_when_clean(paddle):
    for s in ("00", "1001", "8888"):
        assert paddle.text(render(FONT, s)) == s
