"""Defanging indicators, so a page carrying them is not itself a threat (R115).

Visitors reported that the site would not open — a *website restricted* page
from their own network, not an error from ours. The first cause that fits is
this one: the Observatory served live malware-distribution URLs, live C2
addresses and live domains as plain text, and a content-scanning filter
classifies a page by what it carries. One flagged page commonly takes the
whole host with it.

So an indicator that came from a feed is rendered the way the feeds themselves
publish them — `hxxp://evil[.]example`, `45[.]61[.]184[.]22` — and never in a
form a browser, a crawler or a filter will treat as live. This is the oldest
convention in threat intelligence and it exists for exactly this reason: a
reader can see the value, and nothing downstream can accidentally resolve it.

**What is defanged, and what is not.** Values that came from a feed: the
indicator itself, and any URL or host inside it. Not the *advisory* link —
`urlhaus.abuse.ch/url/3906624/` is a reference about the thing, which R24
already settled is what gets linked, and defanging it would leave the reader
no way to check. Not documentation-range addresses in the scripted scenarios
(`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), which exist to be
written down and cannot route anywhere.

`refang` is the exact inverse, so the value a lookup is keyed by survives the
round trip and an analyst who needs the live form can get it back
deliberately — which is the point of the convention rather than a hole in it.
"""

from __future__ import annotations

import ipaddress
import re

SCHEME = re.compile(r"\b(?P<scheme>https?|ftp)(?=://)", re.IGNORECASE)
DOT = re.compile(r"\.(?=\w)")
AT = re.compile(r"@")

_DEFANGED_SCHEME = re.compile(r"\b(?P<scheme>h[x]{2}ps?|f[x]p)(?=://)", re.IGNORECASE)
_DEFANGED_DOT = re.compile(r"\[\.\]")
_DEFANGED_AT = re.compile(r"\[@\]")

DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)
"""RFC 5737's TEST-NET ranges. Reserved for documentation, guaranteed not to
route, and therefore the only addresses a written scenario should contain."""


def is_documentation_address(value: str) -> bool:
    """Whether this is an address that exists to be written down."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return any(address in network for network in DOCUMENTATION_NETWORKS)


def is_routable(value: str) -> bool:
    """Whether an address could actually be reached — the test a scenario has
    to pass before it may carry one literally."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_reserved
        or address.is_multicast
        or address.is_link_local
        or address.is_unspecified
        or is_documentation_address(value)
    )


def defang(text: str) -> str:
    """The convention, applied: `.` becomes `[.]`, `@` becomes `[@]`, and a
    URL scheme loses its `tt`.

    Idempotent — defanging an already-defanged string leaves it alone, which
    matters because this runs at a serialisation boundary and a value can
    reach it twice.
    """
    if not text:
        return text
    marked = SCHEME.sub(lambda m: _mangle_scheme(m.group("scheme")), text)
    marked = AT.sub("[@]", marked)
    return DOT.sub("[.]", marked)


def refang(text: str) -> str:
    """The exact inverse. A lookup keyed by the live value survives the round
    trip, and an analyst gets the real thing back by asking for it."""
    if not text:
        return text
    restored = _DEFANGED_SCHEME.sub(lambda m: _unmangle_scheme(m.group("scheme")), text)
    restored = _DEFANGED_AT.sub("@", restored)
    return _DEFANGED_DOT.sub(".", restored)


def _mangle_scheme(scheme: str) -> str:
    lowered = scheme.lower()
    replaced = {"http": "hxxp", "https": "hxxps", "ftp": "fxp"}[lowered]
    return replaced.upper() if scheme.isupper() else replaced


def _unmangle_scheme(scheme: str) -> str:
    lowered = scheme.lower()
    replaced = {"hxxp": "http", "hxxps": "https", "fxp": "ftp"}[lowered]
    return replaced.upper() if scheme.isupper() else replaced


def defang_value(value: str) -> str:
    """One indicator value, defanged unless it is an address that cannot route.

    The exception is narrow on purpose: a documentation address is reserved
    precisely so it can be written down, and defanging it would make a
    scripted scenario harder to read for no gain. Everything else — every
    feed-sourced address, domain and URL — is defanged whether or not anyone
    believes this particular one is dangerous, because the filter reading the
    page is not making that judgement either.
    """
    candidate = (value or "").strip()
    if is_documentation_address(candidate):
        return candidate
    return defang(value)


__all__ = [
    "DOCUMENTATION_NETWORKS",
    "defang",
    "defang_value",
    "is_documentation_address",
    "is_routable",
    "refang",
]
