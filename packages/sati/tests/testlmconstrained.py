"""RP-44: constrained decoding only ever emits an identifier from the context, and cites its passage."""

from __future__ import annotations

import numpy as np

from sati.lm.constrained import constrained_id, identifiers
from sati.lm.sft import ABSTAIN

VOCAB = list("0123456789TCVEW-. ")


def decode(ids: list[int]) -> str:
    return "".join(VOCAB[i] for i in ids)


def prefers(text: str):
    """A fake model that always wants to write `text`, one character at a time,
    even when `text` is not in the context."""
    def next_scores(ids: list[int]) -> np.ndarray:
        written = len(ids) - 1  # one prompt token
        scores = np.zeros(len(VOCAB))
        if written < len(text):
            scores[VOCAB.index(text[written])] = 5.0
        scores[VOCAB.index(" ")] = 1.0
        return scores
    return next_scores


CONTEXT = ["T1055.011 Extra Window Memory Injection: ...", "T1566 Phishing: ...", "CVE-2021-44228 Log4j ..."]


def test_identifiers_are_found_with_their_passage():
    assert identifiers(CONTEXT) == [("T1055.011", 1), ("T1566", 2), ("CVE-2021-44228", 3)]


def test_a_model_that_wants_an_id_in_the_context_gets_it_with_the_right_citation():
    assert constrained_id(prefers("T1566"), decode, [0], CONTEXT) == "T1566 [2]"
    assert constrained_id(prefers("T1055.011"), decode, [0], CONTEXT) == "T1055.011 [1]"


def test_a_model_that_wants_an_id_not_in_the_context_cannot_write_it():
    out = constrained_id(prefers("T1027.003"), decode, [0], CONTEXT)
    name = out.split(" [")[0]
    assert name in {"T1055.011", "T1566", "CVE-2021-44228"}
    assert out.endswith(f"[{dict(identifiers(CONTEXT))[name]}]")


def test_every_output_parses_or_abstains():
    for wanted in ("T1566", "T9999", "CVE-2021-44228", "W"):
        out = constrained_id(prefers(wanted), decode, [0], CONTEXT)
        assert out.split(" [")[0] in {"T1055.011", "T1566", "CVE-2021-44228"} and out.endswith("]")
    assert constrained_id(prefers("T1566"), decode, [0], ["no identifiers here"]) == ABSTAIN
