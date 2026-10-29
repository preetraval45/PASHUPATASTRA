"""URLhaus and ThreatFox through abuse.ch's keyed APIs, once ABUSECH_AUTH_KEY is set."""

from __future__ import annotations

import pytest

from app.feeds import attacks, sources
from app.feeds.sources import FeedUnavailable


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv("ABUSECH_AUTH_KEY", "test-key")
    calls: list[tuple[str, dict | None, str]] = []

    def fake(url: str, body: dict | None, key: str):
        calls.append((url, body, key))
        if "threatfox" in url:
            return {"query_status": "ok", "data": [{
                "ioc": "198.51.100.9:443", "ioc_type": "ip:port", "threat_type": "botnet_cc",
                "malware_printable": "Cobalt Strike", "confidence_level": 100, "reporter": "abuse_ch",
                "first_seen": "2026-10-29 06:00:00 UTC", "tags": ["c2", "cobaltstrike"]}]}
        return {"query_status": "ok", "urls": [{
            "url": "http://bad.example/payload.exe", "url_status": "online", "threat": "malware_download",
            "date_added": "2026-10-29 05:00:00 UTC", "urlhaus_reference": "https://urlhaus.abuse.ch/url/42/",
            "reporter": "someone", "tags": ["exe"]}]}

    monkeypatch.setattr(attacks, "post_keyed", fake)
    monkeypatch.setattr(sources, "post_keyed", fake)
    return calls


def test_threatfox_reads_the_keyed_api_with_the_key_in_the_header(keyed):
    events = attacks.fetch_threatfox(limit=25)
    assert len(events) == 1 and events[0].entity_ref.name == "198.51.100.9:443"
    assert events[0].labels["tags"] == "c2, cobaltstrike"
    url, body, key = keyed[0]
    assert url == attacks.THREATFOX_API and body == {"query": "get_iocs", "days": 1} and key == "test-key"


def test_urlhaus_reads_the_keyed_api_and_links_the_advisory_not_the_malware(keyed):
    events = sources.fetch_urlhaus(limit=25)
    assert len(events) == 1 and events[0].entity_ref.name == "bad.example"
    assert events[0].provenance.url == "https://urlhaus.abuse.ch/url/42/"


def test_a_refused_key_is_a_feed_failure(monkeypatch):
    monkeypatch.setenv("ABUSECH_AUTH_KEY", "wrong")
    monkeypatch.setattr(attacks, "post_keyed", lambda *a: {"query_status": "unknown_auth_key"})
    with pytest.raises(FeedUnavailable):
        attacks.fetch_threatfox(limit=5)
