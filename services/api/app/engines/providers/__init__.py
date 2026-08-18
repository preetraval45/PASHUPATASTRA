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


def build_provider(name: str, model: str, region: str) -> Provider:
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
        case _:
            raise ValueError(
                f"unknown model provider {name!r}; expected 'bedrock', 'anthropic', or 'echo'"
            )
