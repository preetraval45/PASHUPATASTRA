"""Drafts written from an incident's own records, and never anything more.

Two documents an analyst would otherwise write by hand at three in the morning:
a playbook for responding to this kind of incident, and a post-incident report
of what actually happened. Both are assembled here, from stored records.

**A line that cites nothing cannot be constructed.** `Line` rejects an empty
`refs` at construction, the same way `Hypothesis` rejects empty evidence and for
the same reason: a rule enforced at the type is a rule the next author cannot
forget. The alternative — assemble freely, then check — leaves the uncited
sentence written, reviewed and one deletion away from shipping.

**Nothing here is adopted.** There is no field to set, no state to advance and
no second rendering path: a draft is a draft in every constructor, and adopting
one is a registered action that goes through Dharma like every other action. The
document object never becomes the approved thing, because the approved thing is
an audit record saying a named human accepted it.

**Absence is stated, not omitted.** A post-incident report with no "what was
verified" section reads as a report whose author forgot; one that says nothing
was verified and cites the incident is a report making a claim a reader can
check. Empty sections are the interesting half of a report and are kept.
"""

from __future__ import annotations

from dataclasses import dataclass

from .incidents import Incident

PLAYBOOK = "playbook"
POST_INCIDENT = "post_incident"


@dataclass(frozen=True)
class Line:
    """One assertion, and the records it rests on.

    Refs are required and non-empty. A draft sentence nobody can trace is the
    thing this whole document exists not to produce.
    """

    text: str
    refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a draft line with no text is not a line")
        if not self.refs:
            raise ValueError(
                f"draft line {self.text[:40]!r} cites nothing; "
                "every assertion in a draft carries its evidence reference"
            )


@dataclass(frozen=True)
class Section:
    title: str
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class Draft:
    """A document that is always a draft, whatever anyone does with it."""

    kind: str
    incident_ref: str
    title: str
    sections: tuple[Section, ...]

    @property
    def status(self) -> str:
        """Not a field. A status that can be assigned is a status that will be,
        and there is no code path here that should be able to call this
        anything else — adoption is an action, recorded elsewhere."""
        return "draft"

    @property
    def refs(self) -> list[str]:
        seen: list[str] = []
        for section in self.sections:
            for line in section.lines:
                for ref in line.refs:
                    if ref not in seen:
                        seen.append(ref)
        return seen

    @property
    def adopt_action_id(self) -> str:
        """What adopting this would require. A registered id, so the caller
        cannot invent one and the policy engine has something to score."""
        return "adopt_playbook" if self.kind == PLAYBOOK else "adopt_report"


def _chain_lines(incident: Incident) -> list[Line]:
    return [
        Line(
            text=f"{link.entity.key()} — {link.transition}",
            refs=(f"{incident.id}#chain-{index}", *link.evidence),
        )
        for index, link in enumerate(incident.causal_chain)
    ]


def _diagnosis_line(incident: Incident) -> Line | None:
    top = incident.top_hypothesis
    if top is None:
        return None
    return Line(
        text=f"{top.statement} (confidence {top.confidence:.2f})",
        refs=(f"{incident.id}#hypothesis-0", *top.evidence),
    )


def _ruled_out_lines(incident: Incident) -> list[Line]:
    """What the diagnosis beat, and on what.

    Carried into both documents because it is the part a reader most needs and
    the part a written-up-afterwards report always drops: by the time anyone
    writes the report the answer feels obvious, and the alternative that was
    live at 3am goes unmentioned.
    """
    ranked = sorted(incident.hypotheses, key=lambda h: h.confidence, reverse=True)
    lines = []
    for index, hypothesis in enumerate(ranked[1:], start=1):
        if not hypothesis.contradicted_by:
            continue
        lines.append(
            Line(
                text=f"Ruled out: {hypothesis.statement}",
                refs=(f"{incident.id}#hypothesis-{index}", *hypothesis.contradicted_by),
            )
        )
    return lines


