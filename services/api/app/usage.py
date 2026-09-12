"""Tokens against the allowance — computed from the ledger, not from a counter.

Every chat turn is already an `agent_turn` audit record carrying `tokens` and
`cached` (R22). This rolls those up by day: turns, the share answered from
cache, tokens spent, and how much of the provider's daily allowance that is.
Nothing here is incremented as it happens; a counter beside the ledger would be
a second answer to "how much did we spend", and the day the two disagreed the
wrong one would be the one on the page.

Spend is zero on this deployment and the route says why, because a cost panel
reading `$0.00` with no explanation looks like a panel nobody wired (R104).

Cached turns cost nothing and are counted as turns, not as tokens: a cached
record carries the token count of the run that *produced* the answer (R22), and
adding that again would bill every repeat of a question at full price.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from .engines.audit import AuditKind, AuditRecord

WINDOW_DAYS = 14

SPEND_REASON = (
    "The model is reached on a free tier — Groq for the primary, an Oracle "
    "Always Free box for the fallback — chosen on 21 August 2026 over any "
    "pay-per-token key. Tokens are the only currency, and the allowance is the "
    "provider's daily limit."
)


def _day(at: datetime) -> str:
    return at.astimezone(UTC).date().isoformat()


def roll_up(
    turns: list[AuditRecord],
    *,
    allowance: int,
    now: datetime | None = None,
    window_days: int = WINDOW_DAYS,
) -> dict:
    """Usage per day from `agent_turn` records.

    Pure over its inputs so a script can recompute it from `/audit` and compare
    — that comparison is the route's own done-when.
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    today = now.date().isoformat()

    by_day: dict[str, dict[str, int]] = defaultdict(lambda: {"turns": 0, "from_cache": 0, "tokens": 0})
    for record in turns:
        if record.kind is not AuditKind.AGENT_TURN:
            continue
        bucket = by_day[_day(record.at)]
        bucket["turns"] += 1
        if record.detail.get("cached"):
            bucket["from_cache"] += 1
        else:
            bucket["tokens"] += int(record.detail.get("tokens") or 0)

    days = []
    for offset in range(window_days):
        day = (now - timedelta(days=offset)).date().isoformat()
        bucket = by_day.get(day, {"turns": 0, "from_cache": 0, "tokens": 0})
        days.append({"day": day, **bucket})

    current = days[0]
    turns_today = current["turns"]
    return {
        "as_of": now.isoformat(),
        "timezone": "UTC",
        "window_days": window_days,
        "allowance": {
            "tokens_per_day": allowance,
            "source": "settings.chat_daily_allowance — the provider's free-tier daily limit",
        },
        "today": {
            "day": today,
            "turns": turns_today,
            "from_cache": current["from_cache"],
            "answered_by_model": turns_today - current["from_cache"],
            "tokens": current["tokens"],
            "cache_hit_rate": (current["from_cache"] / turns_today) if turns_today else None,
            "allowance_used": (current["tokens"] / allowance) if allowance else None,
        },
        "days": days,
        "spend_usd": 0,
        "spend_reason": SPEND_REASON,
        "computed_from": "agent_turn audit records; cached turns count as turns and not as tokens",
    }
