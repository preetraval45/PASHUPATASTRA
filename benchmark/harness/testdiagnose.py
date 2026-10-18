"""RP-14: the diagnosis harness scores any diagnoser the same way.

Done-when: a fake diagnoser registered here is scored correctly. Three fakes —
always right, always abstaining, and confidently wrong with invented citations —
pin every reported number.
"""

from __future__ import annotations

import pytest

from benchmark.harness.diagnose import Case, Diagnosis, StubRefused, refuse_stub, score

CASES = [
    Case(
        id=f"C-{i}",
        evidence=(("sig-1", "pool saturation 0.97"), ("sig-2", "deploy v4.21")),
        options=("pool_saturation", "dns_failure", "disk_full", "cert_expiry"),
        correct=("pool_saturation", "dns_failure", "disk_full", "cert_expiry")[i % 4],
    )
    for i in range(8)
]


class Perfect:
    name = "fake:perfect"

    def diagnose(self, case):
        others = tuple(o for o in case.options if o != case.correct)
        return Diagnosis(ranked=(case.correct, *others), evidence_refs=("sig-1",))


class SecondBest:
    name = "fake:second"

    def diagnose(self, case):
        others = tuple(o for o in case.options if o != case.correct)
        return Diagnosis(ranked=(others[0], case.correct, others[1]), evidence_refs=("sig-2",))


class Abstainer:
    name = "fake:abstain"

    def diagnose(self, case):
        return Diagnosis(abstain=True)


class Fabricator:
    name = "fake:fabricator"

    def diagnose(self, case):
        return Diagnosis(ranked=("disk_full",), evidence_refs=("sig-99",))


class Broken:
    name = "fake:broken"

    def diagnose(self, case):
        return Diagnosis(error="provider unavailable")


def test_a_perfect_diagnoser_scores_one_everywhere():
    r = score(Perfect(), CASES)
    assert (r.rca1, r.rca3, r.precision_when_answering, r.grounding, r.abstention_rate) == (1, 1, 1, 1, 0)
    assert r.rca1_ci[0] > 0.6


def test_second_place_is_a_top3_hit_and_a_top1_miss():
    r = score(SecondBest(), CASES)
    assert r.rca1 == 0 and r.rca3 == 1


def test_abstaining_is_counted_not_hidden():
    r = score(Abstainer(), CASES)
    assert r.abstention_rate == 1 and r.answered == 0
    assert r.rca1 == 0 and r.precision_when_answering is None


def test_invented_citations_are_not_grounded():
    r = score(Fabricator(), CASES)
    assert r.grounding == 0
    assert r.rca1 == 2 / 8  # disk_full is right on two of eight cases


def test_errors_are_kept_apart_from_wrong_answers():
    r = score(Broken(), CASES)
    assert r.errors == 8 and r.answered == 0 and r.abstention_rate == 0


def test_the_stub_is_refused():
    with pytest.raises(StubRefused):
        refuse_stub("echo-0")
    refuse_stub("qwen2.5:7b")
