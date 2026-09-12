"""What acting earlier would have prevented, computed from the stored chain.

*"What if we had blocked the ASN at 09:14 instead of 10:31?"* The answer is a
walk over two things this codebase already holds: the causal chain, placed in
time by the events each step cites, and the access edges saying what depends on
what. Nothing here is a judgement, and no model participates.

**Later is not the same as caused by, and this module refuses to conflate them.**
The tempting implementation counts everything after the intervention and reports
it as prevented. That is post hoc reasoning wearing an estimate's clothes, and it
inflates the one number the homepage's *cost of the gap* framing rests on. A step
is prevented only where it is both later than the intervention *and* reachable
from the entity the intervention removed, through edges that cite their own
evidence. `relations.py` makes the same refusal about time one layer up, and the
correlator's adjacency gate makes it one layer down; it would be strange for the
counterfactual to be the one place where "afterwards" means "because".

**An intervention cannot precede the evidence that would have justified it.**
This is the constraint that separates an estimate from a wish. Asked what
blocking the address at 09:14 would have saved, a system with no such rule
happily answers — and the first observation of that address arrived at 10:27, so
the question is really *what if we had known something we did not know*. That is
not a counterfactual about response, it is a fantasy about clairvoyance, and
answering it produces a large avoided-impact number that no amount of faster
operating could ever have delivered. So the earliest defensible time is the first
record naming the entity, and anything before it is refused.

**The remainder is stated, not dropped.** Steps that came after the intervention
and were *not* downstream of it would have happened anyway. They are reported as
`unavoidable` rather than quietly excluded, because a reader comparing the
avoided count against the incident wants to know why the two differ, and an
estimate that only shows its winnings is an advertisement.

The assumptions the records cannot settle — that blocking works immediately and
completely, and that the attacker does not simply take another route — are
carried in `basis` and travel with every answer. They are the difference between
an estimate and a claim, and they are exactly what a confident number omits.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime

from .incidents import Incident


class CounterfactualRefused(ValueError):
    """A question the stored timeline does not support.

    Raised rather than answered with a hedge. "We cannot tell" delivered as a
    small number with a caveat is read as a small number.
    """


@dataclass(frozen=True)
class Intervention:
    """The thing that would have been done, where, and when."""

    entity_key: str
    at: datetime
    action_id: str | None = None
    """Optional, and validated by the caller against the registry rather than
    here — `packages/core` has the registry but the policy question ("may this
    be done") belongs to Dharma, and a counterfactual that scored its own
    proposal would be marking its own work."""


@dataclass(frozen=True)
class Step:
    """One causal step, placed in time by the records that established it."""

    index: int
    entity_key: str
    transition: str
    at: datetime
    refs: tuple[str, ...]

    def describe(self) -> str:
        return (
            f"{self.at.strftime('%H:%M')} {self.entity_key} — {self.transition} "
            f"({', '.join(self.refs)})"
        )


@dataclass(frozen=True)
class Untimed:
    """A step no stored event could place in time.

    Reported rather than assumed early or late. Either assumption changes the
    answer, and a step silently sorted to one end is a thumb on the scale in a
    calculation whose whole output is a comparison against a moment.
    """

    index: int
    entity_key: str
    reason: str


@dataclass(frozen=True)
class Counterfactual:
    """What the records say acting at that moment would and would not have done."""

    incident_ref: str
    intervention: Intervention
    earliest_defensible: datetime
    prevented: tuple[Step, ...]
    unavoidable: tuple[Step, ...]
    already_happened: tuple[Step, ...]
    untimed: tuple[Untimed, ...]
    basis: tuple[str, ...]
    reach: tuple[str, ...]

    @property
    def avoided_entities(self) -> list[str]:
        """Distinct entities the prevented steps touched.

        Counted from the steps rather than from the reachable set: reachability
        says what *could* have been affected, and the chain says what actually
        was. Reporting the larger of the two as avoided would credit the
        intervention with harm that never happened.
        """
        seen: list[str] = []
        for step in self.prevented:
            if step.entity_key not in seen:
                seen.append(step.entity_key)
        return seen

    @property
    def refs(self) -> list[str]:
        seen: list[str] = []
        for step in self.prevented:
            for ref in step.refs:
                if ref not in seen:
                    seen.append(ref)
        return seen

    @property
    def gap_seconds(self) -> float:
        """How much earlier this is than the last thing that happened anyway.

        Zero when the intervention lands after everything: the honest answer to
        "what if we had acted at the end" is that it changes nothing.
        """
        if not self.prevented:
            return 0.0
        return (self.prevented[-1].at - self.intervention.at).total_seconds()

    def describe(self) -> str:
        when = self.intervention.at.strftime("%H:%M")
        if not self.prevented:
            trailing = (
                f" {len(self.unavoidable)} later step(s) were not downstream of it, so "
                "they would have happened regardless."
                if self.unavoidable
                else ""
            )
            return (
                f"Acting on {self.intervention.entity_key} at {when} would have "
                f"prevented nothing recorded in {self.incident_ref}: every step it "
                f"could have reached had already happened.{trailing}"
            )
        minutes = self.gap_seconds / 60
        steps = "; ".join(step.describe() for step in self.prevented)
        avoided = ", ".join(self.avoided_entities)
        remainder = (
            f" {len(self.unavoidable)} later step(s) were not downstream of it and "
            "would have happened anyway."
            if self.unavoidable
            else ""
        )
        return (
            f"Estimate. Acting on {self.intervention.entity_key} at {when} would have "
            f"pre-empted {len(self.prevented)} recorded step(s) over the following "
            f"{minutes:.0f} minutes, sparing {avoided}. Those steps were: {steps}."
            f"{remainder}"
        )


def _step_times(
    incident: Incident, observed_at: Mapping[str, datetime]
) -> tuple[list[Step], list[Untimed]]:
    """Place each causal step at the earliest record that established it.

    Earliest rather than latest: a step is *the moment the behaviour began*, and
    dating it from the last confirming observation would report the intrusion as
    later than it was — which shortens every gap this module exists to measure.
    """
    timed: list[Step] = []
    untimed: list[Untimed] = []
    for index, link in enumerate(incident.causal_chain):
        times = [observed_at[ref] for ref in link.evidence if ref in observed_at]
        if not times:
            untimed.append(
                Untimed(
                    index=index,
                    entity_key=link.entity.key(),
                    reason=(
                        f"none of {list(link.evidence)} resolves to a stored event, so "
                        "this step cannot be placed before or after the intervention"
                    ),
                )
            )
            continue
        timed.append(
            Step(
                index=index,
                entity_key=link.entity.key(),
                transition=link.transition,
                at=min(times),
                refs=tuple(ref for ref in link.evidence if ref in observed_at),
            )
        )
    return sorted(timed, key=lambda s: s.at), untimed


def earliest_defensible(
    incident: Incident, entity_key: str, observed_at: Mapping[str, datetime]
) -> datetime | None:
    """The first moment a record named this entity.

    Before this there is nothing that would have prompted the action, so an
    intervention dated earlier is not a faster response — it is a different
    incident, one where we already knew.
    """
    times = [
        observed_at[ref]
        for link in incident.causal_chain
        if link.entity.key() == entity_key
        for ref in link.evidence
        if ref in observed_at
    ]
    return min(times) if times else None


def counterfactual(
    incident: Incident,
    intervention: Intervention,
    observed_at: Mapping[str, datetime],
    reachable: Collection[str],
) -> Counterfactual:
    """What acting at that moment would have prevented.

    `observed_at` and `reachable` are supplied by the caller rather than read
    here, for the reason `relations.py` takes its indicators as an argument:
    `packages/core` holds no store and has to run on a laptop. The caller maps
    event ids to times and walks the access graph; this module decides what
    those two facts mean together, which is the part that must not vary between
    a laptop and a deployment.
    """
    chain_entities = {link.entity.key() for link in incident.causal_chain}
    if intervention.entity_key not in chain_entities:
        raise CounterfactualRefused(
            f"{intervention.entity_key} is not on {incident.id}'s causal chain, which "
            f"names {sorted(chain_entities)}. What blocking something this incident "
            "never recorded would have done is not a question its records can answer."
        )

    timed, untimed = _step_times(incident, observed_at)
    if not timed:
        raise CounterfactualRefused(
            f"no step of {incident.id} could be placed in time — none of its evidence "
            "resolves to a stored event. Without a timeline there is no 'earlier' to "
            "reason about."
        )

    earliest = earliest_defensible(incident, intervention.entity_key, observed_at)
    if earliest is None:
        raise CounterfactualRefused(
            f"nothing stored places {intervention.entity_key} in time, so there is no "
            "moment from which acting on it would have been possible."
        )
    if intervention.at < earliest:
        raise CounterfactualRefused(
            f"{intervention.at.strftime('%H:%M')} is before "
            f"{earliest.strftime('%H:%M')}, the first record naming "
            f"{intervention.entity_key}. Acting then would have required knowing "
            "something nothing had yet observed, so the answer would measure "
            "clairvoyance rather than response time."
        )

    # The entity's own later steps count: removing it stops what it goes on to
    # do, not only what depends on it.
    affected = {intervention.entity_key, *reachable}

    prevented = tuple(s for s in timed if s.at > intervention.at and s.entity_key in affected)
    unavoidable = tuple(
        s for s in timed if s.at > intervention.at and s.entity_key not in affected
    )
    already = tuple(s for s in timed if s.at <= intervention.at)

    basis = [
        (
            f"Timed from {len({r for s in timed for r in s.refs})} stored event(s); "
            "each step is dated to the earliest record that established it."
        ),
        (
            f"Downstream reach of {intervention.entity_key} taken from "
            f"{len(list(reachable))} stored access edge target(s), each citing its own "
            "evidence. A later step not among them is reported as unavoidable rather "
            "than counted."
        ),
        (
            "Assumes the action would have been immediate and complete. Nothing "
            "stored measures how long it takes to apply or whether it fully works."
        ),
        (
            "Assumes the attacker would not have taken another route. The records "
            "describe what happened once; they cannot say what would have been tried "
            "next, and a determined intruder blocked at one path is not a stopped one."
        ),
    ]
    if untimed:
        basis.append(
            f"{len(untimed)} step(s) could not be placed in time and are excluded from "
            "both counts rather than assumed early or late."
        )

    return Counterfactual(
        incident_ref=incident.id,
        intervention=intervention,
        earliest_defensible=earliest,
        prevented=prevented,
        unavoidable=unavoidable,
        already_happened=already,
        untimed=tuple(untimed),
        basis=tuple(basis),
        reach=tuple(sorted(reachable)),
    )


def moments(incident: Incident, observed_at: Mapping[str, datetime]) -> list[Step]:
    """The chain as a timeline, for a caller offering the moments to ask about.

    Offered rather than free-form: the interesting counterfactuals are the ones
    at the boundaries between steps, and a caller that has to invent a timestamp
    will invent one outside what the records support.
    """
    timed, _ = _step_times(incident, observed_at)
    return timed


__all__ = [
    "Counterfactual",
    "CounterfactualRefused",
    "Intervention",
    "Step",
    "Untimed",
    "counterfactual",
    "earliest_defensible",
    "moments",
]
