"""R73: argue the other side, and be capable of losing.

The test this module exists for is `test_the_alternative_wins_when_nothing_rules
_it_out`. An implementation that reads the confidence numbers passes every other
test here and fails that one, and it would be wrong in the direction that
matters — always confirming the diagnosis it was asked to challenge.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from pashupatastra.contest import ContestRefused, Verdict, contest
from pashupatastra.events import EntityKind, EntityRef
from pashupatastra.incidents import (
    CausalLink,
    Hypothesis,
    Incident,
    IncidentSeverity,
)

NOW = datetime(2026, 9, 4, 12, 0).astimezone()
HOST = EntityRef(kind=EntityKind.HOST, id="ws-0148", name="ws-0148")

# The beaconing shape: the leader rests on four records, the rival on one of
# them, and three records contradict the rival.
LEADER = Hypothesis(
    statement="Implant beaconing to a C2 host, then moving laterally.",
    confidence=0.86,
    evidence=["a", "b", "c", "d"],
)
RIVAL = Hypothesis(
    statement="A backup agent is running on its schedule.",
    confidence=0.09,
    evidence=["b"],
    contradicted_by=["e", "c"],
)

ALL = {"a", "b", "c", "d", "e"}


def an_incident(hypotheses: list[Hypothesis] | None = None) -> Incident:
    return Incident(
        id="INC-2026-0903",
        severity=IncidentSeverity.CRITICAL,
        opened_at=NOW,
        affected_entities=[HOST],
        hypotheses=hypotheses if hypotheses is not None else [LEADER, RIVAL],
        causal_chain=[CausalLink(entity=HOST, transition="beaconed", evidence=["a"])],
    )


# --- the diagnosis survives ----------------------------------------------------


def test_the_rejection_cites_the_records_that_rule_the_rival_out() -> None:
    """R73's second clause."""
    result = contest(an_incident(), ALL)
    assert result.verdict is Verdict.UPHELD
    assert result.ruled_out_by == ("e", "c")
    assert "ruled out by e, c" in result.describe()


def test_the_rival_is_argued_before_it_is_answered() -> None:
    """"Argue the other side" means stating its case, not only its defeat."""
    said = contest(an_incident(), ALL).describe()
    assert said.startswith("The case for the alternative")
    assert "backup agent" in said
    assert said.index("backup agent") < said.index("ruled out")


def test_the_shared_observation_is_named() -> None:
    """What makes the two answers to one question rather than two findings."""
    result = contest(an_incident(), ALL)
    assert result.shared == ("b",)
    assert "It explains b" in result.describe()


# --- the alternative wins ------------------------------------------------------


def test_the_alternative_wins_when_nothing_rules_it_out() -> None:
    """R73's third clause, and the reason this module is not a narrator.

    An implementation reading the confidence numbers reports 0.86 against 0.09
    and calls the alternative rejected. But the incident asserting its own
    diagnosis is likelier is the claim under examination, not evidence for it.
    """
    rival = Hypothesis(
        statement="A backup agent is running on its schedule.",
        confidence=0.09,
        evidence=["b"],
        contradicted_by=[],
    )
    result = contest(an_incident([LEADER, rival]), ALL)

    assert result.verdict is Verdict.UNREFUTED
    assert result.ruled_out_by == ()
    assert "Nothing stored rules it out" in result.describe()
    assert "ranked below" in result.describe()


def test_a_rejection_that_resolves_to_nothing_does_not_count_as_one() -> None:
    """The rejection is claimed and uncheckable, which is the same failure as
    naming no reason at all — R68 collapses the two for the same reason."""
    result = contest(an_incident(), resolvable={"a", "b", "c", "d"} - {"c"})

    assert result.verdict is Verdict.UNREFUTED
    assert set(result.unresolved_rejection) == {"e", "c"}
    assert "resolve to nothing and are not counted" in result.describe()


def test_a_large_confidence_gap_never_decides_it() -> None:
    """The property, stated directly: the verdict is a function of the records
    contradicting the rival and of nothing else."""
    for confidence in (0.01, 0.4, 0.49):
        rival = Hypothesis(
            statement="A backup agent is running on its schedule.",
            confidence=confidence,
            evidence=["b"],
        )
        assert contest(an_incident([LEADER, rival]), ALL).verdict is Verdict.UNREFUTED


