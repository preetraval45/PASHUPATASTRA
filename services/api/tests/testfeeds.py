"""Threat feed ingestion.

Run against captured payloads, not against the live feeds. A suite that fetches
from CISA and abuse.ch fails when somebody else has an outage, and a red suite
that means nothing is a suite people learn to ignore. `scripts/verifyfeeds.py`
is where "does the real feed still have this shape" belongs.

The captured samples are trimmed real responses, so the parsing is exercised
against the field names and formats those services actually send — including
URLhaus's tags arriving as a Python-repr string rather than JSON.
"""

from __future__ import annotations

import pytest
from app.feeds import RANK, Verification
from app.feeds.ingest import MemoryCursors, run
from app.feeds.sources import FeedUnavailable, fetch_kev, fetch_urlhaus

KEV_PAYLOAD = {
    "title": "CISA Catalog of Known Exploited Vulnerabilities",
    "count": 3,
    "vulnerabilities": [
        {
            "cveID": "CVE-2026-0001",
            "vendorProject": "Acme",
            "product": "Gateway",
            "vulnerabilityName": "Acme Gateway Command Injection",
            "dateAdded": "2026-08-20",
            "shortDescription": "Acme Gateway contains a command injection flaw.",
            "requiredAction": "Apply mitigations per vendor instructions.",
            "dueDate": "2026-09-10",
            "knownRansomwareCampaignUse": "Known",
        },
        {
            "cveID": "CVE-2026-0002",
            "vendorProject": "Beta",
            "product": "Server",
            "vulnerabilityName": "Beta Server Path Traversal",
            "dateAdded": "2026-08-18",
            "shortDescription": "Beta Server contains a path traversal flaw.",
            "requiredAction": "Apply updates.",
            "dueDate": "2026-09-08",
            "knownRansomwareCampaignUse": "Unknown",
        },
        # Out of order on purpose: the real catalogue is not date-sorted, and
        # its last rows are years old.
        {
            "cveID": "CVE-2019-9999",
            "vendorProject": "Old",
            "product": "Thing",
            "vulnerabilityName": "Old Thing Flaw",
            "dateAdded": "2019-01-01",
            "shortDescription": "An old one.",
            "requiredAction": "Upgrade.",
            "dueDate": "2019-02-01",
            "knownRansomwareCampaignUse": "Unknown",
        },
    ],
}

URLHAUS_PAYLOAD = {
    "3906624": [
        {
            "dateadded": "2026-08-21 16:43:19 UTC",
            "url": "http://113.221.25.94:57880/i/Mozi.m",
            "url_status": "online",
            "threat": "malware_download",
            "tags": "['32-bit', 'elf', 'Mozi']",
            "reporter": "geenensp",
            "urlhaus_link": "https://urlhaus.abuse.ch/url/3906624/",
        }
    ],
    "3906623": [
        {
            "dateadded": "2026-08-21 10:00:00 UTC",
            "url": "http://malicious.example/payload.exe",
            "url_status": "offline",
            "threat": "malware_download",
            "tags": ["exe"],
            "reporter": "someone",
            "urlhaus_link": "https://urlhaus.abuse.ch/url/3906623/",
        }
    ],
}


@pytest.fixture
def feeds(monkeypatch):
    """Both sources answering from captured payloads."""
    from app.feeds import sources

    def fake_get(url: str):
        return KEV_PAYLOAD if "cisa.gov" in url else URLHAUS_PAYLOAD

    monkeypatch.setattr(sources, "_get", fake_get)


# --- the verification vocabulary ---------------------------------------------


def test_verification_is_ordered_not_just_named() -> None:
    """`confirmed` outranking `reported` is the point. Used as a set of labels
    with no order, nothing can sort or filter by how much a claim is worth."""
    assert RANK[Verification.CONFIRMED] > RANK[Verification.CORROBORATED]
    assert RANK[Verification.CORROBORATED] > RANK[Verification.REPORTED]


def test_cisa_is_confirmed_and_abuse_ch_is_reported(feeds) -> None:
    """The distinction is the whole value of the second feed. CISA's entry
    criterion is evidence of exploitation; URLhaus publishes submissions."""
    assert all(e.labels["verification"] == Verification.CONFIRMED for e in fetch_kev())
    assert all(e.labels["verification"] == Verification.REPORTED for e in fetch_urlhaus())


def test_a_report_is_never_rated_as_confidently_as_a_confirmation(feeds) -> None:
    kev = fetch_kev()[0]
    reported = fetch_urlhaus()[0]
    assert kev.payload.confidence > reported.payload.confidence


# --- provenance ---------------------------------------------------------------


def test_every_entry_carries_a_url_a_human_can_open(feeds) -> None:
    """An advisory the reader cannot check is worth less than none: it invites
    belief without offering verification."""
    for event in [*fetch_kev(), *fetch_urlhaus()]:
        assert event.provenance.url, event.entity_ref.key()
        assert event.provenance.url.startswith("https://")
        assert event.provenance.source_system


