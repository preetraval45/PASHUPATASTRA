"""Two providers, one fast and one unlimited, with the fast one first.

The pair is chosen for how their limits differ rather than for redundancy.
Groq's free tier answers in seconds and stops at 8,000 tokens a minute. Ollama
on a small always-free box has no quota at all and takes tens of seconds. Either
alone is the wrong trade for a public console: the first fails under a burst of
visitors, the second is too slow to feel like a console.

So the primary is tried first and the secondary catches what it drops. A visitor
who arrives during a quiet minute gets an answer in two seconds; a visitor who
arrives in the middle of a rush waits, which is much better than being refused.

`name` and `model` report whichever provider actually answered, because they end
up in the audit record and on the page. A pair that reported itself as one name
would make "which model said this" unanswerable — and that question is the whole
reason those fields exist.
"""

from __future__ import annotations

from typing import Any

from pashupatastra.gateway import ModelRequest, ProviderUnavailable, Usage


class FailoverProvider:
    """Primary, then secondary. Never the other way round."""

    supports_tools = True

    def __init__(self, primary, secondary) -> None:
        self.primary = primary
        self.secondary = secondary
        self._answered = primary

    @property
    def name(self) -> str:
        return self._answered.name

    @property
    def model(self) -> str:
        return self._answered.model

    def available(self) -> bool:
        """True if *either* can answer. A secondary with no key is not an
        outage, it is a deployment that chose not to configure one."""
        return _available(self.primary) or _available(self.secondary)

    def _candidates(self):
        return [p for p in (self.primary, self.secondary) if _available(p)]

    def _attempt(self, call, *args, **kwargs):
        failures: list[str] = []
        for provider in self._candidates():
            try:
                result = call(provider, *args, **kwargs)
            except ProviderUnavailable as error:
                # Rate limits arrive here too — the OpenAI-compatible provider
                # raises 429 and 413 as unavailable precisely so that a quota
                # sends the question to the box that has no quota, instead of
                # showing a stranger an error.
                failures.append(f"{provider.name}: {error}")
                continue
            self._answered = provider
            return result
        raise ProviderUnavailable(
            "no provider answered — " + "; ".join(failures or ["none configured"])
        )

    def complete(self, prompt: str, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        return self._attempt(lambda p: p.complete(prompt, request))

    def converse(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        schema_name: str | None,
        max_tokens: int,
    ) -> tuple[dict[str, Any], Usage]:
        return self._attempt(
            lambda p: p.converse(
                messages=messages,
                tools=tools,
                schema_name=schema_name,
                max_tokens=max_tokens,
            )
        )


def _available(provider) -> bool:
    return bool(getattr(provider, "available", lambda: True)())
