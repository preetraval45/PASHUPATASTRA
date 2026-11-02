"""Kavach 7.3: every intelligence record says where it came from, under what terms, from which
edition of the feed, and which weakness class a vulnerability belongs to."""

from __future__ import annotations

import json
from pathlib import Path

from app.feeds import ingest, sources
from app.feeds.ingest import LICENSES, MemoryCursors
from app.graphmemory import MemoryGraph

SAMPLES = Path(__file__).parent / "samples"

KEV = {
    "catalogVersion": "2026.10.30",
    "vulnerabilities": [{
        "cveID": "CVE-2026-0001", "vendorProject": "Acme", "product": "Gateway",
        "vulnerabilityName": "Acme Gateway OS Command Injection", "dateAdded": "2026-10-30",
        "shortDescription": "Acme Gateway contains an OS command injection flaw.",
        "requiredAction": "Apply updates.", "dueDate": "2026-11-20",
        "knownRansomwareCampaignUse": "Known", "cwes": ["CWE-78"],
    }],
}


def test_every_stored_record_carries_its_licence_and_feed_version(monkeypatch) -> None:
    monkeypatch.setattr(sources, "_get", lambda url: KEV)
    monkeypatch.setattr(ingest, "FEEDS", {"cisa-kev": sources.fetch_kev})
    graph = MemoryGraph()
    ingest.run(store=graph, cursors=MemoryCursors())
    [row] = graph.entity_events("vulnerability:CVE-2026-0001")
    assert row["provenance"]["license"] == "CC0-1.0"
    assert row["provenance"]["feed_version"] == "2026.10.30"
    assert row["labels"]["cwe"] == "CWE-78"
    assert row["observed_at"], "retrieval time"
    assert row["payload"]["confidence"] == 1.0


def test_nvd_records_link_their_weaknesses_and_name_the_api_edition(monkeypatch) -> None:
    payload = json.loads((SAMPLES / "nvd.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(sources, "_get", lambda url: payload)
    events = sources.fetch_nvd(limit=50)
    linked = [e for e in events if e.labels.get("cwe")]
    assert linked, "the real sample names CWEs, and some record must carry them"
    assert all(c.startswith("CWE-") for e in linked for c in e.labels["cwe"].split(","))
    assert all(e.provenance.feed_version and e.provenance.feed_version.startswith("NVD API") for e in events)


def test_every_polled_feed_has_its_terms_on_file() -> None:
    assert set(ingest.FEEDS) <= set(LICENSES), set(ingest.FEEDS) - set(LICENSES)


def test_an_advisory_shown_to_the_model_names_its_weakness() -> None:
    from app.agent.context import intel_evidence

    class Graph:
        def entity_events(self, key, limit=50):
            return [{"id": "e1", "source": "cisa-kev", "labels": {"title": "x", "cwe": "CWE-78"},
                     "provenance": {"source_system": "cisa-kev"}}]

    [block] = intel_evidence(Graph(), "Is CVE-2026-0001 bad?")
    assert "weakness: CWE-78" in block.content
