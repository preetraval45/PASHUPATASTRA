"""RP-42: the Kushmanda corpus manifest identifies a corpus without storing it."""

from __future__ import annotations

from sati.lm import corpus


def _docs():
    return [{"source": "mitre-attack", "id": f"T{i}", "text": f"technique {i} text"} for i in range(40)] + \
        [{"source": "cisa-kev", "id": f"CVE-{i}", "text": f"vulnerability {i}"} for i in range(20)]


def test_the_manifest_counts_each_source_and_split_and_hashes_ids_and_texts():
    docs = _docs()
    train, test = corpus.split(docs)
    m = corpus.manifest(docs, train, test, {"version": "test"})
    assert m["total"]["documents"] == 60 == m["train"]["documents"] + m["held_out"]["documents"]
    assert m["by_source"]["cisa-kev"]["documents"] == 20
    assert len(m["total"]["ids_sha256"]) == 64 and "text" not in str(m["by_source"]).lower().replace("texts_sha256", "")


def test_the_manifest_is_order_independent_and_changes_when_any_text_does():
    docs = _docs()
    train, test = corpus.split(docs)
    a = corpus.manifest(docs, train, test, {})
    b = corpus.manifest(list(reversed(docs)), train, test, {})
    assert a == b
    edited = [dict(d) for d in docs]
    edited[0]["text"] += "!"
    c = corpus.manifest(edited, *corpus.split(edited), {})
    assert c["total"]["ids_sha256"] == a["total"]["ids_sha256"]
    assert c["total"]["texts_sha256"] != a["total"]["texts_sha256"]
