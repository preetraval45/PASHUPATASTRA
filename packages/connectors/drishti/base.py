"""Connector framework.

Every connector produces `Event` objects and nothing else. Two rules are
structural rather than conventional:

1. **Connectors are read-only.** A connector has no method that mutates anything.
   Perception is therefore incapable of causing an incident — which is why its
   AWS credentials are a separate, read-only role (docs/DEPLOYMENT.md).
2. **Provenance is stamped here, not by the caller.** Every event carries the
   query that produced it, so any downstream claim can be traced back to a
   record a human can re-fetch.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pashupatastra import Event, QuarantinedEvent


@dataclass
class Window:
    """The time range a poll covers.

    `start` is exclusive so consecutive polls cannot double-count a sample at the
    boundary — duplicated metric points would look like a spike that never
    happened, which is the kind of artefact that produces a confident wrong
    diagnosis.
    """

    start: datetime
    end: datetime

    @classmethod
    def trailing(cls, seconds: int, now: datetime | None = None) -> "Window":
        end = now or datetime.now().astimezone()
        return cls(start=end - timedelta(seconds=seconds), end=end)


@dataclass
class Harvest:
    """What one poll produced.

    Quarantined events are returned alongside good ones rather than dropped:
    they signal stale topology, and silence about them would hide the fact that
    perception has a blind spot.
    """

    events: list[Event] = field(default_factory=list)
    quarantined: list[QuarantinedEvent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.errors

    def extend(self, other: "Harvest") -> "Harvest":
        self.events.extend(other.events)
        self.quarantined.extend(other.quarantined)
        self.errors.extend(other.errors)
        return self


class Connector(abc.ABC):
    """Read-only source of normalized events."""

    name: str
    version: str = "0.1.0"

    @abc.abstractmethod
    def poll(self, window: Window) -> Harvest:
        """Fetch everything observed in `window`, normalized into events."""

    def check(self) -> bool:
        """Whether the upstream system is reachable."""
        try:
            return self.poll(Window.trailing(60)).healthy
        except Exception:
            return False
