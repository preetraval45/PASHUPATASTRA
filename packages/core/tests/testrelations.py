"""R69: two incidents are related when they touched the same things, and not
when they merely happened near each other.

The pair with no overlap is the case that matters most. A relation feature that
has never been shown a "no" is a feature nobody has tested — every plausible
implementation says yes to something.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pashupatastra import relate
from pashupatastra.events import EntityKind, EntityRef
from pashupatastra.incidents import CausalLink, Incident, IncidentSeverity

NOW = datetime(2026, 8, 25, 12, 0).astimezone()


def entity(kind: EntityKind, name: str) -> EntityRef:
    return EntityRef(kind=kind, id=name, name=name)


def an_incident(
    incident_id: str,
    chain: list[tuple[EntityRef, str, list[str]]],
    opened_at: datetime | None = None,
    affected: list[EntityRef] | None = None,
) -> Incident:
    return Incident(
        id=incident_id,
        severity=IncidentSeverity.HIGH,
        opened_at=opened_at or NOW,
        affected_entities=affected or [ref for ref, _, _ in chain],
        causal_chain=[
            CausalLink(entity=ref, transition=transition, evidence=evidence)
            for ref, transition, evidence in chain
        ],
    )


def test_a_shared_host_is_a_relation_and_cites_both_sides() -> None:
    host = entity(EntityKind.HOST, "ws-0148")
    left = an_incident("INC-1", [(host, "beaconed outbound", ["evt-a"])])
    right = an_incident("INC-2", [(host, "ran a scheduled task", ["evt-b"])])

    relation = relate(left, right)

    assert relation.related
    overlap = relation.overlaps[0]
    assert overlap.value == "host:ws-0148"
    assert "INC-1#chain-0" in overlap.left_refs and "evt-a" in overlap.left_refs
    assert "INC-2#chain-0" in overlap.right_refs and "evt-b" in overlap.right_refs
    assert relation.refs, "a relation with nothing to cite is not an answer"


def test_a_pair_with_no_overlap_is_no_relation() -> None:
    """The case the task names, and the one every implementation gets wrong by
    finding a resemblance and calling it a link."""
    left = an_incident(
        "INC-1", [(entity(EntityKind.ACCOUNT, "j.rivera"), "signed in", ["evt-a"])]
    )
    right = an_incident(
        "INC-2", [(entity(EntityKind.ACCOUNT, "m.okafor"), "signed in", ["evt-b"])]
    )

    relation = relate(left, right)

    assert not relation.related
    assert relation.overlaps == ()
    assert relation.refs == []
    assert "No relation found" in relation.describe()


def test_a_no_says_what_it_looked_for() -> None:
    """A bare "no relation" is indistinguishable from not having looked."""
    left = an_incident("INC-1", [(entity(EntityKind.HOST, "a"), "x", ["evt-a"])])
    right = an_incident("INC-2", [(entity(EntityKind.HOST, "b"), "y", ["evt-b"])])

    described = relate(left, right).describe()

    assert "entities against" in described
    assert "indicators against" in described


def test_happening_at_the_same_moment_is_not_a_relation() -> None:
    """Two incidents in the same minute are two incidents. The correlator says
    so where it groups events, and this must not disagree with it."""
    left = an_incident("INC-1", [(entity(EntityKind.HOST, "a"), "x", ["evt-a"])])
    right = an_incident("INC-2", [(entity(EntityKind.HOST, "b"), "y", ["evt-b"])])

    relation = relate(left, right)

    assert relation.seconds_apart == 0.0
    assert not relation.related, "simultaneity is a coincidence until something overlaps"


def test_the_interval_is_reported_either_way() -> None:
    host = entity(EntityKind.HOST, "ws-0148")
    left = an_incident("INC-1", [(host, "x", ["evt-a"])])
    right = an_incident("INC-2", [(host, "y", ["evt-b"])], opened_at=NOW + timedelta(hours=3))

    assert "3.0 hours apart" in relate(left, right).describe()


def test_an_overlap_neither_side_can_cite_is_not_asserted() -> None:
    """An entity listed in `affected_entities` and established by nothing is a
    claim without a citation. Counting it would let the answer assert a link a
    reader cannot finish checking."""
    ghost = entity(EntityKind.SERVICE, "shared-thing")
    left = an_incident(
        "INC-1",
        [(entity(EntityKind.HOST, "a"), "x", ["evt-a"])],
        affected=[entity(EntityKind.HOST, "a"), ghost],
    )
    right = an_incident(
        "INC-2",
        [(entity(EntityKind.HOST, "b"), "y", ["evt-b"])],
        affected=[entity(EntityKind.HOST, "b"), ghost],
    )

    relation = relate(left, right)

    assert not relation.related
    assert [overlap.value for overlap in relation.uncited] == ["service:shared-thing"]
    assert "could not be traced" in relation.describe()


def test_an_overlap_only_one_side_can_cite_is_not_asserted() -> None:
    """Citable on one side says the entity is in one incident and, somewhere, in
    the other — a claim a reader cannot finish checking."""
    host = entity(EntityKind.HOST, "ws-0148")
    left = an_incident("INC-1", [(host, "beaconed", ["evt-a"])])
    right = an_incident("INC-2", [(entity(EntityKind.HOST, "b"), "y", ["evt-b"])],
                        affected=[entity(EntityKind.HOST, "b"), host])

    relation = relate(left, right)

    assert not relation.related
    assert [overlap.value for overlap in relation.uncited] == ["host:ws-0148"]


def test_a_shared_indicator_relates_two_incidents_that_share_no_entity() -> None:
    """The case entity overlap misses: two different hosts talking to one
    address. The caller supplies the mapping because the events live in a store
    and this package has none."""
    left = an_incident("INC-1", [(entity(EntityKind.HOST, "a"), "x", ["evt-a"])])
    right = an_incident("INC-2", [(entity(EntityKind.HOST, "b"), "y", ["evt-b"])])

    relation = relate(
        left,
        right,
        left_indicators={"198.51.100.74": ("evt-a",)},
        right_indicators={"198.51.100.74": ("evt-b",)},
    )

    assert relation.related
    assert relation.overlaps[0].kind == "indicator"
    assert relation.refs == ["evt-a", "evt-b"]


def test_an_incident_is_not_related_to_itself() -> None:
    """Not a relation, a mistake — and one that would otherwise report every
    entity as shared and look like the strongest link on the site."""
    left = an_incident("INC-1", [(entity(EntityKind.HOST, "a"), "x", ["evt-a"])])

    with pytest.raises(ValueError):
        relate(left, left)
