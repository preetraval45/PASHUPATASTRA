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


def test_answer_only_loss_ignores_the_question():
    """SFT masks the prompt: changing only question tokens' targets must not
    change the loss."""
    torch.manual_seed(0)
    model = Kushmanda(TINY).eval()
    x = torch.randint(0, 50, (1, 12))
    y = torch.randint(0, 50, (1, 12))
    mask = torch.zeros(1, 12, dtype=torch.long)
    mask[0, 8:] = 1
    y2 = y.clone()
    y2[0, :8] = (y2[0, :8] + 3) % 50
    _, a = model(x, y, mask)
    _, b = model(x, y2, mask)
    assert torch.allclose(a, b)


def test_rotary_positions_make_attention_relative():
    from sati.lm.model import rope_tables, rotate

    cos, sin = rope_tables(8, 32, 10000.0)
    q, k = torch.randn(8), torch.randn(8)
    dot = lambda i, j: (rotate(q, cos[i], sin[i]) * rotate(k, cos[j], sin[j])).sum()  # noqa: E731
    assert torch.allclose(dot(3, 1), dot(12, 10), atol=1e-5)