def test_the_rival_is_credited_with_what_the_diagnosis_does_not_explain() -> None:
    """The point a confident diagnosis is least likely to make about its own
    alternative."""
    rival = Hypothesis(
        statement="A backup agent is running on its schedule.",
        confidence=0.09,
        evidence=["b", "f"],
    )
    result = contest(an_incident([LEADER, rival]), ALL | {"f"})

    assert result.unexplained_by_leader == ("f",)
    assert "also accounts for f" in result.describe()


# --- what is refused -----------------------------------------------------------


def test_a_restatement_is_not_a_rival() -> None:
    """Two hypotheses on the same records with nothing to separate them are one
    claim written twice, and adjudicating between them is theatre."""
    twin = Hypothesis(
        statement="The host is beaconing to a command-and-control server.",
        confidence=0.5,
        evidence=["a", "b", "c", "d"],
    )
    with pytest.raises(ContestRefused, match="one claim written twice"):
        contest(an_incident([LEADER, twin]), ALL)


def test_an_alternative_sharing_no_observation_is_not_competing() -> None:
    """It answers a different question. Staging a contest between them would
    produce a confident verdict about nothing."""
    unrelated = Hypothesis(
        statement="A certificate expired on an unrelated service.",
        confidence=0.2,
        evidence=["f"],
    )
    with pytest.raises(ContestRefused, match="different question"):
        contest(an_incident([LEADER, unrelated]), ALL | {"f"})


def test_one_hypothesis_has_no_other_side() -> None:
    with pytest.raises(ContestRefused, match="no other side"):
        contest(an_incident([LEADER]), ALL)


def test_an_ungrounded_diagnosis_is_not_adjudicated() -> None:
    """A contest neither side can win is not worth staging, and reporting the
    alternative as beaten by an unsupported diagnosis would be worse."""
    leader = Hypothesis(statement="Something happened.", confidence=0.9, evidence=["gone"])
    with pytest.raises(ContestRefused, match="none of which resolves"):
        contest(an_incident([leader, RIVAL]), ALL)


def test_an_ungrounded_rival_is_passed_over_and_the_reason_given() -> None:
    """It is skipped rather than argued: a rival resting on records that do not
    exist has no case to state."""
    ghost = Hypothesis(statement="A ghost did it.", confidence=0.5, evidence=["nowhere"])
    with pytest.raises(ContestRefused, match="none of which resolves"):
        contest(an_incident([LEADER, ghost]), ALL)


def test_the_strongest_qualifying_rival_is_the_one_argued() -> None:
    """A weaker but real rival is not passed over for a stronger restatement."""
    twin = Hypothesis(
        statement="Beaconing to a C2 host.", confidence=0.5, evidence=["a", "b", "c", "d"]
    )
    result = contest(an_incident([LEADER, twin, RIVAL]), ALL)
    assert result.rival.statement.startswith("A backup agent")


# --- what it rests on ----------------------------------------------------------


def test_the_contest_cites_the_records_it_used() -> None:
    result = contest(an_incident(), ALL)
    assert set(result.refs) == {"e", "c", "b"}


def test_evidence_that_does_not_resolve_is_kept_on_the_case() -> None:
    """A hypothesis resting on three records, two of which do not exist, is
    weaker than one resting on one that does."""
    result = contest(an_incident(), resolvable={"a", "b", "c", "e"})
    assert result.leader.supported_by == ("a", "b", "c")
    assert result.leader.uncited == ("d",)


def test_an_unrefuted_alternative_is_an_open_question_not_a_conclusion() -> None:
    """The distinction is easy to lose and matters: this never says the rival is
    right, only that the diagnosis has not earned its place over it."""
    rival = Hypothesis(statement="A backup agent.", confidence=0.09, evidence=["b"])
    said = contest(an_incident([LEADER, rival]), ALL).describe()
    assert "has not been beaten" in said
    assert "is correct" not in said
