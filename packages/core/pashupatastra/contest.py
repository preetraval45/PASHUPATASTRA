"""The case for the other explanation, and whether the record actually beats it.

The Blue Team rubric tells a player that *one of the explanations is plausible
and wrong*, and scores them on whether they opened the evidence that rules it
out. This module holds the agent to the same standard on the same incidents: it
states the rival's case in its strongest form, then reports what defeats it — or
reports that nothing does.

**A ranking is not a refutation.** The tempting implementation reads the
confidence numbers, sees 0.86 against 0.09, and reports the alternative as
rejected. Confidence is a figure an author wrote; the incident's own diagnosis
asserting it is unlikely is the claim under examination, not the evidence for
it. So the verdict turns on one thing only: whether something stored, and
resolvable, contradicts the rival. Where nothing does, the answer is that the
diagnosis has *not* beaten it — and that is the case where the alternative wins.

**A restatement is not a rival.** Two hypotheses resting on the same records with
nothing to tell them apart are one claim written twice, and adjudicating between
them is theatre that produces a confident-looking verdict about nothing. A real
rival has to share ground — it must explain at least one of the same
observations, or it is not an answer to the same question — and it must diverge,
by the leader citing something it does not or by something contradicting it.
Where neither holds, this refuses rather than staging a contest.

Text is never compared. Deciding "these say the same thing" by wording would be
the resemblance-matching `relations.py` refuses and Smriti marks as a text match
rather than a precedent; two hypotheses can be worded identically and rest on
different records, or worded differently and rest on the same ones. Only the
records decide.

No model participates. What Sati contributes is the decision to ask and the
prose around the answer.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum

from .incidents import Hypothesis, Incident


class Verdict(StrEnum):
    UPHELD = "upheld"
    """Something stored contradicts the rival, and it resolves."""

    UNREFUTED = "unrefuted"
    """Nothing checkable rules the rival out.

    Not a claim that the rival is correct — a claim that the diagnosis has not
    earned its place over it. The distinction matters and is easy to lose: an
    unrefuted alternative is an open question, not a rival conclusion.
    """


class ContestRefused(ValueError):
    """There is no contest here worth staging."""


@dataclass(frozen=True)
class Case:
    """One explanation, and the records that survive checking."""

    ref: str
    statement: str
    confidence: float

    supported_by: tuple[str, ...]
    """Evidence that resolves. This is the case's actual footing."""

    uncited: tuple[str, ...]
    """Evidence it claims and nothing resolves.

    Kept rather than dropped: a hypothesis resting on three records, two of
    which do not exist, is weaker than one resting on one that does, and a
    reader comparing the two needs to see that.
    """

    @property
    def grounded(self) -> bool:
        return bool(self.supported_by)


@dataclass(frozen=True)
class Contest:
    """The leading explanation, its strongest rival, and what separates them."""

    incident_ref: str
    leader: Case
    rival: Case
    verdict: Verdict

    ruled_out_by: tuple[str, ...]
    """Resolvable records contradicting the rival. Empty on `UNREFUTED`."""

    unresolved_rejection: tuple[str, ...]
    """Records the incident claims rule the rival out, that resolve to nothing.

    Reported rather than quietly ignored. A rejection nobody can check spends a
    reader's trust without earning it, and naming no reason and naming a reason
    that does not exist are the same failure — R68 collapses them for the same
    reason.
    """

    shared: tuple[str, ...]
    """Observations both explain. This is what makes them answers to one question."""

    separators: tuple[str, ...]
    """What could tell them apart: records the leader rests on and the rival does
    not, plus whatever contradicts the rival."""

    unexplained_by_leader: tuple[str, ...]
    """Records the rival accounts for and the leader does not cite.

    A point for the rival, and the one a confident diagnosis is least likely to
    mention about its own alternative.
    """

    @property
    def refs(self) -> list[str]:
        """Everything this adjudication rests on."""
        seen: list[str] = []
        for ref in (*self.ruled_out_by, *self.shared, *self.unexplained_by_leader):
            if ref not in seen:
                seen.append(ref)
        return seen

    def describe(self) -> str:
        """The rival's case, then what answers it."""
        argued = (
            f"The case for the alternative — {self.rival.statement} It explains "
            f"{', '.join(self.shared)}, the same observation(s) the diagnosis "
            f"rests on."
        )
        if self.unexplained_by_leader:
            argued += (
                f" It also accounts for {', '.join(self.unexplained_by_leader)}, "
                "which the diagnosis does not cite."
            )

        if self.verdict is Verdict.UPHELD:
            answered = (
                f" It is ruled out by {', '.join(self.ruled_out_by)}. "
                f"The diagnosis stands: {self.leader.statement}"
            )
        else:
            answered = (
                " Nothing stored rules it out. The diagnosis leads it only on "
                f"confidence ({self.leader.confidence:.2f} against "
                f"{self.rival.confidence:.2f}), and a confidence figure is a number "
                "an author wrote rather than a record anyone can check — so this "
                "alternative has not been beaten, it has been ranked below."
            )
        if self.unresolved_rejection:
            answered += (
                f" {len(self.unresolved_rejection)} claimed contradiction(s) "
                f"({', '.join(self.unresolved_rejection)}) resolve to nothing and are "
                "not counted."
            )
        return argued + answered


