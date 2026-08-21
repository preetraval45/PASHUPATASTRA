"""Threat intelligence feeds, normalised into the event schema.

Three rules hold across every feed here, and they are the reason this is a
package rather than a function that fetches JSON.

**Nothing is fetched from the browser.** A page that asked a feed about each
address this deployment talks to would tell that feed everything this deployment
talks to. Feeds are polled server-side on a schedule and served from the store.

**Every entry carries the URL a human uses to check it.** An advisory the reader
cannot open is worth less than no advisory, because it invites belief without
offering verification.

**A report is never labelled confirmed.** `Verification` is a closed vocabulary,
not a free-text field, because the distinction between "CISA has observed this
being exploited" and "somebody submitted this URL an hour ago" is the entire
value of the second one. Losing it turns intelligence into rumour with a badge.
"""

from __future__ import annotations

from enum import StrEnum


class Verification(StrEnum):
    """How much weight an entry has earned. Ordered, and used as an ordering."""

    REPORTED = "reported"
    """Someone asserted this. No one here has checked it, and the publisher may
    not have either — community submissions arrive this way."""

    CORROBORATED = "corroborated"
    """More than one independent source says so, or the publisher applies review
    before listing."""

    CONFIRMED = "confirmed"
    """An authority states it as fact — CISA listing a vulnerability as
    exploited in the wild. The strongest label available, and never applied to
    something merely reported."""


RANK = {Verification.REPORTED: 1, Verification.CORROBORATED: 2, Verification.CONFIRMED: 3}


__all__ = ["RANK", "Verification"]
