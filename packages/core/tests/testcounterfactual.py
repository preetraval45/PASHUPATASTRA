"""R72: what acting earlier would have prevented, and what it would not.

The two tests that carry this module are the ones about restraint. Any
implementation counts the steps after the intervention and reports a number; the
ones worth having refuse to count a later step that never depended on the thing
removed, and refuse the question entirely when it asks what we would have done
with knowledge we did not have.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pashupatastra.counterfactual import (
    CounterfactualRefused,
    Intervention,
    counterfactual,
    moments,
)
from pashupatastra.events import EntityKind, EntityRef
from pashupatastra.incidents import (
    AttackTechnique,
    CausalLink,
    Hypothesis,
    Incident,
    IncidentSeverity,
)

NOON = datetime(2026, 9, 4, 12, 0).astimezone()

FLOW = "network_flow:ws-0148->198.51.100.74:8443"
HOST = "host:ws-0148"
TASK = "process:app-07/schtasks"


def _ref(key: str) -> EntityRef:
    kind, _, ident = key.partition(":")
    return EntityRef(kind=EntityKind(kind), id=ident, name=ident)


def at(minutes: int) -> datetime:
    return NOON + timedelta(minutes=minutes)


def an_incident(chain: list[CausalLink] | None = None) -> Incident:
    """The beaconing shape: a C2 flow, then SMB, then a scheduled task."""
    return Incident(
        id="INC-2026-0903",
        severity=IncidentSeverity.CRITICAL,
        opened_at=NOON,
        affected_entities=[_ref(HOST)],
        hypotheses=[
            Hypothesis(statement="Beaconing then lateral movement.", confidence=0.9, evidence=["a"])
        ],
        causal_chain=chain
        if chain is not None
        else [
            CausalLink(
                entity=_ref(FLOW),
                transition="outbound every 60s to a destination never seen before",
                evidence=["a"],
                attack_technique=AttackTechnique(
                    id="T1071.001", name="Web Protocols", tactic="Command and Control"
                ),
            ),
            CausalLink(
                entity=_ref(HOST),
                transition="SMB opened to two hosts never previously contacted",
                evidence=["c"],
            ),
            CausalLink(
                entity=_ref(TASK),
                transition="scheduled task created from a remote session",
                evidence=["d"],
            ),
        ],
    )


# a at noon, c at +80, d at +90 — the demo's ninety-minute gap.
OBSERVED = {"a": at(0), "c": at(80), "d": at(90)}
REACH = [HOST, TASK, "host:fs-02", "host:app-07"]


# --- the estimate --------------------------------------------------------------


def test_acting_early_pre_empts_the_steps_that_depended_on_it() -> None:
    result = counterfactual(
        an_incident(), Intervention(entity_key=FLOW, at=at(5)), OBSERVED, REACH
    )
    assert [s.index for s in result.prevented] == [1, 2]
    assert result.avoided_entities == [HOST, TASK]
    assert result.gap_seconds == 85 * 60


def test_the_answer_says_it_is_an_estimate_and_shows_its_working() -> None:
    """R72's second clause. A number without its basis is read as a measurement."""
    result = counterfactual(
        an_incident(), Intervention(entity_key=FLOW, at=at(5)), OBSERVED, REACH
    )
    assert result.describe().startswith("Estimate.")
    assert result.basis
    joined = " ".join(result.basis)
    assert "immediate and complete" in joined, "the efficacy assumption is not stated"
    assert "another route" in joined, "the adaptive-attacker assumption is not stated"
    assert "earliest record" in joined


def test_every_prevented_step_cites_the_records_that_dated_it() -> None:
    result = counterfactual(
        an_incident(), Intervention(entity_key=FLOW, at=at(5)), OBSERVED, REACH
    )
    for step in result.prevented:
        assert step.refs
    assert result.refs == ["c", "d"]


def test_acting_after_everything_prevents_nothing_and_says_so() -> None:
    result = counterfactual(
        an_incident(), Intervention(entity_key=FLOW, at=at(120)), OBSERVED, REACH
    )
    assert result.prevented == ()
    assert result.gap_seconds == 0.0
    assert "prevented nothing" in result.describe()
    assert len(result.already_happened) == 3


# --- later is not the same as caused by ----------------------------------------


def test_a_later_step_that_was_not_downstream_is_not_counted() -> None:
    """The failure this module exists to avoid. Counting everything after the
    intervention is post hoc reasoning wearing an estimate's clothes, and it
    inflates the one number the homepage's cost-of-the-gap framing rests on."""
    result = counterfactual(
        an_incident(),
        Intervention(entity_key=FLOW, at=at(5)),
        OBSERVED,
        # The task is downstream; the SMB host is not.
        reachable=[TASK],
    )
    assert [s.index for s in result.prevented] == [2]
    assert [s.index for s in result.unavoidable] == [1]
    assert HOST not in result.avoided_entities