def _case(hypothesis: Hypothesis, index: int, resolvable: Collection[str]) -> Case:
    return Case(
        ref=f"#hypothesis-{index}",
        statement=hypothesis.statement,
        confidence=hypothesis.confidence,
        supported_by=tuple(r for r in hypothesis.evidence if r in resolvable),
        uncited=tuple(r for r in hypothesis.evidence if r not in resolvable),
    )


def contest(incident: Incident, resolvable: Collection[str]) -> Contest:
    """Argue the strongest alternative, then report what answers it.

    `resolvable` is the set of refs that resolve to a stored record, supplied by
    the caller rather than read here — `packages/core` holds no store, the same
    reason `relations.py` takes its indicators and `counterfactual.py` takes its
    timeline. The judgement is here so a laptop and a deployment cannot disagree
    about what a set of records means.
    """
    resolvable = set(resolvable)
    ranked = sorted(
        enumerate(incident.hypotheses), key=lambda pair: pair[1].confidence, reverse=True
    )
    if len(ranked) < 2:
        raise ContestRefused(
            f"{incident.id} records {len(ranked)} hypothesis(es). There is no other "
            "side to argue, and inventing one in order to knock it down would be "
            "the rigour-shaped version of having none."
        )

    leader_index, leader_hypothesis = ranked[0]
    leader = _case(leader_hypothesis, 0, resolvable)
    if not leader.grounded:
        raise ContestRefused(
            f"{incident.id}'s leading explanation rests on {list(leader_hypothesis.evidence)}, "
            "none of which resolves. Adjudicating between an ungrounded diagnosis and "
            "an alternative would stage a contest neither side can win."
        )

    considered: list[tuple[Case, Hypothesis, tuple[str, ...], tuple[str, ...]]] = []
    rejected: list[str] = []
    for rank, (index, hypothesis) in enumerate(ranked[1:], start=1):
        if index == leader_index:
            continue
        rival = _case(hypothesis, rank, resolvable)
        shared = tuple(r for r in leader.supported_by if r in rival.supported_by)
        contradicted = tuple(r for r in hypothesis.contradicted_by if r in resolvable)
        separators = tuple(
            dict.fromkeys(
                (*(r for r in leader.supported_by if r not in rival.supported_by), *contradicted)
            )
        )
        if not rival.grounded:
            rejected.append(
                f"{rival.ref} rests on {list(hypothesis.evidence)}, none of which resolves"
            )
            continue
        if not shared:
            rejected.append(
                f"{rival.ref} shares no observation with the diagnosis, so it answers a "
                "different question rather than competing for this one"
            )
            continue
        if not separators:
            rejected.append(
                f"{rival.ref} rests on exactly the records the diagnosis does and nothing "
                "contradicts it — the two are one claim written twice, and there is "
                "nothing that could tell them apart"
            )
            continue
        considered.append((rival, hypothesis, shared, separators))

    if not considered:
        raise ContestRefused(
            f"{incident.id} records no alternative that competes with its diagnosis. "
            + "; ".join(rejected)
        )

    rival, hypothesis, shared, separators = considered[0]
    ruled_out_by = tuple(r for r in hypothesis.contradicted_by if r in resolvable)
    return Contest(
        incident_ref=incident.id,
        leader=leader,
        rival=rival,
        # The only thing that decides it. Not the confidence gap, which is the
        # diagnosis asserting its own correctness.
        verdict=Verdict.UPHELD if ruled_out_by else Verdict.UNREFUTED,
        ruled_out_by=ruled_out_by,
        unresolved_rejection=tuple(
            r for r in hypothesis.contradicted_by if r not in resolvable
        ),
        shared=shared,
        separators=separators,
        unexplained_by_leader=tuple(
            r for r in rival.supported_by if r not in leader.supported_by
        ),
    )


__all__ = ["Case", "Contest", "ContestRefused", "Verdict", "contest"]
