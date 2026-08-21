"""Buddhi's model access — the assembled gateway.

The one place a `Gateway` is constructed, so every engine shares one accountant
(cost per incident is a single number, not a per-module guess) and one circuit
breaker (a failing provider is discovered once, not independently by each caller).

Engines import `gateway()` from here. They never import a provider, and never
import an SDK — rule 5 in `CLAUDE.md`.
"""

from __future__ import annotations

from functools import lru_cache

from pashupatastra.gateway import Accountant, CircuitBreaker, Gateway
from pashupatastra.reasoning import Reasoner
from pashupatastra.smriti import Smriti

from ..config import get_settings
from .providers import build_provider


@lru_cache
def gateway() -> Gateway:
    """The process-wide gateway.

    Cached because the accountant and breaker carry state that is only meaningful
    when shared: a per-request gateway would reset the budget on every call and
    re-discover an outage from scratch each time.
    """
    settings = get_settings()
    provider = build_provider(
        name=settings.model_provider,
        model=settings.model_id,
        region=settings.aws_region,
        base_url=settings.model_base_url,
        api_key_env=settings.model_api_key_env,
        fallback=(
            {
                "base_url": settings.fallback_base_url,
                "model": settings.fallback_model,
                "api_key_env": settings.fallback_api_key_env,
                "requires_key": settings.fallback_requires_key,
                "timeout": settings.fallback_timeout,
            }
            if settings.fallback_base_url
            else None
        ),
    )
    return Gateway(
        provider=provider,
        accountant=Accountant(ceiling_per_incident=settings.model_token_ceiling),
        breaker=CircuitBreaker(),
    )


@lru_cache
def memory() -> Smriti:
    """Organizational memory.

    In-memory for now; the persistence decision is deferred to a measurement
    rather than an assumption (ADR Smriti). The embedder is the local lexical
    one, so this works with no credentials — and degrades honestly rather than
    silently, since the structured filters carry most of the weight.
    """
    return Smriti()


@lru_cache
def reasoner() -> Reasoner:
    """Buddhi's reasoning layer, on the shared gateway and memory.

    Shares the process gateway rather than building its own, so reasoning spend
    lands in the same per-incident budget as every other model call — a second
    accountant would let one incident quietly spend twice its ceiling.
    """
    settings = get_settings()
    return Reasoner(gateway(), memory=memory(), tenant=settings.tenant)


def model_health() -> dict[str, object]:
    """What `/health` reports about the model layer.

    `configured: false` is a first-class state rather than an error: running on
    the stub is the correct default for a fresh checkout, and an operator should
    be able to see at a glance that no model is wired up — the same reason the
    detector reports its unwarmed baselines instead of staying quiet.
    """
    settings = get_settings()
    accounting = gateway().accountant.report()
    return {
        "provider": settings.model_provider,
        "model": settings.model_id,
        "configured": settings.model_provider != "echo",
        "calls": accounting["calls"],
        "total_tokens": accounting["total_tokens"],
    }
