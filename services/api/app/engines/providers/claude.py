"""Claude providers — direct API and Bedrock, behind one shape.

Both reach the same Messages API and expose the same `messages.create` surface,
so the request construction lives here once and the two concrete providers differ
only in how the client is built and how the model is named. That is the vendor
neutrality the ADR asks for, made real: if the two paths had separate request
builders they would drift, and "swappable by configuration" would quietly stop
being true.

Request choices worth knowing, since several would be bugs if copied from older
code:

* **Structured outputs, not prompted JSON.** `output_config.format` constrains
  the response to the declared schema server-side. Asking for JSON in the prompt
  and parsing what comes back is the thing this module exists to prevent.
* **No sampling parameters.** `temperature`, `top_p` and `top_k` are rejected on
  current Claude models. Behaviour is steered by the prompt.
* **Adaptive thinking.** Fixed thinking budgets are gone; depth is set through
  effort instead.
* **Streaming above the timeout threshold.** A large non-streaming request dies
  on an HTTP timeout rather than returning, so the request is streamed once
  `max_tokens` is large and the final message collected.
"""

from __future__ import annotations

import json
from typing import Any

from pashupatastra.gateway import (
    Effort,
    ModelRequest,
    ProviderUnavailable,
    SchemaViolation,
    Usage,
)

from .schemas import schema_for

STREAM_ABOVE_TOKENS = 16_000
"""Past this, a non-streaming request risks an HTTP timeout — the SDK refuses
some of them outright. Streaming and collecting the final message costs nothing
and removes the failure mode."""

_EFFORT = {Effort.LOW: "low", Effort.MEDIUM: "medium", Effort.HIGH: "high"}


class ClaudeProvider:
    """Shared request construction. Subclasses supply a client and a model id."""

    name = "claude"

    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self.model = model

    def complete(self, prompt: str, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        schema = schema_for(request.schema_name)
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": request.instructions,
            "messages": [{"role": "user", "content": prompt}],
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": _EFFORT[request.effort],
                "format": {"type": "json_schema", "schema": schema},
            },
        }

        try:
            if request.max_tokens > STREAM_ABOVE_TOKENS:
                with self._client.messages.stream(**params) as stream:
                    message = stream.get_final_message()
            else:
                message = self._client.messages.create(**params)
        except Exception as error:  # noqa: BLE001 — mapped to the gateway's vocabulary below
            raise self._translate(error) from error

        return self._read(message, request)

    # -- response handling ----------------------------------------------------

    def _read(self, message: Any, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        usage = self._usage(message)

        stop = getattr(message, "stop_reason", None)
        if stop == "refusal":
            # A declined request is a successful HTTP response with empty or
            # partial content. Reading content[0] here would raise something
            # unrelated and send the caller looking in the wrong place.
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None)
            raise SchemaViolation(
                f"model declined the request (category={category}); "
                f"purpose={request.purpose}"
            )
        if stop == "max_tokens":
            raise SchemaViolation(
                f"response truncated at max_tokens={request.max_tokens}; "
                "the object is incomplete and must not be parsed as if whole"
            )

        text = next(
            (block.text for block in message.content if getattr(block, "type", None) == "text"),
            None,
        )
        if text is None:
            raise SchemaViolation("response contained no text block to decode")

        try:
            output = json.loads(text)
        except json.JSONDecodeError as error:
            raise SchemaViolation(f"response was not valid JSON: {error}") from error

        if not isinstance(output, dict):
            raise SchemaViolation(f"expected a JSON object, got {type(output).__name__}")

        self._check_required(output, schema_for(request.schema_name))
        return output, usage

    @staticmethod
    def _check_required(output: dict[str, Any], schema: dict[str, Any]) -> None:
        """A shallow required-keys check on top of server-side constraint.

        Belt and braces, deliberately: `output_config.format` already constrains
        the shape, but this module's whole purpose is that nothing downstream
        trusts an unvalidated field. Cheap enough to always run, and it catches
        the case where a provider silently ignores the format constraint.
        """
        missing = [key for key in schema.get("required", []) if key not in output]
        if missing:
            raise SchemaViolation(f"response missing required field(s): {', '.join(missing)}")

    @staticmethod
    def _usage(message: Any) -> Usage:
        raw = getattr(message, "usage", None)
        if raw is None:
            return Usage()
        return Usage(
            input_tokens=getattr(raw, "input_tokens", 0) or 0,
            output_tokens=getattr(raw, "output_tokens", 0) or 0,
            cached_input_tokens=getattr(raw, "cache_read_input_tokens", 0) or 0,
        )

    @staticmethod
    def _translate(error: Exception) -> Exception:
        """Map SDK exceptions into the gateway's vocabulary.

        Retryable transport conditions become `ProviderUnavailable`, which the
        gateway retries and which trips the circuit breaker. A malformed or
        rejected request becomes `SchemaViolation`, which is retried but must not
        take a healthy provider offline. Matching on class name rather than
        importing the SDK's exception tree keeps this readable when only one
        provider's package is installed.
        """
        name = type(error).__name__
        retryable = {
            "APIConnectionError",
            "APITimeoutError",
            "RateLimitError",
            "InternalServerError",
            "APIStatusError",
        }
        if name in retryable:
            status = getattr(error, "status_code", None)
            if status is not None and 400 <= status < 500 and status not in (408, 409, 429):
                return SchemaViolation(f"request rejected ({status}): {error}")
            return ProviderUnavailable(f"{name}: {error}")
        if name in {"BadRequestError", "UnprocessableEntityError"}:
            return SchemaViolation(f"{name}: {error}")
        if name in {"AuthenticationError", "PermissionDeniedError", "NotFoundError"}:
            # Not retryable and not a schema problem — a misconfiguration. Raised
            # as unavailable so it escalates rather than looking like model noise.
            return ProviderUnavailable(f"{name}: {error}")
        return ProviderUnavailable(f"{name}: {error}")


class AnthropicProvider(ClaudeProvider):
    """The direct API. Credentials resolve from the environment."""

    name = "anthropic"

    def __init__(self, model: str) -> None:
        import anthropic

        super().__init__(anthropic.Anthropic(), model)


class BedrockProvider(ClaudeProvider):
    """Bedrock — the primary target (the Platform ADR).

    Uses the Mantle client, which speaks the Messages API, rather than the legacy
    `bedrock-runtime` InvokeModel path. Credentials come from the environment,
    which on EKS means IRSA — never a long-lived key (docs/SECURITY.md).
    """

    name = "bedrock"

    def __init__(self, model: str, region: str) -> None:
        from anthropic import AnthropicBedrockMantle

        super().__init__(AnthropicBedrockMantle(aws_region=region), bedrock_model_id(model))


def bedrock_model_id(model: str) -> str:
    """Bedrock names the same models with an `anthropic.` prefix.

    Applied here rather than stored prefixed in configuration, so one setting
    names the model and switching provider does not require editing it — which
    is the difference between provider-neutral and provider-neutral-in-principle.
    """
    return model if model.startswith("anthropic.") else f"anthropic.{model}"
