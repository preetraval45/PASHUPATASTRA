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


def test_markup_in_a_passage_never_reaches_the_answer():
    from app.engines.providers.sati import first_sentences

    text = "<xhtml:p>An adversary tries known username/password combinations.</xhtml:p> <xhtml:p>More.</xhtml:p>"
    out = first_sentences(text)
    assert "<" not in out and out.startswith("An adversary tries")


@pytest.fixture
def with_skandamata(provider, tmp_path, monkeypatch):
    # "phishing" → user training (M1017); "ransomware" → data backup (M1053).
    # Its own, larger hash space: at 64 buckets a long question collides with
    # "phishing" and the test would measure the collision, not the routing.
    buckets, hidden = 4096, 2
    bag = bytearray(buckets * WIDTH)
    for word, dim in (("phishing", 0), ("ransomware", 1)):
        bag[(zlib.crc32(word.encode()) % buckets) * WIDTH + dim] = 127
    (tmp_path / "skandamata.bag").write_bytes(bytes(bag))
    (tmp_path / "skandamata.json").write_text(json.dumps({
        "buckets": buckets, "width": WIDTH, "hidden": hidden, "bag_scale": [1 / 127] * buckets,
        "w1": [[1, 0, 0, 0], [0, 1, 0, 0]], "b1": [0, 0],
        "w2": [[40, 0], [0, 40]], "b2": [-3, -3],
        "mitigations": [{"id": "M1017", "name": "User Training", "url": "https://attack.mitre.org/mitigations/M1017/"},
                        {"id": "M1053", "name": "Data Backup", "url": "https://attack.mitre.org/mitigations/M1053/"}],
    }))
    monkeypatch.setattr(sati_module.Skandamata.__init__, "__defaults__", (tmp_path,))
    sati_module.mitigator.cache_clear()
    yield
    sati_module.mitigator.cache_clear()


def _general(provider, question: str) -> dict:
    return ask(provider, "general_answer_v1", question)


def test_a_defence_question_is_answered_by_skandamata_with_sources(provider, with_skandamata):
    out = _general(provider, "How do we defend against ransomware encrypting our files?")
    assert out["area"] == "skandamata"
    assert "Data Backup (M1053)" in out["answer"] and "https://attack.mitre.org/mitigations/M1053/" in out["answer"]
    assert "User Training" not in out["answer"]  # below the confidence floor for this question


def test_choosing_a_model_by_name_uses_only_that_model(provider, with_skandamata):
    lookup = sati_module.SatiProvider("brahmacharini")
    assert _general(lookup, "How do we defend against phishing?")["area"] != "skandamata"
    only = sati_module.SatiProvider("skandamata")
    assert only.available() and _general(only, "phishing emails to staff")["area"] == "skandamata"
    with pytest.raises(ValueError):
        sati_module.SatiProvider("not-a-model")


def test_without_its_files_skandamata_is_not_offered(provider):
    assert not sati_module.SatiProvider("skandamata").available()
    assert _general(provider, "How do we defend against phishing?")["area"] != "skandamata"


class _FakeTok:
    """Words in, words out: enough to drive `_write` without a real tokenizer."""

    def __init__(self, reply: str):
        self.reply = reply

    def encode(self, text):
        return type("E", (), {"ids": [1, 2, 3]})()

    def decode(self, ids):
        return self.reply

    def token_to_id(self, token):
        return 0


class _FakeEngine:
    def generate(self, ids, n, stop=None):
        return [5, 6]


def _kushmanda(monkeypatch, reply: str):
    monkeypatch.setattr(sati_module, "writer", lambda: (_FakeEngine(), _FakeTok(reply)))
    return sati_module.SatiProvider("kushmanda")


def test_kushmanda_answers_in_its_own_words_and_cites_its_passage(provider, monkeypatch):
    out = _general(_kushmanda(monkeypatch, "Attackers send deceptive messages to trick users. [1]"), "what is phishing")
    assert out["area"] == "kushmanda" and out["answer"].startswith("Attackers send deceptive messages")
    assert "Source: Phishing (MITRE ATT&CK T1566)" in out["answer"]


def test_an_identifier_its_cited_passage_lacks_is_never_shown(provider, monkeypatch):
    out = _general(_kushmanda(monkeypatch, "This is technique T1059.001. [1]"), "what is phishing")
    assert "T1059.001" not in out["answer"] and out["area"] != "kushmanda"  # fell back to the passage itself


def test_an_uncited_answer_falls_back_and_a_refusal_is_said_plainly(provider, monkeypatch):
    assert _general(_kushmanda(monkeypatch, "Phishing tricks users."), "what is phishing")["area"] != "kushmanda"
    out = _general(_kushmanda(monkeypatch, "The context does not answer this."), "what is phishing")
    assert out["area"] == "kushmanda" and "declines rather than guess" in out["answer"]
