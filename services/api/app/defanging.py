"""Defanging at the serving boundary — one pass, so no route can forget it (R115).

`pashupatastra.defang` says how to defang a string. This says *what* gets
defanged on the way out, and it is applied where feed data leaves the API
rather than where a page happens to render it. The reason is the RSC payload:
a server component that renders a defanged string can still have been handed
the live one as a prop, and the live value lands in the bytes the browser
receives whether or not it is ever shown. Defanging at the exit means the live
value does not cross the wire at all.

**The advisory link is deliberately not defanged.** `urlhaus.abuse.ch/url/…`
is a reference *about* the indicator, not the indicator: R24 settled that the
malware URL is never rendered and the advisory always is, and a reader who
cannot follow the advisory cannot check the claim. It is also, unlike the
indicator, a page a filter is happy to see.

**Keys rather than a recursive guess.** The fields that carry indicator text
are listed, because a walk that defanged every string it met would mangle
prose, model names and entity keys that have nothing to do with a feed — and
because a reader of this module should be able to see what is covered without
running it.
"""

from __future__ import annotations

from typing import Any

from pashupatastra.defang import defang, defang_value

INDICATOR_FIELDS = frozenset(
    {
        "entity_key",
        "value",
        "name",
        "title",
        "summary",
        "identifier",
        "host",
        "ioc",
        "indicator",
    }
)
"""Fields whose value is, or contains, the indicator itself."""

LABEL_FIELDS = frozenset({"title", "summary", "tags", "exposed", "malware", "family"})
"""Keys inside a record's `labels` that carry feed-written text. A URLhaus
title is the host; a ThreatFox title names the family and the value."""

INDICATOR_LIST_FIELDS = frozenset({"keys_tried"})
"""Fields holding a list of strings that embed an indicator. `keys_tried` is
diagnostic and nothing renders it — and it still carries the live value into
the payload, which is the whole of what R115 forbids."""

PRESERVED = frozenset({"url", "advisory", "href", "source_system", "offset"})
"""Never defanged: the advisory link, and the bookkeeping around it. The
`offset` is a cursor — defanging it would move the feed's own place in the
catalogue."""


def defang_record(record: Any) -> Any:
    """One feed record, defanged. Returns a copy; the stored row is untouched.

    Recursive over lists and the nested `labels`/`provenance` mappings,
    because a group carries its reports and each report carries its own
    labels — but only the listed keys are ever rewritten.
    """
    if isinstance(record, list):
        return [defang_record(item) for item in record]
    if not isinstance(record, dict):
        return record

    out: dict[str, Any] = {}
    for key, value in record.items():
        if key in PRESERVED:
            out[key] = value
        elif key == "labels" and isinstance(value, dict):
            out[key] = {
                label: (defang(text) if label in LABEL_FIELDS and isinstance(text, str) else text)
                for label, text in value.items()
            }
        elif key == "provenance" and isinstance(value, dict):
            # Its `url` is the advisory and stays; anything else in it is
            # bookkeeping that carries no indicator.
            out[key] = value
        elif key in INDICATOR_FIELDS and isinstance(value, str):
            out[key] = defang_value(value)
        elif key in INDICATOR_LIST_FIELDS and isinstance(value, list):
            out[key] = [defang(item) if isinstance(item, str) else item for item in value]
        elif isinstance(value, (dict, list)):
            out[key] = defang_record(value)
        else:
            out[key] = value
    return out


def defang_intel(payload: dict) -> dict:
    """An `/intel` response, defanged — groups, their reports, and the raw
    rows alike."""
    return {
        key: (defang_record(value) if key in ("groups", "reports", "entries") else value)
        for key, value in payload.items()
    }


__all__ = ["INDICATOR_FIELDS", "INDICATOR_LIST_FIELDS", "LABEL_FIELDS", "PRESERVED", "defang_intel", "defang_record"]
