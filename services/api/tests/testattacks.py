"""The four real-attack feeds, against committed samples of the real responses.

The samples in `tests/samples/` were captured from the live endpoints on
24 August 2026. They are the real shape — including the parts that make these
feeds awkward, which is the reason to commit a real sample rather than write a
tidy fixture: ransomware.live sends `"N/A"` where a description is missing and
marks some of them `[AI generated]`, Feodo sends `first_seen_utc: null` on most
rows, and HIBP's `BreachDate` is routinely years before its `AddedDate`.

A fixture written from the documentation would have none of those, and every
one of them is a way this code can be wrong.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.feeds import Verification
from app.feeds import attacks
from app.feeds.attacks import (
    ATTACK_FEEDS,
    fetch_feodo,
    fetch_hibp,
    fetch_ransomware,
    fetch_threatfox,
)
from app.feeds.sources import FeedUnavailable
from pashupatastra.events import EntityKind

SAMPLES = Path(__file__).resolve().parent / "samples"


def sample(name: str):
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def offline(monkeypatch):
    """Serve each feed its committed sample instead of the network.

    Keyed by URL rather than by call order, so a test that fetches two feeds
    cannot pass by getting the right payloads in the wrong sequence.
    """
    payloads = {
        attacks.RANSOMWARE_URL: sample("ransomware-live"),
        attacks.FEODO_URL: sample("feodo-tracker"),
        attacks.THREATFOX_URL: sample("threatfox"),
        attacks.HIBP_URL: sample("hibp"),
    }
    monkeypatch.setattr(attacks, "_get", lambda url: payloads[url])
    return payloads


# --- each feed produces events ----------------------------------------------


def test_every_feed_parses_its_real_sample(offline) -> None:
    for name, fetch in ATTACK_FEEDS.items():
        events = fetch(limit=25)
        assert events, f"{name} produced nothing from its own sample"


def test_a_ransomware_claim_names_the_victim_and_the_group(offline) -> None:
    events = fetch_ransomware(limit=25)
    first = events[0]
    assert first.entity_ref.kind is EntityKind.ORGANISATION
    assert first.entity_ref.id.startswith("victim:")
    assert first.labels["group"]
    assert first.labels["group"] in first.labels["title"]


def test_feodo_names_the_malware_family(offline) -> None:
    families = {event.labels["malware"] for event in fetch_feodo(limit=25)}
    assert families
    assert all(family for family in families)


def test_threatfox_reads_the_bulk_export_shape(offline) -> None:
    """The export is an object keyed by id, each value a single-element list —
    not the array the other three send."""
    events = fetch_threatfox(limit=25)
    assert events
    assert all(event.entity_ref.kind is EntityKind.INDICATOR for event in events)


def test_hibp_counts_the_accounts(offline) -> None:
    events = fetch_hibp(limit=25)
    assert events
    assert all(int(event.labels["accounts"]) >= 0 for event in events)


# --- the honesty rules ------------------------------------------------------


def test_a_leak_site_claim_is_never_confirmed(offline) -> None:
    """The source of a ransomware listing is the attacker, publishing to
    pressure a payment. Some listings are inflated and a few are invented."""
    for event in fetch_ransomware(limit=25):
        assert event.labels["verification"] == Verification.REPORTED
        assert event.labels["claimed_by"] == "the attacker"


def test_nothing_links_to_a_leak_site(offline) -> None:
    """`claim_url` on these records is a Tor address serving stolen data. The
    console links to ransomware.live's clearnet page for the group instead.

    Asserted over the whole event, not just provenance, because a `.onion`
    address reaching a label would be rendered too."""
    raw = sample("ransomware-live")
    onions = [row["claim_url"] for row in raw if row.get("claim_url")]
    assert onions, "the sample must contain a leak-site URL or this proves nothing"

    for event in fetch_ransomware(limit=25):
        body = event.model_dump_json()
        assert ".onion" not in body
        for onion in onions:
            assert onion not in body
        assert event.provenance.url.startswith(attacks.RANSOMWARE_GROUP_PAGE)


def test_no_reported_attack_carries_an_invented_causal_chain(offline) -> None:
    """These records say *that* it happened and to whom, and nothing about how.
    An `Event` has no place to put a causal chain, which is the point — the
    absence is structural rather than a convention someone must remember."""
    for name, fetch in ATTACK_FEEDS.items():
        for event in fetch(limit=25):
            assert not hasattr(event, "hypotheses"), name
            assert not hasattr(event, "plan"), name
            # No technique attributed to a specific victim.
            body = event.model_dump_json()
            assert "attack_technique" not in body, name


def test_a_fabricated_breach_is_dropped_not_captioned(offline, monkeypatch) -> None:
    """HIBP flags records whose data it believes is not real. Publishing one
    with a caveat would put a fake breach on a page about real ones."""
    rows = sample("hibp")
    rows[0]["IsFabricated"] = True
    monkeypatch.setattr(attacks, "_get", lambda url: rows)
    names = {event.entity_ref.name for event in fetch_hibp(limit=25)}
    assert rows[0]["Title"] not in names


# --- a bad record must not take the poll down --------------------------------


@pytest.mark.parametrize("feed", sorted(ATTACK_FEEDS))
def test_a_malformed_record_is_dropped_rather_than_fatal(offline, monkeypatch, feed) -> None:
    """One publisher sending one broken row is not a reason to lose the other
    three feeds for an hour."""
    payloads = {
        "ransomware-live": (attacks.RANSOMWARE_URL, sample("ransomware-live")),
        "feodo-tracker": (attacks.FEODO_URL, sample("feodo-tracker")),
        "threatfox": (attacks.THREATFOX_URL, sample("threatfox")),
        "hibp": (attacks.HIBP_URL, sample("hibp")),
    }
    url, rows = payloads[feed]

    if isinstance(rows, dict):
        broken = {"junk": [{"ioc_value": None}], **rows}
    else:
        broken = [{}, {"victim": None, "group": None}, *rows]

    monkeypatch.setattr(attacks, "_get", lambda _u, rows=broken: rows)
    events = ATTACK_FEEDS[feed](limit=25)
    assert events, f"{feed} dropped everything because one row was broken"


@pytest.mark.parametrize("feed", sorted(ATTACK_FEEDS))
def test_a_wrongly_shaped_response_raises_feed_unavailable(monkeypatch, feed) -> None:
    """Not a crash and not silence. `FeedUnavailable` is what the scheduler
    already knows how to record and retry."""
    monkeypatch.setattr(attacks, "_get", lambda _u: "not what this feed sends")
    with pytest.raises(FeedUnavailable):
        ATTACK_FEEDS[feed](limit=5)


# --- dates ------------------------------------------------------------------


def test_an_unreadable_date_drops_the_record_rather_than_dating_it_now(monkeypatch) -> None:
    """Dating a record to the moment it was fetched would present a two-year-old
    breach as this afternoon's news, and every one of these feeds is read as a
    timeline."""
    rows = sample("ransomware-live")
    for row in rows:
        row["attackdate"] = "the day before yesterday"
        row["discovered"] = ""
    monkeypatch.setattr(attacks, "_get", lambda _u: rows)
    assert fetch_ransomware(limit=25) == []


def test_hibp_orders_by_disclosure_not_by_breach_date(offline) -> None:
    """The two are often years apart. Ordered by `BreachDate`, today's
    disclosure of a 2023 incident would appear as nothing at all."""
    rows = sample("hibp")
    expected = [
        r["Title"] or r["Name"]
        for r in sorted(rows, key=lambda r: r["AddedDate"], reverse=True)
    ]
    assert [event.entity_ref.name for event in fetch_hibp(limit=25)] == expected


def test_the_cursor_skips_what_was_already_stored(offline) -> None:
    """The `since` cursor is what stops an hourly poll rewriting the same rows
    twenty-four times a day."""
    everything = fetch_ransomware(limit=25)
    assert len(everything) > 1
    newest = everything[0].provenance.offset
    assert fetch_ransomware(limit=25, since=newest) == []


def test_stamps_are_timezone_aware(offline) -> None:
    """A naive datetime compared against an aware one raises, and the comparison
    happens in the grouping code rather than here."""
    for fetch in ATTACK_FEEDS.values():
        for event in fetch(limit=25):
            assert event.occurred_at.tzinfo is not None
            assert event.occurred_at <= datetime.now(UTC)


# --- polled and served must be the same set ---------------------------------


def test_every_feed_that_is_polled_is_also_served() -> None:
    """The bug this catches actually happened.

    `/intel` imported `FEEDS` from `sources.py` rather than the merged registry
    in `ingest.py`, so all four attack feeds polled successfully on the hour,
    wrote 44 real events to the store, and were then filtered out of the only
    endpoint that reads them. Every individual piece worked. The site showed
    nothing.

    Asserted as set equality rather than a subset: a feed served but never
    polled is the same failure seen from the other end.
    """
    from app.api.routes import intel
    from app.feeds.ingest import FEEDS

    served = set(intel(limit=1)["sources"])
    assert served == set(FEEDS), (
        f"polled but not served: {sorted(set(FEEDS) - served)}; "
        f"served but not polled: {sorted(served - set(FEEDS))}"
    )


def test_the_attack_feeds_are_registered() -> None:
    """Named explicitly, so deleting one from the registry fails here rather
    than quietly reducing the site to indicators again."""
    from app.feeds.ingest import FEEDS

    assert {"ransomware-live", "feodo-tracker", "threatfox", "hibp"} <= set(FEEDS)


def test_a_breach_is_dated_to_its_disclosure_not_to_the_breach(offline) -> None:
    """The event recorded is "this was published", which is today's news. The
    breach itself may be years old and is carried as a label.

    Dating to `BreachDate` sorted every HIBP record off the end of a timeline
    built on recency: twelve were stored and none reached the page.
    """
    rows = {r["Title"] or r["Name"]: r for r in sample("hibp")}
    for event in fetch_hibp(limit=25):
        row = rows[event.entity_ref.name]
        assert event.occurred_at == _stamped(row["AddedDate"])
        assert event.labels["breach_date"] == str(row["BreachDate"])


def _stamped(value):
    from app.feeds.attacks import _stamp

    return _stamp(value)
