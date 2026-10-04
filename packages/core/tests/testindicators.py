"""R78: what counts as an indicator, and what must never be mistaken for one.

The cases are in `pashupatastra/indicators.json`, shared with the TypeScript
classifier that marks up the page — two implementations, one definition.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pashupatastra.indicators import (
    IndicatorKind,
    candidate_keys,
    classify,
    scan,
)

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "pashupatastra" / "indicators.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES["classify"], ids=lambda c: c["value"] or "empty")
def test_classify_matches_the_shared_cases(case: dict) -> None:
    expected = IndicatorKind(case["kind"]) if case["kind"] else None
    assert classify(case["value"]) == expected, case.get("why", "")


@pytest.mark.parametrize("case", CASES["scan"], ids=lambda c: c["text"][:30] or "empty")
def test_scan_matches_the_shared_cases(case: dict) -> None:
    found = [[span.value, span.kind.value] for span in scan(case["text"])]
    assert found == [list(span) for span in case["spans"]], case.get("why", "")


def test_a_span_knows_where_it_sat_so_the_page_can_mark_it_up() -> None:
    text = "network_flow:ws-0148->198.51.100.74:8443"
    span = scan(text)[0]
    assert text[span.start : span.end] == span.value


def test_an_unknown_suffix_is_not_a_domain_rather_than_a_guess() -> None:
    """The rule the suffix list exists to enforce. A new generic TLD is a
    missing link until it is listed; a permissive rule is an interface for
    asking which accounts exist, and only one of those is recoverable."""
    assert classify("thing.zzzzz") is None
    assert classify("thing.com") is IndicatorKind.DOMAIN


def test_the_keys_a_lookup_tries_cover_how_each_feed_writes_them() -> None:
    """Feodo writes `indicator:ip:`, URLhaus writes `indicator:url:<host>`,
    ThreatFox writes its own `ioc_type`. One address sits under more than one
    key, and a lookup that tried only the first would report nothing known
    about something the store holds."""
    assert candidate_keys("198.51.100.74", IndicatorKind.IPV4) == [
        "indicator:ip:198.51.100.74",
        "indicator:ip_port:198.51.100.74",
        "indicator:url:198.51.100.74",
    ]
    assert "vulnerability:CVE-2026-69836" in candidate_keys("cve-2026-69836", IndicatorKind.CVE)
    assert candidate_keys("EVIL.COM", IndicatorKind.DOMAIN) == [
        "indicator:domain:evil.com",
        "indicator:url:evil.com",
    ]
    md5 = "d41d8cd98f00b204e9800998ecf8427e"
    assert candidate_keys(md5, IndicatorKind.MD5) == [
        f"indicator:md5:{md5}",
        f"indicator:md5_hash:{md5}",
    ]


def test_no_entity_key_in_this_estate_is_ever_an_indicator() -> None:
    """The guard, stated as its own test because it is the one that matters:
    this classifier runs over every identifier the console renders, and the
    permissive mistake would make a public page an enumeration interface."""
    for key in (
        "account:j.rivera",
        "account:m.okafor",
        "host:ws-0148",
        "asset:oauth-app-Rep0rt-Sync",
        "process:app-07/schtasks",
        "network_flow:ws-0148->198.51.100.74:8443",
    ):
        assert classify(key) is None
