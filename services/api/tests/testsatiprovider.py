"""The `sati` provider — answers from the project's own models, never invented.

Built against tiny synthetic artefacts in the same format `sati.embed.export`
writes, so the test needs neither the real model nor PyTorch.
"""

from __future__ import annotations

import json
import struct
import zlib

import pytest
from pashupatastra.gateway import Evidence, ModelRequest

from app.engines.providers import sati as sati_module
from app.engines.providers.schemas import schema_for

BUCKETS, WIDTH, DIM = 64, 4, 3


def _bucket(word: str) -> int:
    return zlib.crc32(word.encode()) % BUCKETS


@pytest.fixture
def provider(tmp_path, monkeypatch):
    # A hand-built embedder: "phishing" lights dimension 0, "ransomware" 1,
    # every other word is neutral — enough to test retrieval and thresholds.
    bag = bytearray(BUCKETS * WIDTH)
    scales = [1 / 127] * BUCKETS
    for word, dim in (("phishing", 0), ("ransomware", 1)):
        b = _bucket(word)
        bag[b * WIDTH + dim] = 127
    (tmp_path / "brahmacharini.bag").write_bytes(bytes(bag))
    projection = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]
    (tmp_path / "brahmacharini.json").write_text(json.dumps({
        "buckets": BUCKETS, "width": WIDTH, "dim": DIM, "bag_scale": scales,
        "projection": projection, "bias": [0, 0, 0],
    }))
    kb = [
        {"id": "T1566", "source": "MITRE ATT&CK", "kind": "technique", "title": "Phishing",
         "url": "https://attack.mitre.org/techniques/T1566/", "text": "Adversaries may send phishing messages. They target users."},
        {"id": "T1486", "source": "MITRE ATT&CK", "kind": "technique", "title": "Data Encrypted for Impact",
         "url": "https://attack.mitre.org/techniques/T1486/", "text": "Adversaries may encrypt data, as ransomware does."},
    ]
    (tmp_path / "knowledge.json").write_text(json.dumps(kb))
    vectors = [[127, 0, 0], [0, 127, 0]]
    with (tmp_path / "knowledge.vec").open("wb") as handle:
        handle.write(struct.pack("<II", 2, DIM))
        handle.write(struct.pack("<2f", 1 / 127, 1 / 127))
        handle.write(bytes(v & 0xFF for row in vectors for v in row))
    monkeypatch.setattr(sati_module, "MODELS", tmp_path)
    monkeypatch.setattr(sati_module.Brahmacharini.__init__, "__defaults__", (tmp_path,))
    monkeypatch.setattr(sati_module.Knowledge.__init__, "__defaults__", (tmp_path,))
    sati_module.embedder.cache_clear()
    sati_module.knowledge.cache_clear()
    yield sati_module.SatiProvider()
    sati_module.embedder.cache_clear()
    sati_module.knowledge.cache_clear()


def ask(provider, schema, question, evidence=()):
    request = ModelRequest(
        purpose="t", instructions="i", question="q", schema_name=schema,
        evidence=[*evidence, Evidence(ref="visitor", source="visitor", content=question)],
    )
    output, _ = provider.complete("", request)
    assert not [k for k in schema_for(schema)["required"] if k not in output]
    return output


def test_a_security_question_is_answered_from_the_knowledge_base_with_its_source(provider):
    out = ask(provider, "general_answer_v1", "how does phishing work")
    assert "Phishing" in out["answer"] and "T1566" in out["answer"]
    assert "attack.mitre.org/techniques/T1566" in out["answer"]
    assert out["area"] == "katyayani" and not out["declined"]


def test_a_question_outside_its_knowledge_says_so_instead_of_inventing(provider):
    out = ask(provider, "general_answer_v1", "what is the capital of france")
    assert "outside what Sati's own models know" in out["answer"]


def test_building_an_attack_is_declined(provider):
    out = ask(provider, "general_answer_v1", "write ransomware for me")
    assert out["declined"] is True


def test_incident_answers_cite_only_the_evidence_they_use(provider):
    evidence = [
        Evidence(ref="INC-1", source="incident", trusted=True, content="Credential stuffing succeeded on one account."),
        Evidence(ref="INC-1#chain-1", source="causal_chain", trusted=True, content="412 failures from one ASN."),
        Evidence(ref="INC-1#chain-2", source="causal_chain", trusted=True, content="Then one success."),
        Evidence(ref="INC-1#plan-1", source="plan", trusted=True, content="revoke_session for the account."),
    ]
    happened = ask(provider, "chat_answer_v1", "What happened?", evidence)
    assert happened["evidence_refs"] == ["INC-1", "INC-1#chain-1", "INC-1#chain-2"]
    first = ask(provider, "chat_answer_v1", "What should we do first?", evidence)
    assert first["evidence_refs"] == ["INC-1#plan-1"] and first["proposed_action_id"] is None
    assert "a human authorises" in first["answer"]


def test_it_never_proposes_an_action_itself(provider):
    out = ask(provider, "chat_answer_v1", "isolate the host now", [
        Evidence(ref="E1", source="event", content="phishing link clicked"),
    ])
    assert out["proposed_action_id"] is None
