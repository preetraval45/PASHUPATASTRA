"""R75: the matrix says what the library observed, in ATT&CK's order, and
says nothing about what it did not."""

from __future__ import annotations

from datetime import datetime

from pashupatastra.attack import TACTICS, matrix
from pashupatastra.events import EntityKind, EntityRef
from pashupatastra.incidents import (
    AttackTechnique,
    CausalLink,
    Hypothesis,
    Incident,
    IncidentSeverity,
)

NOW = datetime(2026, 9, 13, 12, 0).astimezone()
HOST = EntityRef(kind=EntityKind.HOST, id="ws-1", name="ws-1")


def step(technique: AttackTechnique | None) -> CausalLink:
    return CausalLink(entity=HOST, transition="did a thing", evidence=["a"], attack_technique=technique)


def incident(id: str, *steps: CausalLink) -> Incident:
    return Incident(
        id=id,
        severity=IncidentSeverity.HIGH,
        opened_at=NOW,
        affected_entities=[HOST],
        hypotheses=[Hypothesis(statement="s", confidence=0.9, evidence=["a"])],
        causal_chain=list(steps),
    )


BEACON = AttackTechnique(id="T1071.001", name="Web Protocols", tactic="Command and Control")
SMB = AttackTechnique(id="T1021.002", name="SMB/Windows Admin Shares", tactic="Lateral Movement")
TASK = AttackTechnique(id="T1053.005", name="Scheduled Task", tactic="Persistence")


def test_every_column_is_a_tactic_in_attacks_own_order() -> None:
    result = matrix([])
    assert [c.tactic for c in result.columns] == list(TACTICS)
    assert len(TACTICS) == 14


def test_a_filled_cell_links_to_the_exact_step_that_fills_it() -> None:
    result = matrix([incident("INC-1", step(BEACON), step(SMB), step(TASK))])
    cell = next(c for col in result.columns for c in col.techniques if c.id == "T1021.002")
    assert cell.refs == ["INC-1#chain-1"]
    assert cell.incidents == ["INC-1"]
    assert cell.url == "https://attack.mitre.org/techniques/T1021/002/"


def test_the_same_technique_in_two_incidents_is_one_cell_with_two_refs() -> None:
    result = matrix([incident("INC-1", step(TASK)), incident("INC-2", step(BEACON), step(TASK))])
    cell = next(c for col in result.columns for c in col.techniques if c.id == "T1053.005")
    assert cell.refs == ["INC-1#chain-0", "INC-2#chain-1"]
    assert cell.incidents == ["INC-1", "INC-2"]
    assert result.technique_count == 2


def test_an_empty_tactic_is_not_observed_and_still_present() -> None:
    """The page needs the empty columns to say *not observed* — a matrix that
    omitted them would read as coverage of everything it showed."""
    result = matrix([incident("INC-1", step(BEACON))])
    assert result.observed_tactics == ["Command and Control"]
    assert "Impact" in result.unobserved_tactics
    assert len(result.columns) == 14


def test_a_step_without_a_technique_is_neither_counted_nor_invented() -> None:
    result = matrix([incident("INC-1", step(None), step(BEACON))])
    assert result.step_count == 1
    assert result.technique_count == 1


def test_a_tactic_outside_attacks_fourteen_is_shown_and_marked_not_filed_elsewhere() -> None:
    odd = AttackTechnique(id="T9999", name="Made Up", tactic="Mischief")
    result = matrix([incident("INC-1", step(odd))])
    extra = result.columns[-1]
    assert extra.tactic == "Mischief" and extra.known is False and extra.observed
    assert "Mischief" not in result.unobserved_tactics
    assert len(result.columns) == 15