def playbook(incident: Incident) -> Draft:
    """How to respond to this, written from what was planned for it."""
    sections: list[Section] = []

    diagnosis = _diagnosis_line(incident)
    if diagnosis is not None:
        sections.append(Section(title="What this was", lines=(diagnosis,)))

    chain = _chain_lines(incident)
    if chain:
        sections.append(Section(title="How it unfolded", lines=tuple(chain)))

    steps = []
    for step in sorted(incident.plan, key=lambda s: s.order):
        rollback = step.rollback_action_id or "none declared"
        # A step with no stored verdict has not been scored *for this incident*
        # — risk depends on blast radius and confidence, so the registry's base
        # figure is not the answer and printing it here would read like one.
        tier = (
            step.verdict.tier
            if step.verdict is not None
            else "not scored for this incident yet"
        )
        steps.append(
            Line(
                text=f"{step.order}. {step.action_id} — rollback: {rollback}; authorisation: {tier}",
                refs=(f"{incident.id}#plan-{step.order}",),
            )
        )
    if steps:
        sections.append(Section(title="What to do", lines=tuple(steps)))
    else:
        sections.append(
            Section(
                title="What to do",
                lines=(
                    Line(
                        text="No plan is recorded for this incident, so this draft "
                        "proposes no steps.",
                        refs=(incident.id,),
                    ),
                ),
            )
        )

    checks = []
    for step in sorted(incident.plan, key=lambda s: s.order):
        for key, value in step.expected_post_state.items():
            checks.append(
                Line(
                    text=f"{key} should read {value} after step {step.order}",
                    refs=(f"{incident.id}#plan-{step.order}",),
                )
            )
    if checks:
        sections.append(Section(title="How to tell it worked", lines=tuple(checks)))

    return Draft(
        kind=PLAYBOOK,
        incident_ref=incident.id,
        title=f"Draft playbook — {incident.id}",
        sections=tuple(sections),
    )


def post_incident(incident: Incident) -> Draft:
    """What happened, what was done about it, and what is still not known."""
    sections: list[Section] = []

    happened = []
    diagnosis = _diagnosis_line(incident)
    if diagnosis is not None:
        happened.append(diagnosis)
    happened.extend(_chain_lines(incident))
    if happened:
        sections.append(Section(title="What happened", lines=tuple(happened)))

    ruled_out = _ruled_out_lines(incident)
    if ruled_out:
        sections.append(Section(title="What was ruled out", lines=tuple(ruled_out)))

    done = [
        Line(
            text=(
                f"{execution.action_id} — "
                + (
                    "succeeded"
                    if execution.succeeded
                    else "failed" if execution.succeeded is False else "outcome not recorded"
                )
                + f"; authorised at tier {execution.verdict_snapshot.tier}"
            ),
            refs=(f"{incident.id}#plan-{execution.step_order}",),
        )
        for execution in incident.executions
    ]
    sections.append(
        Section(
            title="What was done",
            lines=tuple(done)
            or (
                Line(
                    text="Nothing was executed. The plan was drawn up and did not run.",
                    refs=(incident.id,),
                ),
            ),
        )
    )

    verification = incident.verification
    if verification is None or not verification.checks:
        verified = (
            Line(
                text="No verification is recorded, so nothing here says the incident "
                "was resolved rather than merely closed.",
                refs=(incident.id,),
            ),
        )
    else:
        verified = tuple(
            Line(
                text=(
                    f"{check.name}: expected {check.expected}, "
                    + (
                        f"observed {check.observed}"
                        if check.observed is not None
                        else "nothing observed"
                    )
                ),
                refs=(incident.id,),
            )
            for check in verification.checks
        )
    sections.append(Section(title="What was verified", lines=verified))

    return Draft(
        kind=POST_INCIDENT,
        incident_ref=incident.id,
        title=f"Draft post-incident report — {incident.id}",
        sections=tuple(sections),
    )


def build_draft(kind: str, incident: Incident) -> Draft:
    builders = {PLAYBOOK: playbook, POST_INCIDENT: post_incident}
    if kind not in builders:
        raise KeyError(f"unknown draft kind {kind!r}; there are {sorted(builders)}")
    return builders[kind](incident)


__all__ = [
    "PLAYBOOK",
    "POST_INCIDENT",
    "Draft",
    "Line",
    "Section",
    "build_draft",
    "playbook",
    "post_incident",
]
