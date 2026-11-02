"""Live incidents: built from stored feed records, citing them, and nothing invented.

Each rule is checked at its edges (inside the window, outside it, below the threshold), and the
properties every live incident must have are checked across all of them: it cites only records
the store holds, its links are https, no ransomware victim is named, and a malicious address is
never written in a form a reader could click.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.feeds import liveincidents as live

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def row(source: str, rid: str, at: datetime, entity: str, **labels: str) -> dict:
    return {
        "id": rid,
        "source": source,
        "occurred_at": at.isoformat(),
        "entity_key": entity,
        "labels": labels,
        "provenance": {"source_system": source, "url": f"https://example.org/{rid}"},
    }


class Store:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def recent_events(self, sources: list[str] | None = None, limit: int = 50) -> list[dict]:
        return [r for r in self.rows if not sources or r["source"] in sources][:limit]


def corpus() -> list[dict]:
    rows = [
        row("cisa-kev", "kev-new", NOW - timedelta(days=2), "vulnerability:CVE-2026-1000",
            title="Acme Gateway Injection", ransomware="known", due_date="2026-11-20"),
        row("cisa-kev", "kev-old", NOW - timedelta(days=120), "vulnerability:CVE-2026-0999", title="Old"),
        row("nvd", "nvd-crit", NOW - timedelta(days=1), "vulnerability:CVE-2026-2000", cvss="9.8",
            cvss_severity="CRITICAL", summary="Auth bypass."),
        row("nvd", "nvd-high", NOW - timedelta(days=1), "vulnerability:CVE-2026-2001", cvss="8.1"),
        row("nvd", "nvd-low", NOW - timedelta(days=1), "vulnerability:CVE-2026-2002", cvss="6.9"),
        row("hibp", "hibp-1", NOW - timedelta(days=3), "organisation:breach:acme",
            title="Acme: 2,000,000 accounts exposed", accounts="2000000", exposed="Emails"),
    ]
    rows += [
        row("threatfox", f"tf-{i}", NOW - timedelta(hours=i), f"indicator:domain:evil{i}.example.com",
            malware="AMOS")
        for i in range(6)
    ]
    rows += [row("threatfox", f"tf-few-{i}", NOW, f"indicator:ip:203.0.113.{i}", malware="Rare") for i in range(2)]
    rows += [
        row("ransomware-live", f"rw-{i}", NOW - timedelta(hours=10 * i), f"organisation:victim:victim corp {i}",
            group="pear", sector="Finance", country="US", title=f"pear claims a breach of Victim Corp {i}")
        for i in range(4)
    ]
    return rows


@pytest.fixture(autouse=True)
def no_record(monkeypatch):
    """The deploy-time record is merged into the live windows; these tests read only their rows."""
    from app.feeds import history

    monkeypatch.setattr(history, "records", lambda: [])


@pytest.fixture
def built() -> dict[str, object]:
    return {i.id: i for i in live.build(Store(corpus()), now=NOW)}


def test_each_rule_fires_inside_its_window_and_only_there(built) -> None:
    assert "LIVE-KEV-CVE-2026-1000" in built
    assert "LIVE-KEV-CVE-2026-0999" not in built, "older than 90 days"
    assert "LIVE-NVD-CVE-2026-2000" in built
    assert built["LIVE-NVD-CVE-2026-2001"].severity == "medium", "high CVSS, below critical"
    assert "LIVE-NVD-CVE-2026-2002" not in built, "below CVSS 7.0"
    assert "LIVE-C2-amos-20261102" in built
    assert not any("rare" in i for i in built), "two indicators are not a surge"
    assert "LIVE-RW-pear-20261102" in built
    assert "LIVE-BREACH-acme" in built


def test_ransomware_use_makes_an_exploited_cve_critical(built) -> None:
    assert built["LIVE-KEV-CVE-2026-1000"].severity == "critical"
    assert built["LIVE-BREACH-acme"].severity == "high"


def test_every_incident_cites_only_records_the_store_holds(built) -> None:
    held = {r["id"] for r in corpus()}
    for incident in built.values():
        assert incident.event_ids and set(incident.event_ids) <= held, incident.id
        for hypothesis in incident.hypotheses:
            assert set(hypothesis.evidence) <= held, incident.id
        for link in incident.causal_chain:
            assert set(link.evidence) <= held, incident.id
        assert all(s.url.startswith("https://") for s in incident.sources)
        assert incident.impact.estimated_users_affected == 0, "no invented user counts"


def test_no_ransomware_victim_is_named(built) -> None:
    text = built["LIVE-RW-pear-20261102"].model_dump_json().lower()
    assert "victim corp" not in text
    assert "finance 4" in text and "us 4" in text


def test_malicious_addresses_are_defanged_in_the_incident(built) -> None:
    text = built["LIVE-C2-amos-20261102"].model_dump_json()
    assert "evil0.example.com" not in text
    assert "evil0[.]example[.]com" in text


def test_a_source_that_cannot_be_read_does_not_empty_the_list() -> None:
    class Flaky(Store):
        def recent_events(self, sources=None, limit=50):
            if sources == ["nvd"]:
                raise RuntimeError("throttled")
            return super().recent_events(sources, limit)

    built = {i.id for i in live.build(Flaky(corpus()), now=NOW)}
    assert "LIVE-KEV-CVE-2026-1000" in built and not any(i.startswith("LIVE-NVD") for i in built)


def test_the_store_lists_live_incidents_when_the_deployment_serves_them(monkeypatch) -> None:
    from app.store import STORE

    fixed = live.build(Store(corpus()), now=NOW)
    monkeypatch.setattr(live, "current", lambda store: fixed)
    monkeypatch.setattr("app.store._get_settings", lambda: type("S", (), {"live_incidents": True})())
    listed = STORE.all()
    assert listed and all(live.is_live(i.id) for i in listed)
    assert STORE.get("LIVE-KEV-CVE-2026-1000").severity == "critical"
    assert STORE.get("LIVE-KEV-CVE-1999-0001") is None


def test_the_record_fills_the_live_window_and_the_poll_is_cited_first(monkeypatch) -> None:
    from app.feeds import history

    recorded = [
        row("cisa-kev", "hist-kev-CVE-2026-1000", NOW - timedelta(days=2), "vulnerability:CVE-2026-1000", title="dup"),
        row("cisa-kev", "hist-kev-CVE-2026-3000", NOW - timedelta(days=60), "vulnerability:CVE-2026-3000", title="older"),
    ]
    monkeypatch.setattr(history, "records", lambda: recorded)
    built = {i.id: i for i in live.build(Store(corpus()), now=NOW)}
    assert built["LIVE-KEV-CVE-2026-1000"].event_ids == ["kev-new"], "the polled record is cited"
    assert "LIVE-KEV-CVE-2026-3000" in built
    assert len([i for i in built if i == "LIVE-KEV-CVE-2026-1000"]) == 1


def test_scenario_records_stay_out_of_the_activity_views(monkeypatch) -> None:
    from app.engines import audit as audit_module
    from app.engines.audit import AuditKind, AuditLog, AuditRecord

    log = AuditLog()
    monkeypatch.setattr(log, "_store", lambda: None)
    log.append(AuditRecord(kind=AuditKind.OBSERVATION, actor="drishti", incident_ref="INC-2026-0904", summary="seeded"))
    log.append(AuditRecord(kind=AuditKind.AGENT_TURN, actor="sati.analyst", incident_ref=None, summary="real"))
    monkeypatch.setattr(audit_module, "_hide_scenarios", lambda: True)
    assert [r.summary for r in log.records()] == ["real"]
    assert [r.summary for r in log.records(incident_ref="INC-2026-0904")] == ["seeded"], "a drill reads its own trail"
    monkeypatch.setattr(audit_module, "_hide_scenarios", lambda: False)
    assert len(log.records()) == 2
