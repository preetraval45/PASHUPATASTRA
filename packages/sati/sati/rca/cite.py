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

**Which events are cited first** follows what drove the ranking. LightGBM's
exact per-feature contributions (TreeSHAP, `predict(..., pred_contrib=True)`)
say how much each feature pushed this service's score up; each event is scored
by the positive contributions of the features it fed (the strongest anomaly
feeds `peak`, the earliest `onset_*`, every anomaly `n_anomalous`, a log
`error_log`, a deploy just before onset `deploy_before`), and the
`MAX_REFS` most influential are cited, strongest first. Before 2 Nov 2026 it
cited every event behind the service in arrival order, capped at six.

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


def event_features(inc: Incident) -> dict[str, dict[str, set[str]]]:
    """For each service, which of its features each cited event fed, mirroring `kaal.featurise`."""
    out: dict[str, dict[str, set[str]]] = {}
    anomalies: dict[str, list] = {}
    for e in inc.events:
        p = e.payload
        sigma = getattr(p, "deviation_sigma", None)
        roles = out.setdefault(e.entity_ref.id, {})
        if sigma is not None and abs(sigma) >= kaal.ANOMALOUS:
            anomalies.setdefault(e.entity_ref.id, []).append(e)
            roles[e.id] = {"n_anomalous"} | ({"own_metric"} if p.name not in kaal.RESOURCE else set())
        elif p.kind == "log":
            roles[e.id] = {"error_log"}
        elif p.kind == "deployment":
            roles[e.id] = {"deploy_before"}
    for service, events in anomalies.items():
        strongest = max(events, key=lambda e: abs(e.payload.deviation_sigma))
        earliest = min(events, key=lambda e: e.occurred_at)
        out[service][strongest.id].add("peak")
        out[service][earliest.id] |= {"onset_min", "onset_rank"}
    return out


def ranked_refs(refs: list[str], roles: dict[str, set[str]], contribution: dict[str, float]) -> list[str]:
    """The refs ordered by how much the features they fed pushed the score up, strongest first; ties keep
    their original order. Features that pushed it down count for nothing: a citation supports a claim."""
    def weight(ref: str) -> float:
        return sum(max(0.0, contribution.get(f, 0.0)) for f in roles.get(ref, ()))

    return sorted(refs, key=lambda ref: -weight(ref))


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
        contributions = self.ranker.predict(table[kaal.FEATURES], pred_contrib=True)
        roles = event_features(self.inc)
        order = np.argsort(-scores)
        weights = np.exp(scores - scores.max())
        probs = weights / weights.sum()
        hypotheses = []
        for i in order[: self.top]:
            service = str(table.iloc[i]["service"])
            contribution = dict(zip(kaal.FEATURES, contributions[i][: len(kaal.FEATURES)], strict=True))
            refs = ranked_refs([ref for ref in provenance.get(service, []) if ref in shown],
                               roles.get(service, {}), contribution)[:MAX_REFS]
            if not refs:
                continue  # nothing it can cite, so it claims nothing about this service
            fault = ""
            if self.fault_head is not None and self.fault_classes:
                fault = self.fault_classes[int(self.fault_head.predict(table.iloc[[i]][kaal.FEATURES]).argmax())]
            statement = f"{service} is the root cause" + (f" ({fault.replace('_', ' ')})" if fault else "")
            hypotheses.append({"statement": statement, "confidence": round(float(probs[i]), 4), "evidence_refs": refs})
        return {"hypotheses": hypotheses}, Usage(input_tokens=0, output_tokens=0)
