"""RP-27: Sati-RCA's hypotheses pass the Reasoner's citation check, and a fabricated ref does not."""

from __future__ import annotations

import pandas as pd
import pytest
from pashupatastra.gateway import Gateway
from pashupatastra.kaal.generator import incident
from pashupatastra.reasoning import Reasoner, SuppressionReason

from sati.rca import kaal, model
from sati.rca.cite import SatiRCAProvider


@pytest.fixture(scope="module")
def ranker():
    frames = [kaal.featurise(inc)[0] for inc in (incident(21, i) for i in range(600)) if inc.label["root_service"]]
    return model.train_ranker(pd.concat(frames, ignore_index=True), kaal.FEATURES)


def _incidents(n: int = 40):
    return [inc for inc in (incident(22, i) for i in range(n * 2)) if inc.label["root_service"]][:n]


def test_every_sati_rca_hypothesis_survives_citation_verification(ranker):
    admitted = 0
    for inc in _incidents():
        result = Reasoner(Gateway(SatiRCAProvider(ranker, inc))).analyse(inc.id, inc.events)
        assert not [s for s in result.suppressed if s.reason is SuppressionReason.FABRICATED_CITATION]
        ids = {e.id for e in inc.events}
        for h in result.hypotheses:
            assert h.evidence and set(h.evidence) <= ids
        admitted += len(result.hypotheses)
    assert admitted > 0


def test_the_top_hypothesis_names_the_true_root_most_of_the_time(ranker):
    incidents = _incidents()
    right = 0
    for inc in incidents:
        result = Reasoner(Gateway(SatiRCAProvider(ranker, inc))).analyse(inc.id, inc.events)
        right += bool(result.hypotheses) and result.hypotheses[0].statement.startswith(str(inc.label["root_service"]) + " ")
    assert right / len(incidents) > 0.8


class Tampered(SatiRCAProvider):
    """The same provider, but it adds a ref it was never shown."""

    def complete(self, prompt, request):
        out, usage = super().complete(prompt, request)
        for h in out["hypotheses"]:
            h["evidence_refs"] = [*h["evidence_refs"], "evt-not-shown"]
        return out, usage


def test_a_fabricated_ref_suppresses_the_hypothesis(ranker):
    inc = _incidents(1)[0]
    result = Reasoner(Gateway(Tampered(ranker, inc))).analyse(inc.id, inc.events)
    assert result.hypotheses == []
    assert any(s.reason is SuppressionReason.FABRICATED_CITATION and "evt-not-shown" in s.detail
               for s in result.suppressed)
