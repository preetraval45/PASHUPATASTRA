"""Sati's chat surface.

`sati.analyst` — the read-only role. It answers questions about an incident and
cannot act; anything it proposes goes through Dharma and a human, on the same
path a person's request takes. See CLAUDE.md: Sati proposes, Dharma authorises.
"""

from __future__ import annotations

__all__ = ["chat", "context", "tools"]
