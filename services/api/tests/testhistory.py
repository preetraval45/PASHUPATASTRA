"""Past incidents: built from the deploy-time record with the live rules, paged, and citable."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.feeds import history

NOW = datetime.now(UTC)


def record(source: str, rid: str, days_ago: int, entity: str, **labels: str) -> dict:
    return {
        "id": rid,
        "source": source,
        "occurred_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "entity_key": entity,
        "labels": labels,
        "provenance": {"source_system": source, "url": f"https://nvd.nist.gov/vuln/detail/{rid}"},
    }


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"generated": NOW.isoformat(), "records": [
        record("cisa-kev", "hist-kev-CVE-2021-44228", 1400, "vulnerability:CVE-2021-44228",
               title="Apache Log4j2 Remote Code Execution", ransomware="known"),
        record("cisa-kev", "hist-kev-CVE-2020-0001", 2000, "vulnerability:CVE-2020-0001", title="Old flaw"),
        record("cisa-kev", "hist-kev-CVE-2026-0001", 3, "vulnerability:CVE-2026-0001", title="This week"),
        record("hibp", "hist-hibp-Acme", 900, "organisation:breach:acme",
               title="Acme: 2,000,000 accounts exposed", accounts="2000000", exposed="Emails"),
    ]}), encoding="utf-8")
    monkeypatch.setattr(history, "FILE", path)
    for cached in (history._data, history._by_id, history._index, history._postings):
        cached.cache_clear()
    yield
    for cached in (history._data, history._by_id, history._index, history._postings):
        cached.cache_clear()


def test_the_past_starts_where_the_live_window_ends(recorded) -> None:
    ids = {i.id for i in history.incidents()}
    assert ids == {"PAST-KEV-CVE-2021-44228", "PAST-KEV-CVE-2020-0001", "PAST-BREACH-acme"}


def test_pages_filter_and_search(recorded) -> None:
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    page = client.get("/api/v1/incidents/past", params={"limit": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert page["items"][0]["id"] == "PAST-BREACH-acme", "newest first"
    assert client.get("/api/v1/incidents/past", params={"kind": "kev"}).json()["total"] == 2
    assert client.get("/api/v1/incidents/past", params={"q": "log4j"}).json()["total"] == 1
    assert client.get("/api/v1/incidents/past", params={"severity": "critical"}).json()["total"] == 1


def test_a_past_incident_opens_and_its_evidence_resolves(recorded) -> None:
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    incident = client.get("/api/v1/incidents/PAST-KEV-CVE-2021-44228").json()
    assert incident["severity"] == "critical"
    [ref] = incident["hypotheses"][0]["evidence"]
    cited = client.get(f"/api/v1/events/{ref}")
    assert cited.status_code == 200 and cited.json()["labels"]["title"].startswith("Apache Log4j2")


def test_without_the_file_there_is_no_history_and_it_says_so(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(history, "FILE", tmp_path / "absent.json")
    history._data.cache_clear()
    history._index.cache_clear()
    assert history.available()["records"] == 0 and history.incidents() == ()
    history._data.cache_clear()
    history._index.cache_clear()


def test_seen_before_ranks_by_rare_shared_words_and_says_which(tmp_path, monkeypatch) -> None:
    def rw(group: str, month: str) -> dict:
        return {"id": f"hist-rw-{group}-{month}", "source": "ransomwatch", "occurred_at": f"{month}-01T00:00:00+00:00",
                "entity_key": f"organisation:group:{group}",
                "labels": {"group": group, "month": month, "claims": "12"},
                "provenance": {"url": "https://ransomwatch.telemetry.ltd/"}}

    path = tmp_path / "history.json"
    records = [rw("lockbit3", "2024-01"), rw("lockbit3", "2024-02"), rw("akira", "2024-02")]
    records += [rw(f"filler{i}", "2023-05") for i in range(200)]  # so a group name is a rare word
    path.write_text(json.dumps({"generated": NOW.isoformat(), "records": records}), encoding="utf-8")
    monkeypatch.setattr(history, "FILE", path)
    for cached in (history._data, history._by_id, history._index, history._postings):
        cached.cache_clear()
    try:
        client = TestClient(__import__("app.main", fromlist=["app"]).app)
        found = client.get("/api/v1/incidents/PAST-RW-lockbit3-202402/similar").json()["items"]
        assert found[0]["incident"]["id"] == "PAST-RW-lockbit3-202401"
        assert found[0]["shared"] == ["lockbit3"]
        assert all(f["incident"]["id"] != "PAST-RW-lockbit3-202402" for f in found), "never itself"
        assert client.get("/api/v1/incidents/PAST-NOPE/similar").status_code == 404
    finally:
        for cached in (history._data, history._by_id, history._index, history._postings):
            cached.cache_clear()
