"""Collapsing repeated reports into one row per indicator.

The fixture has a known duplicate count on purpose: R56 asks for a test that
asserts both the number of groups and the number of reports inside each, and a
fixture whose shape is obvious from reading it is the only way that assertion
means anything. The live feed had one address reported forty-three times, which
is what the page was rendering as forty-three cards.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.feeds.grouping import GROUPING_WINDOW, group

BASE = datetime(2026, 8, 24, 12, 0, 0)

# Twelve reports, three indicators: 8 + 3 + 1.
#   busy    — 8 sightings inside the window, plus one from two days earlier
#   quiet   — 3 sightings, the newest of which says the URL has gone offline
#   single  — reported once
FIXTURE: list[dict] = (
    [
        {
            "id": f"busy-{n}",
            "entity_key": "indicator:url:1.1.1.1",
            "occurred_at": (BASE - timedelta(minutes=15 * n)).isoformat(),
            "source": "urlhaus",
            "severity": "warning",
            "provenance": {"url": "https://urlhaus.abuse.ch/url/1/"},
            "labels": {"status": "online", "verification": "reported", "title": "busy"},
        }
        for n in range(8)
    ]
    + [
        {
            "id": "busy-ancient",
            "entity_key": "indicator:url:1.1.1.1",
            "occurred_at": (BASE - timedelta(days=2)).isoformat(),
            "source": "urlhaus",
            "severity": "info",
            "provenance": {},
            "labels": {"status": "offline", "verification": "reported"},
        }
    ]
    + [
        {
            "id": f"quiet-{n}",
            "entity_key": "indicator:url:2.2.2.2",
            "occurred_at": (BASE - timedelta(hours=5, minutes=10 * n)).isoformat(),
            "source": "urlhaus",
            "severity": "info",
            "provenance": {},
            "labels": {"status": "offline", "verification": "reported", "title": "quiet"},
        }
        for n in range(3)
    ]
    + [
        {
            "id": "single",
            "entity_key": "vulnerability:CVE-2026-0001",
            "occurred_at": (BASE - timedelta(hours=1)).isoformat(),
            "source": "cisa-kev",
            "severity": "critical",
            "provenance": {"url": "https://nvd.nist.gov/vuln/detail/CVE-2026-0001"},
            "labels": {"verification": "confirmed", "title": "one advisory"},
        }
    ]
)

EXPECTED = {
    "indicator:url:1.1.1.1": 9,
    "indicator:url:2.2.2.2": 3,
    "vulnerability:CVE-2026-0001": 1,
}


def grouped() -> dict[str, dict]:
    return {row["entity_key"]: row for row in group(FIXTURE)}


# --- the done-when --------------------------------------------------------------


def test_no_indicator_appears_twice() -> None:
    """The bug, stated as a property. Thirteen rows, three indicators."""
    rows = group(FIXTURE)
    keys = [row["entity_key"] for row in rows]
    assert len(keys) == len(set(keys))
    assert len(rows) == len(EXPECTED)


def test_every_group_keeps_all_of_its_reports() -> None:
    """Grouping collapses the display, not the data. Eight independent
    sightings is itself a fact about an indicator."""
    rows = grouped()
    for key, count in EXPECTED.items():
        assert rows[key]["reports"] == count, key
        assert len(rows[key]["history"]) == count, key


def test_no_report_is_lost_between_input_and_output() -> None:
    """Asserted over ids rather than counts, so a group that dropped one report
    and duplicated another could not pass."""
    seen = {report["id"] for row in group(FIXTURE) for report in row["history"]}
    assert seen == {entry["id"] for entry in FIXTURE}


# --- the window -----------------------------------------------------------------


def test_the_window_counts_recent_reports_not_all_of_them() -> None:
    """Eight sightings in two hours, plus one from two days before. The headline
    is about the burst, and the ninth is still in the history."""
    busy = grouped()["indicator:url:1.1.1.1"]
    assert busy["reports"] == 9
    assert busy["reports_in_window"] == 8


def test_the_window_is_relative_to_the_indicator_not_to_now() -> None:
    """`quiet` was last reported five hours before the fixture's clock and days
    before any real one. Anchored to the wall clock its count would be zero, and
    the number a page prints would depend on when the page was loaded."""
    quiet = grouped()["indicator:url:2.2.2.2"]
    assert quiet["reports_in_window"] == 3


def test_the_window_is_a_named_constant() -> None:
    """It appears in the count, in the phrase the page prints and in this file.
    A literal `3` in three places is two chances to change one and forget."""
    assert GROUPING_WINDOW == timedelta(hours=3)
    assert grouped()["indicator:url:1.1.1.1"]["window_hours"] == 3


def test_a_wider_window_gathers_the_older_report() -> None:
    rows = {r["entity_key"]: r for r in group(FIXTURE, window=timedelta(days=3))}
    assert rows["indicator:url:1.1.1.1"]["reports_in_window"] == 9


# --- what the status is for -------------------------------------------------------


def test_activity_follows_the_latest_report_not_the_most_optimistic() -> None:
    """An indicator whose most recent sighting says offline has gone offline.
    Carrying "some report said online" forward would leave dead infrastructure
    on the board as a live threat.

    `busy` is the case that matters: its oldest report is offline and its newest
    is online, so a rule reading any-or-all would get one of them wrong.
    """
    rows = grouped()
    assert rows["indicator:url:1.1.1.1"]["active"] is True
    assert rows["indicator:url:2.2.2.2"]["active"] is False


# --- ordering ---------------------------------------------------------------------


def test_groups_are_ordered_by_recency_not_by_volume() -> None:
    """Forty-three sightings of something last seen on Tuesday matters less than
    one sighting from ten minutes ago."""
    order = [row["entity_key"] for row in group(FIXTURE)]
    assert order == [
        "indicator:url:1.1.1.1",  # newest report, and the most of them
        "vulnerability:CVE-2026-0001",  # an hour old, reported once
        "indicator:url:2.2.2.2",  # five hours old
    ]
    volume = sorted(EXPECTED, key=lambda key: EXPECTED[key], reverse=True)
    assert order != volume, "recency and volume must be distinguishable here"


def test_the_group_carries_the_newest_reports_details() -> None:
    """A group shows one title, one severity and one advisory link, and they
    should be the current ones rather than whichever report happened to be
    first out of the store."""
    busy = grouped()["indicator:url:1.1.1.1"]
    assert busy["severity"] == "warning"
    assert busy["title"] == "busy"
    assert busy["last_at"] == BASE.isoformat()
    assert busy["first_at"] == (BASE - timedelta(days=2)).isoformat()


def test_an_empty_feed_groups_to_nothing() -> None:
    assert group([]) == []


def test_a_feed_that_reports_no_liveness_is_not_filed_as_offline() -> None:
    """Regression, and it reached production.

    `active` was `status == "online"`, so every source that does not report
    liveness — a ransomware leak-site claim, a disclosed breach — evaluated
    false and was collapsed into a panel headed "Gone offline". Four of the six
    feeds were on the site and unreachable.

    Absent is not offline. It is the publisher declining to make the claim.
    """
    silent = [
        {
            "id": "claim-1",
            "entity_key": "organisation:victim:example ltd",
            "occurred_at": BASE.isoformat(),
            "source": "ransomware-live",
            "severity": "critical",
            "provenance": {},
            "labels": {"verification": "reported", "group": "qilin"},
        }
    ]
    assert group(silent)[0]["active"] is None


def test_only_an_explicit_offline_is_offline() -> None:
    rows = {r["entity_key"]: r for r in group(FIXTURE)}
    assert rows["indicator:url:1.1.1.1"]["active"] is True
    assert rows["indicator:url:2.2.2.2"]["active"] is False
