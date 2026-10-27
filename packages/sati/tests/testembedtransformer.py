"""Brahmacharini v1: the transformer encoder reads word order, pads safely, and learns."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from sati.embed.model import TransformerEncoder, info_nce, token_ids  # noqa: E402


def test_word_order_changes_the_embedding_but_padding_does_not():
    torch.manual_seed(0)
    enc = TransformerEncoder(width=32, layers=1, heads=2).eval()
    a, b = enc(["attacker deleted backups", "backups deleted attacker"])
    assert not torch.allclose(a, b, atol=1e-4)  # v0's bag would make these equal
    alone = enc(["short text"])[0]
    padded = enc(["short text", "a much longer text " * 10])[0]
    assert torch.allclose(alone, padded, atol=1e-5)


def test_ids_reserve_zero_for_padding():
    assert 0 not in token_ids("Some words here") and token_ids("") == [1]


def test_contrastive_training_lowers_the_loss():
    torch.manual_seed(0)
    enc = TransformerEncoder(width=32, layers=1, heads=2)
    opt = torch.optim.AdamW(enc.parameters(), lr=3e-3)
    q = ["dumped credentials from lsass", "encrypted files for ransom", "scanned open ports"]
    k = ["OS Credential Dumping", "Data Encrypted for Impact", "Network Service Discovery"]
    first = info_nce(enc(q), enc(k)).item()
    for _ in range(30):
        loss = info_nce(enc(q), enc(k))
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert loss.item() < first
