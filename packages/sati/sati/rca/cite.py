"""Citations from Sati-RCA (RP-27): a ranked root cause that cites the events behind it.

Rule 1: no claim without provenance. Katyayani's ranker, served as an AI
Gateway provider (rule 5), answers the Reasoner's `hypothesis_v1` request with
the top-ranked services as hypotheses. Each one cites the **event ids** its
features were computed from, and only ids that were in the evidence it was
shown.

The Reasoner then does what it does for any model: a hypothesis citing a ref
it never showed is suppressed whole (`SuppressionReason.FABRICATED_CITATION`).
Nothing about Sati-RCA is exempt from that check; the tests drive real Kaal
incidents through the real Reasoner and Gateway.

Done-when (RP-27) is on the 20 labelled incidents, which do not exist yet
(RP-13). Until then, this is exercised on Kaal incidents.
"""

from __future__ import annotations

from typing import Any

import lightgbm as lgb
import numpy as np
from pashupatastra.gateway import ModelRequest, Usage
from pashupatastra.kaal.generator import Incident

from sati.rca import kaal

MAX_REFS = 6


class SatiRCAProvider:
    """A Gateway provider for one incident: ranks its services and cites events."""

    name = "sati"

    def __init__(self, ranker: lgb.Booster, inc: Incident, fault_head: lgb.Booster | None = None,
                 fault_classes: list[str] | None = None, top: int = 2,
                 model: str = "sati-katyayani-kaal-v0") -> None:
        self.ranker, self.inc, self.top = ranker, inc, top
        self.fault_head, self.fault_classes = fault_head, fault_classes or []
        self.model = model

    def complete(self, prompt: str, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        shown = {item.ref for item in request.evidence}
        table, provenance = kaal.featurise(self.inc)
        scores = self.ranker.predict(table[kaal.FEATURES])
        order = np.argsort(-scores)
        weights = np.exp(scores - scores.max())
        probs = weights / weights.sum()
        hypotheses = []
        for i in order[: self.top]:
            service = str(table.iloc[i]["service"])
            refs = [ref for ref in provenance.get(service, []) if ref in shown][:MAX_REFS]
            if not refs:
                continue  # nothing it can cite, so it claims nothing about this service
            fault = ""
            if self.fault_head is not None and self.fault_classes:
                fault = self.fault_classes[int(self.fault_head.predict(table.iloc[[i]][kaal.FEATURES]).argmax())]
            statement = f"{service} is the root cause" + (f" ({fault.replace('_', ' ')})" if fault else "")
            hypotheses.append({"statement": statement, "confidence": round(float(probs[i]), 4), "evidence_refs": refs})
        return {"hypotheses": hypotheses}, Usage(input_tokens=0, output_tokens=0)
