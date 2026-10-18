"""Kushmanda — the causal mask, learning, generation, and the corpus split.

Skipped where PyTorch is not installed; CI installs the CPU build for them.
"""

from __future__ import annotations

import pytest

from sati.lm.corpus import split

torch = pytest.importorskip("torch")

from sati.lm.model import Config, Kushmanda  # noqa: E402

TINY = Config(vocab_size=50, context=16, layers=2, heads=2, width=32, dropout=0.0)


def test_a_position_never_sees_the_future():
    torch.manual_seed(0)
    model = Kushmanda(TINY).eval()
    a = torch.randint(0, 50, (1, 16))
    b = a.clone()
    b[0, 10:] = (b[0, 10:] + 7) % 50  # change only the future
    la, _ = model(a)
    lb, _ = model(b)
    assert torch.allclose(la[0, :10], lb[0, :10], atol=1e-6)
    assert not torch.allclose(la[0, 10:], lb[0, 10:])


def test_it_learns_a_repeating_sequence():
    torch.manual_seed(0)
    model = Kushmanda(TINY)
    seq = torch.arange(17).remainder(5)[None]
    opt = torch.optim.AdamW(model.parameters(), lr=1e-2)
    first = None
    for _ in range(60):
        _, loss = model(seq[:, :-1], seq[:, 1:])
        first = first if first is not None else loss.item()
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert loss.item() < first / 5


def test_generation_extends_the_prompt():
    model = Kushmanda(TINY)
    out = model.generate(torch.zeros(1, 3, dtype=torch.long), new_tokens=5)
    assert out.shape == (1, 8)


def test_the_held_out_split_is_by_document_and_stable():
    docs = [{"source": "s", "id": str(i), "text": "x"} for i in range(2000)]
    train, test = split(docs)
    assert not {d["id"] for d in train} & {d["id"] for d in test}
    assert 50 <= len(test) <= 150
    assert split(docs)[1] == test
