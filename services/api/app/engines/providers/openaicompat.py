"""A provider for any endpoint that speaks the OpenAI chat-completions shape.

One class rather than one per vendor, because Groq, Ollama, vLLM, LM Studio,
LocalAI and OpenRouter all expose the same three things this needs: a
`/chat/completions` route, `response_format` with a JSON schema, and `tools`.
Which one is in use is a base URL and a model id, not a code path.

No SDK. The wire format is a POST with a JSON body, and an SDK here would add a
dependency, a second retry policy competing with the gateway's, and a vendor
name in a module that exists precisely to avoid having one.

The API key is read from the environment at call time, never stored on the
instance and never logged. `available()` reports whether it is present so
`/health` can say `configured: false` instead of failing at the first question.
"""

from __future__ import annotations

import json
import os
from typing import Any

from pashupatastra.gateway import (
    ModelRequest,
    ProviderUnavailable,
    SchemaViolation,
    Usage,
)

from .schemas import schema_for

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_TIMEOUT = 60.0
USER_AGENT = "pashupatastra/0.1 (+https://pashupatastra.vercel.app)"


def _rejects_tools(error: Exception) -> bool:
    """Whether a failure means "this model has no tools" rather than an outage.

    Matched on the message because the wire gives nothing better: Ollama returns
    400 with `does not support tools`, and a 400 is otherwise a bad request that
    should not be retried.
    """
    text = str(error).lower()
    return "does not support tools" in text or "tools are not supported" in text


class OpenAICompatProvider:
    """Chat completions over HTTP, with strict JSON output and tool calls."""

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        api_key_env: str = "PASHU_MODEL_API_KEY",
        timeout: float = DEFAULT_TIMEOUT,
        requires_key: bool = True,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.requires_key = requires_key
        """False for a self-hosted endpoint. Ollama takes no key, and treating
        a missing one as "not configured" would leave the fallback permanently
        switched off for the deployment that needs it most."""

    @property
    def name(self) -> str:
        """Named for the endpoint, not the class.

        `/health` and every audit record carry this, and "openai-compat" would
        tell a reader nothing about which service actually answered.
        """
        host = self.base_url.split("//", 1)[-1].split("/", 1)[0]
        return host.removeprefix("api.").removesuffix(".com") or "openai-compat"

    def available(self) -> bool:
        return not self.requires_key or bool(os.environ.get(self.api_key_env))

    # --- the wire -----------------------------------------------------------

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        import urllib.error
        import urllib.request

        key = os.environ.get(self.api_key_env)
        if not key and self.requires_key:
            raise ProviderUnavailable(
                f"{self.api_key_env} is not set; no model is configured"
            )

        headers = {
            "content-type": "application/json",
            # Named explicitly. urllib sends `Python-urllib/3.x`, which sits on
            # enough blocklists that Groq's edge answers 403 (Cloudflare 1010)
            # before the request reaches the API — a failure that reads exactly
            # like a bad key.
            "user-agent": USER_AGENT,
        }
        if key:
            headers["authorization"] = f"Bearer {key}"

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                **headers,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:400]
            # Raised as unavailable rather than a bare error so the gateway's
            # circuit breaker counts it. A provider that is rate-limiting is
            # exactly the case the breaker exists for.
            raise ProviderUnavailable(f"{error.code} from {self.name}: {detail}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ProviderUnavailable(f"{self.name} unreachable: {error}") from error

    @staticmethod
    def _usage(payload: dict[str, Any]) -> Usage:
        usage = payload.get("usage") or {}
        return Usage(
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    # --- Provider -----------------------------------------------------------

    def complete(self, prompt: str, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        """One structured call, no tools. The `Provider` protocol's method.

        The whole prompt goes in as a system message. The gateway has already
        assembled it with the evidence fenced and labelled, and splitting it
        across roles here would put attacker-influenced text into a `user`
        message — which is the one role these models are trained to treat as
        coming from a person worth obeying.
        """
        schema = schema_for(request.schema_name)
        payload = self._post(
            {
                "model": self.model,
                "messages": [{"role": "system", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": request.schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
                "max_tokens": request.max_tokens,
                "temperature": 0,
            }
        )
        choice = (payload.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content")
        if not content:
            raise SchemaViolation(f"{self.name} returned no content")
        try:
            output = json.loads(content)
        except json.JSONDecodeError as error:
            raise SchemaViolation(f"{self.name} returned non-JSON: {content[:200]}") from error
        if not isinstance(output, dict):
            raise SchemaViolation(f"{self.name} returned {type(output).__name__}, not an object")
        return output, self._usage(payload)

    # --- tool calling -------------------------------------------------------

    supports_tools = True
    """Claimed up front, then corrected by the endpoint if it turns out to be
    false — see `_tools_rejected`."""

    _tools_rejected = False

    def converse(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        schema_name: str | None,
        max_tokens: int,
    ) -> tuple[dict[str, Any], Usage]:
        """One turn of a tool conversation. The loop itself lives in the gateway.

        Returns the raw assistant message so the caller can see whether it asked
        for a tool or produced an answer. Deliberately not parsed here: deciding
        what a tool call means is policy, and policy does not belong in the
        module that knows about HTTP.
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        if tools and not self._tools_rejected:
            body["tools"] = tools
        if schema_name is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema_for(schema_name),
                },
            }
        try:
            payload = self._post(body)
        except ProviderUnavailable as error:
            if "tools" not in body or not _rejects_tools(error):
                raise
            # The endpoint says this model has no tools. Remembered, so the rest
            # of the conversation stops asking, and answered from the evidence
            # already retrieved rather than failing.
            #
            # This is the case deterministic retrieval exists for. A design
            # where the model had to call a tool to see anything would have
            # nothing to say here; this one loses the ability to look further
            # and keeps the ability to answer.
            self._tools_rejected = True
            body.pop("tools")
            payload = self._post(body)

        choice = (payload.get("choices") or [{}])[0]
        return choice.get("message") or {}, self._usage(payload)
