"""The few numbers a stranger meets first, each recomputed on the way out (R119).

A landing page is where a figure nobody can check does the most damage, and
where it is least likely to be questioned. So every figure here is derived from
the store or the registry at request time — not cached, not incremented, not
typed — and each carries the page a reader can go and recount it on.

**A figure whose source is absent renders as absent.** The benchmark is the
case that proves the rule rather than a hypothetical branch: `tables.md` carries
a correct-diagnosis rate and `benchmark/results/` holds no run records, so the
figure cannot be recomputed from this repository and is reported as having no
committed evidence. A stale number would read exactly like a measured one,
which is the whole reason this file exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pashupatastra.dharma import Tier
from pashupatastra.registry import all_actions

from .impact import absent, measured

BENCHMARK = Path(__file__).resolve().parents[3] / "docs" / "benchmark.json"


def citations_resolve(incidents: list, graph: Any) -> dict[str, Any]:
    """The share of every evidence reference that resolves to a stored event.

    The console's central claim, counted rather than asserted: a citation that
    leads nowhere looks exactly like one that leads to the record, and the only
    difference a reader can detect is whether following it works. Every ref on
    every hypothesis and every causal step is followed here.
    """
    event = getattr(graph, "event", None)
    if event is None:
        return absent("this store cannot resolve an event by id")

    refs: set[str] = set()
    for incident in incidents:
        for hypothesis in incident.hypotheses:
            refs.update(hypothesis.evidence)
            refs.update(hypothesis.contradicted_by)
        for link in incident.causal_chain:
            refs.update(link.evidence)
    if not refs:
        return absent("no incident in this store cites anything")

    resolved = sum(1 for ref in sorted(refs) if event(ref) is not None)
    return measured(
        {
            "resolved": resolved,
            "cited": len(refs),
            "share": round(resolved / len(refs), 4),
        },
        "every evidence reference on every incident, followed to the stored event",
    )


def never_unattended(domain: Any = None) -> dict[str, Any]:
    """How much of the action registry can never run without a human.

    Counted from the registry and the tier rules rather than from a sentence on
    a marketing page. `changes_nothing` is the exemption R4b settled — risk 0
    *and* nothing to verify — so what is counted here is every action that
    carries any risk at all, which is the set a human must stand behind.
    """
    actions = all_actions(domain)
    if not actions:
        return absent("no action is registered in this configuration")
    unattended = [action for action in actions if action.changes_nothing]
    return measured(
        {
            "registered": len(actions),
            "needs_a_human": len(actions) - len(unattended),
            "share": round((len(actions) - len(unattended)) / len(actions), 4),
        },
        "the action registry: every action that changes anything needs a human",
    )


def irreversible_refused(domain: Any = None) -> dict[str, Any]:
    """Actions the policy engine will not run at all, whoever asks.

    The `denied` tier is the one claim about autonomy that is worth checking,
    because it is the one a reader assumes is marketing. Counted from the same
    engine that enforces it.
    """
    from pashupatastra.dharma import RiskContext, evaluate
    from .config import get_settings

    settings = get_settings()
    actions = all_actions(domain)
    if not actions:
        return absent("no action is registered in this configuration")

    context = RiskContext(environment=settings.environment, dry_run=settings.dry_run)
    denied = [a for a in actions if evaluate(a, context).tier is Tier.DENIED]
    return measured(
        {
            "registered": len(actions),
            "denied": len(denied),
            "examples": sorted(a.id for a in denied)[:3],
        },
        "Dharma's verdict on every registered action in this environment",
    )


def benchmark() -> dict[str, Any]:
    """The benchmark figure, or why there is not one."""
    if not BENCHMARK.exists():
        return absent("docs/benchmark.json has not been generated")
    try:
        data = json.loads(BENCHMARK.read_text(encoding="utf-8")).get("benchmark", {})
    except (OSError, json.JSONDecodeError) as error:
        return absent(f"docs/benchmark.json unreadable: {type(error).__name__}")
    if data.get("absent"):
        return absent(data["absent"])
    return measured(data, data.get("from", "benchmark/results"))


__all__ = ["benchmark", "citations_resolve", "irreversible_refused", "never_unattended"]