def test_the_malware_url_is_never_the_thing_shown(feeds) -> None:
    """These are live distribution points. The entity key and name reach the
    console; the advisory *about* the URL is what a reader follows."""
    for event in fetch_urlhaus():
        assert "Mozi.m" not in event.entity_ref.key()
        assert "payload.exe" not in event.entity_ref.name
        assert "urlhaus.abuse.ch" in (event.provenance.url or "")


# --- parsing the real shapes ---------------------------------------------------


def test_kev_is_read_newest_first_not_last_first(feeds) -> None:
    """The catalogue is not in date order — its final rows are years old — so
    taking the tail would present 2019 advisories as this week's news."""
    events = fetch_kev(limit=2)
    assert [e.entity_ref.id for e in events] == ["CVE-2026-0001", "CVE-2026-0002"]


def test_ransomware_use_decides_severity(feeds) -> None:
    """The field that separates urgent from merely important, applied rather
    than left in the payload for a reader to notice."""
    by_id = {e.entity_ref.id: e for e in fetch_kev()}
    assert str(by_id["CVE-2026-0001"].severity) == "critical"
    assert str(by_id["CVE-2026-0002"].severity) == "warning"


def test_urlhaus_tags_survive_both_shapes_they_arrive_in(feeds) -> None:
    """They come as a JSON list, and sometimes as a Python-repr string."""
    events = fetch_urlhaus()
    assert "Mozi" in events[0].labels["tags"]
    assert "exe" in events[1].labels["tags"]


def test_an_offline_url_is_less_severe_than_a_live_one(feeds) -> None:
    events = {e.labels["status"]: e for e in fetch_urlhaus()}
    assert str(events["online"].severity) == "warning"
    assert str(events["offline"].severity) == "info"


# --- the cursor ----------------------------------------------------------------


class Recorder:
    def __init__(self) -> None:
        self.events: list = []

    def save_events(self, events) -> int:
        self.events.extend(events)
        return len(events)


def test_a_second_run_stores_nothing_new(feeds) -> None:
    """Without this, an hourly poll of a daily catalogue rewrites the same rows
    twenty-four times a day and calls each of them news."""
    store, cursors = Recorder(), MemoryCursors()
    first = run(store, cursors)
    assert first["cisa-kev"]["stored"] > 0

    before = len(store.events)
    second = run(store, cursors)
    assert second["cisa-kev"]["stored"] == 0
    assert len(store.events) == before


def test_the_cursor_does_not_move_when_the_write_fails(feeds) -> None:
    """Advancing first means a failed write skips those entries forever, and
    the gap is invisible — the feed looks quiet rather than broken."""
    class Failing:
        def save_events(self, events):
            raise RuntimeError("store is down")

    cursors = MemoryCursors()
    with pytest.raises(RuntimeError):
        run(Failing(), cursors)
    assert cursors.get_feed_cursor("cisa-kev") is None


def test_one_feed_being_down_does_not_stop_the_others(monkeypatch) -> None:
    """Third parties have outages. A run that aborted on the first would turn
    somebody else's five minutes into a gap in ours."""
    from app.feeds import sources

    def selective(url: str):
        if "cisa.gov" in url:
            raise FeedUnavailable("cisa is down")
        return URLHAUS_PAYLOAD

    monkeypatch.setattr(sources, "_get", selective)

    store = Recorder()
    summary = run(store, MemoryCursors())

    assert summary["cisa-kev"]["ok"] is False
    assert "cisa is down" in summary["cisa-kev"]["error"]
    assert summary["urlhaus"]["ok"] is True
    assert summary["urlhaus"]["stored"] > 0


def test_the_first_run_is_deliberately_smaller(feeds) -> None:
    """On a first run everything is new, and the point is to have something to
    show rather than to import a catalogue of thousands."""
    from app.feeds.ingest import DEFAULT_LIMIT, FIRST_RUN_LIMIT

    assert FIRST_RUN_LIMIT < DEFAULT_LIMIT


# --- what feeds must not do ----------------------------------------------------


def test_intelligence_never_becomes_a_topology_node(feeds) -> None:
    """A map that draws a thousand CVEs beside eleven hosts tells a reader they
    are the same kind of fact, and blast radius would traverse from a host into
    a vulnerability as though the two were connected."""
    from app.graph import entitystore

    graph = entitystore()
    before, _ = graph.counts()
    graph.save_events([*fetch_kev(), *fetch_urlhaus()])
    after, _ = graph.counts()
    assert after == before


def test_entries_are_retrievable_by_id_like_any_other_evidence(feeds) -> None:
    """The whole point of storing them: a claim about a CVE can be followed to
    the record it came from."""
    from app.graph import entitystore

    graph = entitystore()
    events = fetch_kev(limit=2)
    graph.save_events(events)
    assert graph.event(events[0].id) is not None


# --- R26: the agent answers from the stored entry, not from memory ------------


