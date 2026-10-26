"""The numpy Kushmanda engine matches PyTorch: exactly unquantised, closely int8-quantised."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from sati.lm.infer import Engine, export  # noqa: E402
from sati.lm.model import Config, Kushmanda  # noqa: E402


@pytest.fixture(scope="module")
def model():
    torch.manual_seed(0)
    cfg = Config(vocab_size=97, context=32, layers=2, heads=2, width=16)
    m = Kushmanda(cfg).eval()
    return m, cfg


def _engine(model, tmp_path, quantise):
    m, cfg = model
    export({k: v.detach().cpu() for k, v in m.state_dict().items()}, cfg.__dict__, tmp_path, quantise=quantise)
    return Engine.load(tmp_path)


def test_unquantised_logits_match_pytorch(model, tmp_path):
    m, _ = model
    ids = [3, 14, 15, 92, 65, 35, 8]
    with torch.no_grad():
        expected = m(torch.tensor([ids]))[0][0].numpy()
    got = _engine(model, tmp_path, quantise=False).logits(ids)
    assert np.allclose(got, expected, atol=1e-4)


def test_cached_decoding_equals_recomputing_the_whole_sequence(model, tmp_path):
    engine = _engine(model, tmp_path, quantise=False)
    ids = [5, 6, 7, 8]
    cache = [None] * 2
    engine.logits(ids, 0, cache)
    stepped = engine.logits([9], len(ids), cache)[-1]
    full = engine.logits([*ids, 9])[-1]
    assert np.allclose(stepped, full, atol=1e-5)


def test_greedy_generation_matches_pytorch(model, tmp_path):
    m, _ = model
    prompt = [1, 2, 3]
    with torch.no_grad():
        expected = m.generate(torch.tensor([prompt]), 8, temperature=0)[0, len(prompt):].tolist()
    assert _engine(model, tmp_path, quantise=False).generate(prompt, 8) == expected


def test_int8_weights_stay_close(model, tmp_path):
    m, _ = model
    ids = [10, 20, 30, 40]
    with torch.no_grad():
        expected = m(torch.tensor([ids]))[0][0].numpy()
    got = _engine(model, tmp_path, quantise=True).logits(ids)
    assert np.corrcoef(got.ravel(), expected.ravel())[0, 1] > 0.99
