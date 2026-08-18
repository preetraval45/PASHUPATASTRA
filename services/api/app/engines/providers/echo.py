"""A deterministic provider that calls no model.

Two jobs. It lets the API run end to end on a laptop with no credentials, so the
gateway path is exercised by the ordinary test suite rather than only in an
environment that can spend money. And it gives the evaluation harness a fixed
control arm: a run whose output cannot vary isolates changes in the harness from
changes in the model.

It is deliberately *unhelpful* — it returns a well-formed object with no
hypotheses rather than a plausible-looking answer. A stub that invents findings
is worse than no stub, because a demo built on it looks like a working system.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pashupatastra.gateway import ModelRequest, SchemaViolation, Usage

from .schemas import schema_for


class EchoProvider:
    """Returns the minimum object each schema allows, and cites nothing."""

    name = "echo"
    model = "echo-0"

    def complete(self, prompt: str, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        schema = schema_for(request.schema_name)
        refs = [item.ref for item in request.evidence]

        match request.schema_name:
            case "hypothesis_v1":
                # No hypotheses at all. An empty list is honest; a fabricated one
                # would be indistinguishable from a real finding downstream.
                output: dict[str, Any] = {"hypotheses": []}
            case "summary_v1":
                output = {
                    "summary": "No model configured; this is the deterministic stub provider.",
                    "evidence_refs": refs,
                }
            case "injection_report_v1":
                output = {"instructions_found": False, "evidence_refs": refs}
            case _:
                raise SchemaViolation(
                    f"echo provider has no fixture for schema {request.schema_name!r}"
                )

        missing = [key for key in schema.get("required", []) if key not in output]
        if missing:  # pragma: no cover — guards the fixtures against schema drift
            raise SchemaViolation(f"echo fixture for {request.schema_name} lacks {missing}")

        # Usage is derived from the prompt so accounting has something stable and
        # non-zero to exercise, and so two identical runs report identical cost.
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        return output, Usage(input_tokens=len(prompt) // 4, output_tokens=digest[0] % 32)