class Graph:
    """Just enough store to resolve one advisory by entity key."""

    def __init__(self, rows: dict[str, list[dict]] | None = None) -> None:
        self.rows = rows or {}
        self.asked: list[str] = []

    def entity_events(self, key: str, limit: int = 50) -> list[dict]:
        self.asked.append(key)
        return self.rows.get(key, [])[:limit]


ADVISORY = {
    "id": "evt-advisory-1",
    "source": "cisa-kev",
    "labels": {
        "verification": "confirmed",
        "title": "Acme Gateway Command Injection",
        "summary": "Acme Gateway contains a command injection flaw.",
        "required_action": "Apply mitigations per vendor instructions.",
        "due_date": "2026-09-10",
        "ransomware": "known",
    },
    "provenance": {
        "source_system": "cisa-kev",
        "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-0001",
        "offset": "2026-08-20",
    },
}


def test_identifiers_are_extracted_case_insensitively_and_bounded() -> None:
    """Narrow on purpose. A looser pattern would turn every question into a
    lookup of whatever string it contained, which on a public console is an
    interface for asking which of *our* entities exist."""
    from app.agent.context import identifiers

    assert identifiers("does cve-2026-0001 matter?") == ["CVE-2026-0001"]
    assert identifiers("XCVE-2026-0001Y") == []
    assert identifiers("CVE-2026-0001 and CVE-2026-0001") == ["CVE-2026-0001"]
    assert len(identifiers(" ".join(f"CVE-2026-000{n}" for n in range(1, 9)))) == 4


def test_a_mentioned_cve_is_retrieved_before_the_model_is_asked() -> None:
    """The whole of R26. A model asked about a CVE already has an opinion from
    training, and an opinion is what it gives if nothing better is in front of
    it. Retrieval first makes the grounded answer the easy one."""
    from app.agent.context import intel_evidence

    graph = Graph({"vulnerability:CVE-2026-0001": [ADVISORY]})
    blocks = intel_evidence(graph, "Is CVE-2026-0001 relevant here?")

    assert len(blocks) == 1
    assert blocks[0].ref == "evt-advisory-1"
    assert "Acme Gateway Command Injection" in blocks[0].content
    assert "confirmed" in blocks[0].content
    assert "nvd.nist.gov" in blocks[0].content
    # Reputable, and still not us.
    assert blocks[0].trusted is False


def test_an_unknown_cve_produces_no_block_at_all() -> None:
    """The tempting alternative is a block saying "nothing on file", which
    hands the model a ref to cite for a claim about nothing — an answer that
    looks grounded while resting on an absence."""
    from app.agent.context import intel_evidence

    assert intel_evidence(Graph(), "What about CVE-1999-9999?") == []


def test_a_question_naming_nothing_costs_no_lookups() -> None:
    from app.agent.context import intel_evidence

    graph = Graph()
    intel_evidence(graph, "What happened on this host?")
    assert graph.asked == []


def test_the_advisory_tool_refuses_anything_that_is_not_an_identifier() -> None:
    """Without validation the argument is an arbitrary string reaching
    `entity_events`, and `account:j.rivera` is an arbitrary string."""
    from pashupatastra.gateway import ToolCall
    from app.agent.tools import ToolBox

    class FakeIncident:
        affected_entities: list = []
        causal_chain: list = []

    box = ToolBox(FakeIncident(), None, Graph({"vulnerability:CVE-2026-0001": [ADVISORY]}))

    refused = box.dispatch(ToolCall(id="1", name="lookup_advisory",
                                    arguments={"identifier": "account:j.rivera"}))
    assert refused.ok is False
    assert refused.refused == "not an identifier"

    ok = box.dispatch(ToolCall(id="2", name="lookup_advisory",
                               arguments={"identifier": "CVE-2026-0001"}))
    assert ok.ok is True
    assert ok.refs == ["evt-advisory-1"]
    assert "Acme Gateway" in ok.content


def test_the_advisory_tool_says_so_when_there_is_no_entry() -> None:
    """Distinct from refusing: the identifier was valid and we simply have
    nothing. The model needs to be able to tell those apart."""
    from pashupatastra.gateway import ToolCall
    from app.agent.tools import ToolBox

    class FakeIncident:
        affected_entities: list = []
        causal_chain: list = []

    outcome = ToolBox(FakeIncident(), None, Graph()).dispatch(
        ToolCall(id="1", name="lookup_advisory", arguments={"identifier": "CVE-2026-0001"})
    )
    assert outcome.ok is True
    assert outcome.refs == []
    assert "No stored advisory" in outcome.content


def test_the_prompt_forbids_answering_a_cve_from_memory() -> None:
    """The rule that makes the retrieved advisory win over the recollection."""
    from app.agent.chat import INSTRUCTIONS, PROMPT_VERSION

    assert PROMPT_VERSION == "3", "the prompt changed; the version must move with it"
    lowered = INSTRUCTIONS.lower()
    assert "what you remember does not count" in lowered
    assert "will not answer from memory" in lowered
