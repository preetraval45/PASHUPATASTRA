"""Buddhi's model access — the assembled gateway.

The one place a `Gateway` is constructed, so every engine shares one accountant
(cost per incident is a single number, not a per-module guess) and one circuit
breaker (a failing provider is discovered once, not independently by each caller).

Engines import `gateway()` from here. They never import a provider, and never
import an SDK — rule 5 in `CLAUDE.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
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
        reasoning_effort=settings.model_reasoning_effort,
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


@dataclass(frozen=True)
class ModelChoice:
    """One model a visitor may pick in the Ask console (RP-50).

    The list is built from server configuration and nothing else, so the picker
    is an allow-list: a request can name an `id` from it, never a model or an
    endpoint of its own. Rule 5 holds — the choice still goes through a
    `Gateway`, and the answer carries the provider and model that produced it.
    """

    id: str
    label: str
    provider: str
    model: str
    default: bool = False
    description: str = ""
    """What the model does, in a few words, shown under its name in the picker."""


DEFAULT_CHOICE = "default"

#: Sati's own models a visitor may pick by name, with the job each one does.
SATI_MODELS = (
    ("brahmacharini", "Brahmacharini", "Finds the ATT&CK technique, CVE or attack pattern"),
    ("skandamata", "Skandamata", "Recommends the mitigations that defend against an attack"),
)


def model_choices() -> list[ModelChoice]:
    """The configured default chain first, then each model on the fallback box.

    The fallback endpoint is the self-hosted Ollama box, so anything pulled onto
    it can be offered by naming it in `chat_models`; it needs no key of its own
    beyond the one the fallback already uses.
    """
    settings = get_settings()
    default_label = settings.model_id
    if settings.model_provider == "echo":
        default_label = "echo (deterministic stub)"
    elif settings.model_provider == "sati":
        default_label = "Sati AI"
    elif settings.model_provider == "failover" and settings.fallback_base_url:
        default_label = f"{settings.model_id}, falling back to {settings.fallback_model}"

    choices = [
        ModelChoice(
            id=DEFAULT_CHOICE,
            label=default_label,
            provider=settings.model_provider,
            model=settings.model_id,
            default=True,
            description="Picks the right model for each question" if settings.model_provider == "sati" else "",
        )
    ]
    if settings.model_provider == "sati":
        from .providers.sati import SatiProvider

        for mode, label, description in SATI_MODELS:
            if SatiProvider(mode).available():
                choices.append(ModelChoice(id=f"sati:{mode}", label=label, provider="sati",
                                           model=f"sati-{mode}", description=description))
    if not settings.fallback_base_url:
        return choices

    extra = [name.strip() for name in settings.chat_models.split(",") if name.strip()]
    seen: set[str] = set()
    for name in [settings.fallback_model, *extra]:
        if name in seen:
            continue
        seen.add(name)
        choices.append(
            ModelChoice(
                id=f"ollama:{name}",
                label=f"{name} (self-hosted)",
                provider="openai-compat",
                model=name,
            )
        )
    return choices


@lru_cache
def gateway_for(choice_id: str) -> Gateway:
    """A gateway for one allow-listed choice; `KeyError` for anything else.

    One gateway per choice, cached, rather than one per request: the budget and
    breaker are only meaningful when they persist, and a model that is down
    should be discovered once, not on every question. The default choice is the
    process gateway itself, so picking nothing changes nothing.
    """
    if choice_id == DEFAULT_CHOICE:
        return gateway()

    choice = next((c for c in model_choices() if c.id == choice_id), None)
    if choice is None:
        raise KeyError(choice_id)
    if choice.id.startswith("sati:"):
        from .providers.sati import SatiProvider

        settings = get_settings()
        return Gateway(
            provider=SatiProvider(choice.id.removeprefix("sati:")),
            accountant=Accountant(ceiling_per_incident=settings.model_token_ceiling),
            breaker=CircuitBreaker(),
        )

    settings = get_settings()
    from .providers.openaicompat import OpenAICompatProvider

    provider = OpenAICompatProvider(
        model=choice.model,
        base_url=settings.fallback_base_url or "",
        api_key_env=settings.fallback_api_key_env,
        requires_key=settings.fallback_requires_key,
        timeout=settings.fallback_timeout,
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
