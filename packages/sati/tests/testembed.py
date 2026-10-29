"""Brahmacharini v0 — the split, scoring, BM25 and the encoder."""

from __future__ import annotations

import numpy as np
import pytest

from sati.embed.data import Procedure, clean, split_by_source
from sati.embed.metrics import bm25, ranks, summarise


def test_links_and_citations_are_stripped():
    text = "[Shamoon](https://attack.mitre.org/software/S0140) wipes disks.(Citation: Unit 42)"
    assert clean(text) == "Shamoon wipes disks."


def test_a_source_never_appears_on_two_sides():
    procs = [Procedure(source=f"g{i % 300}", technique="t", text="x") for i in range(3000)]
    parts = split_by_source(procs)
    sources = [{p.source for p in part} for part in parts]
    assert not (sources[0] & sources[1]) and not (sources[0] & sources[2]) and not (sources[1] & sources[2])


def test_ranks_and_summary():
    scores = np.array([[0.1, 0.9, 0.5], [0.8, 0.1, 0.2]])
    r = ranks(scores, [1, 2])
    assert r == [1, 2]
    s = summarise(r)
    assert s["recall@1"] == 0.5 and s["mrr"] == 0.75


def test_bm25_ranks_the_matching_document_first():
    docs = ["phishing email with a malicious link", "disk wiping malware", "credential stuffing attack"]
    assert np.argmax(bm25(["malicious link in an email"], docs)[0]) == 0


def test_the_encoder_is_normalised_and_learns_a_pairing():
    torch = pytest.importorskip("torch")
    from sati.embed.model import Encoder, info_nce

    torch.manual_seed(0)
    enc = Encoder(dim=16, width=32)
    q = ["steals browser passwords", "encrypts files for ransom", "beacons over https"]
    k = ["credentials from web browsers", "data encrypted for impact", "web protocols c2"]
    assert torch.allclose(enc(q).norm(dim=-1), torch.ones(3), atol=1e-5)
    opt = torch.optim.Adam(enc.parameters(), lr=0.05)
    first = info_nce(enc(q), enc(k)).item()
    for _ in range(50):
        loss = info_nce(enc(q), enc(k))
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert loss.item() < first / 3


def test_fusion_weight_is_chosen_on_the_rows_given_and_unrankable_columns_go_last():
    from sati.embed.metrics import choose_weight, fuse, standardise

    a = np.array([[0.9, 0.1, 0.0], [0.0, 0.9, 0.1]])  # right on row 1 only
    b = np.array([[0.1, 0.9, -np.inf], [0.1, 0.9, -np.inf]])  # right on row 2 only
    gold = [0, 1]
    assert ranks(standardise(b), [2, 2]) == [3, 3]
    w = choose_weight(a, b, gold)
    assert summarise(ranks(fuse(a, b, w), gold))["mrr"] >= max(summarise(ranks(a, gold))["mrr"],
                                                               summarise(ranks(b, gold))["mrr"])


def test_pruning_keeps_the_largest_weights_per_row_at_int8():
    from sati.embed.metrics import prune, softmax

    coef = np.array([[0.1, -2.0, 0.5, 0.01], [3.0, 0.0, -0.2, 0.4]])
    p = prune(coef, 2)
    assert (p != 0).sum(axis=1).tolist() == [2, 2]
    assert p[0, 1] == pytest.approx(-2.0) and p[1, 0] == pytest.approx(3.0)
    assert abs(p[0, 2] - 0.5) < 2.0 / 127 and p[0, 0] == 0
    assert softmax(np.array([[1.0, 1.0]])).tolist() == [[0.5, 0.5]]
