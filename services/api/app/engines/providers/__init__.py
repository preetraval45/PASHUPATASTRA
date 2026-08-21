"""Model providers.

These implement `pashupatastra.gateway.Provider` and are the only modules in the
system that import a model SDK. They live here, outside `packages/core`, because
core must stay cloud-free and laptop-runnable (the Platform ADR).

Selection is by configuration, never by import — `build_provider` resolves a
name at runtime, so adding a provider does not touch any engine, and swapping
Bedrock for the direct API is an environment variable.
"""

from __future__ import annotations

from pashupatastra.gateway import Provider

from .schemas import SCHEMAS, schema_for

__all__ = ["SCHEMAS", "build_provider", "schema_for"]


def build_provider(
    name: str,
    model: str,
    region: str,
    base_url: str | None = None,
    api_key_env: str = "PASHU_MODEL_API_KEY",
    fallback: dict | None = None,
) -> Provider:
    """Resolve a provider by name.

    Imports are deferred into the branches on purpose: a deployment that uses
    Bedrock should not need the direct-API client installed, and neither should
    be importable from engine code by accident.
    """
    match name:
        case "bedrock":
            from .claude import BedrockProvider

            return BedrockProvider(model=model, region=region)
        case "anthropic":
            from .claude import AnthropicProvider

            return AnthropicProvider(model=model)
        case "echo":
            from .echo import EchoProvider

            return EchoProvider()
        case "openai-compat":
            # Groq, Ollama, vLLM, LM Studio, OpenRouter. One name, because what
            # separates them is a base URL rather than a protocol.
            from .openaicompat import DEFAULT_BASE_URL, OpenAICompatProvider

            return OpenAICompatProvider(
                model=model,
                base_url=base_url or DEFAULT_BASE_URL,
                api_key_env=api_key_env,
            )
        case "failover":
            # Groq first for speed, a self-hosted box second for the quota it
            # does not have. See `failover.py` for why that order, not the other.
            from .failover import FailoverProvider
            from .openaicompat import DEFAULT_BASE_URL, OpenAICompatProvider

            if not fallback:
                raise ValueError("provider 'failover' needs a fallback endpoint")
            return FailoverProvider(
                primary=OpenAICompatProvider(
                    model=model,
                    base_url=base_url or DEFAULT_BASE_URL,
                    api_key_env=api_key_env,
                ),
                secondary=OpenAICompatProvider(
                    model=fallback["model"],
                    base_url=fallback["base_url"],
                    api_key_env=fallback["api_key_env"],
                    requires_key=fallback.get("requires_key", False),
                    timeout=fallback.get("timeout", 180.0),
                ),
            )
        case _:
            raise ValueError(
                f"unknown model provider {name!r}; expected 'openai-compat', "
                "'failover', 'bedrock', 'anthropic', or 'echo'"
            )
