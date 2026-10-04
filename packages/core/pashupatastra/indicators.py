"""Finding indicators in rendered text, and deciding what they are (R78).

An address in a causal step, a hash in an evidence line, a domain in a feed
entry — each is a thing an analyst wants to look up, and each is currently
plain text. This module says what a string is and where the indicators are
inside a longer one, so the interface can offer a lookup on exactly those
spans and on nothing else.

**The classification errs toward "not an indicator", deliberately.** This runs
over identifiers the console already renders — entity keys, event ids, action
ids — and the dangerous mistake is the permissive one: `j.rivera` is an
account in this estate, and a domain rule loose enough to match it would turn
every identifier on a public page into a question about which of our accounts
exist. So a domain must end in a suffix on the list below, an unlisted suffix
is not a domain rather than a guess, and a missed enrichment is a missing link
where a false one is an enumeration interface.

Nothing here reaches the network. What a lookup may consult is decided in the
API; this module only reads strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class IndicatorKind(StrEnum):
    IPV4 = "ipv4"
    DOMAIN = "domain"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    CVE = "cve"


HASH_KINDS = {32: IndicatorKind.MD5, 40: IndicatorKind.SHA1, 64: IndicatorKind.SHA256}

SUFFIXES = frozenset(
    """
    com net org edu gov mil int info biz io ai co me tv cc ly sh dev app
    cloud online site xyz top club shop store live link click icu work
    uk us ca au de fr nl ru cn jp in br it es se no fi dk pl ch at be cz
    ie nz za kr mx ar cl pt gr hu ro bg hr rs ua tr il sa ae sg hk tw th
    vn id my ph pk bd lk np ir eg ng ke gh tz ug ma dz tn
    """.split()
)
"""Public suffixes recognised as the end of a domain.

Not the full public-suffix list: that is thousands of entries, changes
monthly, and would be a dependency or a stale copy. This is the set a feed in
this console has ever produced plus the common generics, and the rule it
enforces is the one that matters — an unrecognised ending is **not** a domain.
`j.rivera` is an account here and `rivera` is not on this list, which is the
case the list exists for.
"""

_IPV4 = re.compile(r"(?<![\w.])((?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})(?![\w.])")
_HASH = re.compile(r"(?<![\w])([a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})(?![\w])")
_CVE = re.compile(r"(?<![\w-])(CVE-\d{4}-\d{4,7})(?![\w-])", re.IGNORECASE)
_DOMAIN = re.compile(
    r"(?<![\w.@-])((?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24})(?![\w-])"
)

# Order matters: a 32-character hex run is a hash, not four labels, and a CVE
# is matched before anything else can claim its digits.
_PATTERNS: tuple[tuple[re.Pattern[str], IndicatorKind | None], ...] = (
    (_CVE, IndicatorKind.CVE),
    (_HASH, None),  # length decides which hash
    (_IPV4, IndicatorKind.IPV4),
    (_DOMAIN, IndicatorKind.DOMAIN),
)


@dataclass(frozen=True)
class Span:
    """One indicator, and where it sat in the text it was found in."""

    value: str
    kind: IndicatorKind
    start: int
    end: int


def classify(value: str) -> IndicatorKind | None:
    """What this string is, whole. `None` for anything not unambiguously one
    of the kinds above — including every entity key this console uses."""
    candidate = (value or "").strip()
    if not candidate:
        return None
    for pattern, kind in _PATTERNS:
        match = pattern.fullmatch(candidate)
        if match is None:
            continue
        if kind is IndicatorKind.CVE:
            return kind
        if kind is None:
            return HASH_KINDS[len(candidate)]
        if kind is IndicatorKind.DOMAIN and not _has_known_suffix(candidate):
            return None
        return kind
    return None


def _has_known_suffix(domain: str) -> bool:
    return domain.rsplit(".", 1)[-1].lower() in SUFFIXES


def scan(text: str) -> list[Span]:
    """Every indicator inside a longer string, in the order they appear.

    Overlaps are resolved by the pattern order above and then by position, so
    `198.51.100.74` in `network_flow:ws-0148->198.51.100.74:8443` is found once
    as an address and never again as part of something else.
    """
    found: list[Span] = []
    taken: list[tuple[int, int]] = []

    for pattern, kind in _PATTERNS:
        for match in pattern.finditer(text or ""):
            start, end = match.start(1), match.end(1)
            if any(start < other_end and other_start < end for other_start, other_end in taken):
                continue
            value = match.group(1)
            resolved = HASH_KINDS[len(value)] if kind is None else kind
            if resolved is IndicatorKind.DOMAIN and not _has_known_suffix(value):
                continue
            taken.append((start, end))
            found.append(Span(value=value, kind=resolved, start=start, end=end))

    return sorted(found, key=lambda span: span.start)


def candidate_keys(value: str, kind: IndicatorKind) -> list[str]:
    """The entity keys this value could be stored under.

    The feeds key an indicator by what it is and which feed sent it — Feodo
    writes `indicator:ip:…`, ThreatFox writes `indicator:<its own ioc_type>:…`,
    URLhaus writes `indicator:url:<host>` — so one address can sit under more
    than one key and a lookup has to try each. Listed here rather than guessed
    at the call site, because the day a feed changes its key this is the one
    place that has to know.
    """
    lowered = value.lower()
    if kind is IndicatorKind.CVE:
        return [f"vulnerability:{value.upper()}"]
    if kind is IndicatorKind.IPV4:
        return [f"indicator:ip:{value}", f"indicator:ip_port:{value}", f"indicator:url:{value}"]
    if kind is IndicatorKind.DOMAIN:
        return [f"indicator:domain:{lowered}", f"indicator:url:{lowered}"]
    return [f"indicator:{kind.value}:{lowered}", f"indicator:{kind.value}_hash:{lowered}"]


__all__ = [
    "HASH_KINDS",
    "SUFFIXES",
    "IndicatorKind",
    "Span",
    "candidate_keys",
    "classify",
    "scan",
]