def test_what_would_have_happened_anyway_is_reported_not_dropped() -> None:
    """An estimate that only shows its winnings is an advertisement."""
    result = counterfactual(
        an_incident(), Intervention(entity_key=FLOW, at=at(5)), OBSERVED, reachable=[]
    )
    assert result.prevented == ()
    assert len(result.unavoidable) == 2
    assert "would have happened regardless" in result.describe()


def test_the_avoided_set_comes_from_the_chain_not_from_the_reach() -> None:
    """Reachability says what could have been touched; the chain says what was.
    Reporting the larger credits the intervention with harm that never happened."""
    result = counterfactual(
        an_incident(), Intervention(entity_key=FLOW, at=at(5)), OBSERVED, REACH
    )
    assert "host:fs-02" in result.reach
    assert "host:fs-02" not in result.avoided_entities


# --- what is refused -----------------------------------------------------------


def test_acting_before_the_first_record_is_refused() -> None:
    """The constraint that separates an estimate from a wish. Asked what
    blocking the address an hour earlier would have saved, a system with no such
    rule answers with a large number no amount of faster operating could have
    delivered — the question is really "what if we had already known"."""
    with pytest.raises(CounterfactualRefused, match="clairvoyance"):
        counterfactual(
            an_incident(), Intervention(entity_key=FLOW, at=at(-30)), OBSERVED, REACH
        )


def test_acting_exactly_at_the_first_record_is_allowed() -> None:
    """The boundary is inclusive: the moment the observation lands is the first
    moment a response could have begun, and excluding it would make the fastest
    possible response unaskable."""
    result = counterfactual(
        an_incident(), Intervention(entity_key=FLOW, at=at(0)), OBSERVED, REACH
    )
    assert len(result.prevented) == 2
    assert result.earliest_defensible == at(0)


def test_an_entity_the_incident_never_recorded_is_refused() -> None:
    with pytest.raises(CounterfactualRefused, match="not on"):
        counterfactual(
            an_incident(), Intervention(entity_key="host:unrelated", at=at(5)), OBSERVED, REACH
        )


def test_an_incident_with_no_timeline_is_refused() -> None:
    """Without times there is no 'earlier' to reason about, and a module that
    answered anyway would be ordering steps by the sequence somebody typed."""
    with pytest.raises(CounterfactualRefused, match="no step"):
        counterfactual(an_incident(), Intervention(entity_key=FLOW, at=at(5)), {}, REACH)


def test_an_entity_present_but_untimed_is_refused() -> None:
    """The chain names it and nothing dates it, so there is no moment from which
    acting on it would have been possible."""
    with pytest.raises(CounterfactualRefused, match="nothing stored places"):
        counterfactual(
            an_incident(),
            Intervention(entity_key=FLOW, at=at(5)),
            {"c": at(80), "d": at(90)},
            REACH,
        )


# --- steps that cannot be placed -----------------------------------------------


def test_an_untimed_step_is_excluded_and_named() -> None:
    """Assumed early it inflates the estimate, assumed late it deflates it.
    Either is a thumb on the scale in a calculation that is entirely a
    comparison against one moment."""
    result = counterfactual(
        an_incident(),
        Intervention(entity_key=FLOW, at=at(5)),
        {"a": at(0), "c": at(80)},  # `d` resolves to nothing
        REACH,
    )
    assert [u.index for u in result.untimed] == [2]
    assert TASK not in result.avoided_entities
    assert any("could not be placed in time" in line for line in result.basis)


def test_a_step_is_dated_from_its_earliest_record() -> None:
    """Dating from the last confirming observation reports the intrusion as
    later than it was, which shortens every gap this module measures."""
    chain = [
        CausalLink(entity=_ref(FLOW), transition="beaconing", evidence=["a", "b"]),
        CausalLink(entity=_ref(HOST), transition="smb", evidence=["c"]),
    ]
    timeline = moments(an_incident(chain), {"a": at(0), "b": at(50), "c": at(80)})
    assert timeline[0].at == at(0)


def test_moments_lists_the_chain_in_time_order() -> None:
    timeline = moments(an_incident(), OBSERVED)
    assert [s.index for s in timeline] == [0, 1, 2]
    assert [s.at for s in timeline] == [at(0), at(80), at(90)]


def test_the_intervened_entitys_own_later_steps_count() -> None:
    """Removing a thing stops what it goes on to do, not only what depends on
    it — so a second step at the same entity is prevented even with no reach."""
    chain = [
        CausalLink(entity=_ref(FLOW), transition="first beacon", evidence=["a"]),
        CausalLink(entity=_ref(FLOW), transition="still beaconing", evidence=["c"]),
    ]
    result = counterfactual(
        an_incident(chain), Intervention(entity_key=FLOW, at=at(5)), OBSERVED, reachable=[]
    )
    assert len(result.prevented) == 1
    assert result.prevented[0].transition == "still beaconing"
