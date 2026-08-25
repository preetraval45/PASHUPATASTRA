"""Whether two incidents are the same story, decided from what is stored.

No model participates. "Are these two related?" is a question about overlap —
the same host, the same account, the same address — and overlap is a set
intersection over records that already exist. Asking a model to judge it would
replace a checkable fact with a plausible sentence, which is the failure this
codebase is arranged against (the Grounding ADR).

**Resemblance is not relation, and this module refuses to conflate them.**
Smriti already answers "has something like this happened before" by similarity,
and marks the difference between a precedent and a text match for the same
reason. Two credential-stuffing incidents against different accounts look alike
and share nothing; that is a pattern, and saying so is Smriti's job. This module
answers the narrower question of whether the two touched the same things.

**Proximity in time is never evidence.** Two incidents in the same minute are
two incidents — the correlator says so where it groups events, and it would be
strange for this to disagree with it one layer up. The interval is reported
because an analyst wants it, and it can never make `related` true on its own.

**An overlap that cannot be cited is not asserted.** Both sides have to be able
to name a record — a causal-chain step, or an event id that step rests on. An
entity listed in `affected_entities` and established by nothing is a claim
without a citation, and this returns those separately rather than counting them.
The whole value of the answer is that a reader can go and check it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .incidents import Incident


@dataclass(frozen=True)
class Overlap:
    """One thing both incidents touched, and the records that say so."""

    kind: str
    """`entity` or `indicator`."""

    value: str
    left_refs: tuple[str, ...]
    right_refs: tuple[str, ...]

    @property
    def cited(self) -> bool:
        """Both sides name at least one record.

        Both, not either. An overlap citable on one side only says this entity
        is in one incident and, somewhere, in the other — which is the shape of
        a claim a reader cannot finish checking.
        """
        return bool(self.left_refs) and bool(self.right_refs)

    def describe(self) -> str:
        return (
            f"{self.value} — {', '.join(self.left_refs)} "
            f"and {', '.join(self.right_refs)}"
        )


@dataclass(frozen=True)
class Relation:
    """The comparison, including everything it looked at and found nothing in."""

    left: str
    right: str
    overlaps: tuple[Overlap, ...] = ()
    uncited: tuple[Overlap, ...] = ()
    """Things both incidents mention that neither can point at a record for.
    Reported so the answer can say what it declined to count, rather than
    quietly discarding it and looking more certain than it is."""

    seconds_apart: float = 0.0
    compared: tuple[str, ...] = field(default_factory=tuple)
    """What was actually compared. A "no" is only worth reading if it says what
    it looked for — otherwise it is indistinguishable from not having looked."""

    @property
    def related(self) -> bool:
        return bool(self.overlaps)

    @property
    def refs(self) -> list[str]:
        """Every record this relation rests on, for the answer to cite."""
        seen: list[str] = []
        for overlap in self.overlaps:
            for ref in (*overlap.left_refs, *overlap.right_refs):
                if ref not in seen:
                    seen.append(ref)
        return seen

    def describe(self) -> str:
        hours = self.seconds_apart / 3600
        gap = (
            f"{self.seconds_apart / 60:.0f} minutes apart"
            if abs(hours) < 1
            else f"{hours:.1f} hours apart"
        )
        if not self.related:
            found = "; ".join(self.compared)
            trailing = (
                f" {len(self.uncited)} mentioned on both sides could not be traced "
                "to a record on both, so they are not counted."
                if self.uncited
                else ""
            )
            return (
                f"No relation found between {self.left} and {self.right}. "
                f"Compared: {found}. They opened {gap}.{trailing}"
            )
        lines = "; ".join(overlap.describe() for overlap in self.overlaps)
        return (
            f"{self.left} and {self.right} share {len(self.overlaps)} thing(s): "
            f"{lines}. They opened {gap}."
        )


def _entity_refs(incident: Incident) -> dict[str, tuple[str, ...]]:
    """Every entity the incident touches, and the records that establish it.

    A causal-chain step is a record with a ref, and the event ids it rests on
    are records too, so both are offered — an analyst checking an overlap will
    want the step, and an automated check will want the events.
    """
    found: dict[str, list[str]] = {}
    for index, link in enumerate(incident.causal_chain):
        key = link.entity.key()
        refs = found.setdefault(key, [])
        refs.append(f"{incident.id}#chain-{index}")
        refs.extend(ref for ref in link.evidence if ref not in refs)
    # Listed but not established by a chain step. Kept with no refs rather than
    # dropped, so `uncited` can report it.
    for entity in incident.affected_entities:
        found.setdefault(entity.key(), [])
    return {key: tuple(refs) for key, refs in found.items()}


def relate(
    left: Incident,
    right: Incident,
    left_indicators: dict[str, tuple[str, ...]] | None = None,
    right_indicators: dict[str, tuple[str, ...]] | None = None,
) -> Relation:
    """Compare two incidents on what they touched.

    Indicators are passed in rather than read, because reading them means going
    to the store and this package does not have one — it has to run on a laptop
    with no cloud and no database. The caller maps indicator value to the event
    ids carrying it; everything else is derived from the incidents themselves.
    """
    if left.id == right.id:
        raise ValueError("an incident is not related to itself; that is the same incident")

    overlaps: list[Overlap] = []
    uncited: list[Overlap] = []

    left_entities = _entity_refs(left)
    right_entities = _entity_refs(right)
    for key in sorted(set(left_entities) & set(right_entities)):
        overlap = Overlap(
            kind="entity",
            value=key,
            left_refs=left_entities[key],
            right_refs=right_entities[key],
        )
        (overlaps if overlap.cited else uncited).append(overlap)

    left_indicators = left_indicators or {}
    right_indicators = right_indicators or {}
    for value in sorted(set(left_indicators) & set(right_indicators)):
        overlap = Overlap(
            kind="indicator",
            value=value,
            left_refs=tuple(left_indicators[value]),
            right_refs=tuple(right_indicators[value]),
        )
        (overlaps if overlap.cited else uncited).append(overlap)

    return Relation(
        left=left.id,
        right=right.id,
        overlaps=tuple(overlaps),
        uncited=tuple(uncited),
        seconds_apart=abs((left.opened_at - right.opened_at).total_seconds()),
        compared=(
            f"{len(left_entities)} entities against {len(right_entities)}",
            f"{len(left_indicators)} indicators against {len(right_indicators)}",
        ),
    )


__all__ = ["Overlap", "Relation", "relate"]
