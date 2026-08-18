"""Buddhi — hypotheses, contradiction, change correlation, causal chains.

This is the first output a user would call intelligence, and the first place the
system can be confidently wrong in a way that reads as authoritative. Everything
here is built around that asymmetry.

**Citations are verified, not merely required.** The gateway's schema already
forces every hypothesis to carry `evidence_refs`. That is not enough: a model can
satisfy the schema by citing `evt-99`, an ID that looks exactly like the real
ones and does not exist. The schema checks that a citation is *present*; this
module checks that it is *real*, against the events the incident actually holds.
An unverifiable citation is worse than a missing one — a missing citation is
visibly ungrounded, while a fabricated one is indistinguishable from a good one
right up until an operator clicks it.

**Suppression is counted, never silent.** An unsupported hypothesis is dropped
rather than surfaced at low confidence, because a low-confidence hypothesis on
screen is read as a lead and someone spends an hour on it at 3am. But dropping
things quietly is its own failure: a reasoning layer that discards most of what
it produces is broken, and the only way anyone finds out is if the discards are
visible. Every suppression is recorded with its reason.

**Change correlation offers evidence, never a verdict.** A deployment near the
onset of a degradation is the highest-yield causal signal there is, and it is
still only a coincidence in time. This module surfaces the deploy as evidence a
hypothesis may cite; it never concludes the deploy was the cause. That preserves
the Phase 1 connector rule — "a deploy happened" must not read as "a deploy broke
something" — at the layer where the temptation to collapse the two is strongest.

The model proposes. This module decides what survives.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from .events import Event, EventClass
from .gateway import Effort, Evidence, Gateway, ModelRequest
from .incidents import CausalLink, Hypothesis
from .smriti import MemoryKind, Recollection, Smriti, Trust

DEPLOY_LOOKBACK = timedelta(minutes=30)
"""How far back from an incident's onset a deployment is worth surfacing.

Thirty minutes is a judgement, like the correlation window: long enough to catch
a rollout whose damage takes a few minutes to show, short enough that the
lunchtime deploy is not offered as evidence for an evening outage. A tunable the
benchmark should settle."""

MAX_HYPOTHESES = 5
"""More than a handful is not a ranked list, it is a wall of text that pushes the
operator back to reading raw telemetry — which is the thing this replaces."""


class SuppressionReason(StrEnum):
    """Why a proposed hypothesis did not survive."""

    NO_EVIDENCE = "no_evidence"
    """Cited nothing. The schema should have caught this; belt and braces."""

    FABRICATED_CITATION = "fabricated_citation"
    """Cited an event ID that does not exist in this incident. The dangerous one:
    it satisfies every structural check while being ungrounded."""

    EMPTY_STATEMENT = "empty_statement"

    DUPLICATE = "duplicate"
    """Same claim already surfaced. Repetition reads as corroboration."""


@dataclass(frozen=True)
class Suppressed:
    """A dropped hypothesis, kept so the drop is inspectable."""

    statement: str
    reason: SuppressionReason
    detail: str = ""


@dataclass
class ChangeCandidate:
    """A deployment that preceded the onset. Evidence, not a conclusion."""

    event_id: str
    service: str
    version: str
    at: datetime
    seconds_before_onset: float

    def describe(self) -> str:
        return (
            f"{self.service} deployed {self.version} "
            f"{self.seconds_before_onset / 60:.1f} min before onset"
        )


@dataclass
class Reasoning:
    """Everything the layer produced, including what it threw away."""

    hypotheses: list[Hypothesis] = field(default_factory=list)
    causal_chain: list[CausalLink] = field(default_factory=list)
    changes: list[ChangeCandidate] = field(default_factory=list)
    recalled: list[Recollection] = field(default_factory=list)
    suppressed: list[Suppressed] = field(default_factory=list)
    proposed: int = 0
    """How many the model offered, before filtering."""

    @property
    def precedents(self) -> list[Recollection]:
        """Recollections that justify the phrase "we have seen this before".

        Separated from `recalled` so the UI cannot accidentally present a
        text-only resemblance as history.
        """
        return [r for r in self.recalled if r.is_precedent]

    @property
    def suppression_rate(self) -> float:
        """Read next to the hypothesis count.

        A high rate is not automatically bad — suppressing junk is the job — but a
        layer suppressing almost everything is either badly prompted or being fed
        evidence that cannot support conclusions, and both are worth seeing.
        """
        return round(len(self.suppressed) / self.proposed, 3) if self.proposed else 0.0

    @property
    def top(self) -> Hypothesis | None:
        return max(self.hypotheses, key=lambda h: h.confidence, default=None)

    def summary(self) -> dict[str, object]:
        return {
            "proposed": self.proposed,
            "surfaced": len(self.hypotheses),
            "suppressed": len(self.suppressed),
            "suppression_rate": self.suppression_rate,
            "by_reason": {
                reason.value: sum(1 for s in self.suppressed if s.reason is reason)
                for reason in SuppressionReason
                if any(s.reason is reason for s in self.suppressed)
            },
            "changes_considered": len(self.changes),
            "recalled": len(self.recalled),
            "precedents": len(self.precedents),
        }


# --- change correlation (deterministic — no model involved) -------------------


def correlate_changes(
    events: list[Event],
    onset: datetime,
    lookback: timedelta = DEPLOY_LOOKBACK,
) -> list[ChangeCandidate]:
    """Deployments shortly before the onset, nearest first.

    Deterministic on purpose. "Did something change just before this broke?" is a
    question about timestamps, and answering it with a model would be slower, more
    expensive, and less reliable than answering it with a comparison.

    Deploys *after* onset are excluded: a rollout that began after the degradation
    cannot have caused it, and offering it as a candidate invites exactly the
    post-hoc reasoning this is supposed to prevent.
    """
    candidates: list[ChangeCandidate] = []
    for event in events:
        if event.event_class is not EventClass.DEPLOYMENT:
            continue
        payload = event.payload
        service = getattr(payload, "service", None)
        version = getattr(payload, "version", None)
        if service is None or version is None:
            continue

        delta = (onset - event.occurred_at).total_seconds()
        if delta < 0 or delta > lookback.total_seconds():
            continue

        candidates.append(
            ChangeCandidate(
                event_id=event.id,
                service=service,
                version=version,
                at=event.occurred_at,
                seconds_before_onset=delta,
            )
        )

    return sorted(candidates, key=lambda c: c.seconds_before_onset)


# --- the reasoner -------------------------------------------------------------


HYPOTHESIS_INSTRUCTIONS = """\
You are an incident analyst. You are given observed telemetry from one incident.

Propose the most likely explanations for what happened. Rules you must follow:

1. Every hypothesis must cite the evidence supporting it, using the exact `ref`
   values shown in the evidence blocks. Do not invent a ref. If you cannot
   support a claim with a ref that appears above, do not make the claim.
2. Populate `contradicted_by` with the refs of any evidence that argues against
   your own hypothesis. A hypothesis with no counter-evidence is not necessarily
   stronger — it may just be less examined.
3. Confidence reflects how well the evidence supports the claim, not how
   plausible the story sounds. It feeds a risk score, so overstating it widens
   what the system is permitted to do without asking a human.
4. A deployment shortly before onset is a correlation in time. It may be cited
   as evidence; it does not by itself establish cause.
5. Prefer fewer, better-supported hypotheses over a long list."""


class Reasoner:
    """Turns evidence into hypotheses, then decides which survive.

    Takes a `Gateway` rather than a provider or a client: this module never
    learns which model answered, which is what lets the same reasoning run
    against Bedrock, a direct API, or the deterministic stub in the benchmark.
    """

    def __init__(
        self,
        gateway: Gateway,
        max_hypotheses: int = MAX_HYPOTHESES,
        memory: "Smriti | None" = None,
        tenant: str | None = None,
    ) -> None:
        self.gateway = gateway
        self.max_hypotheses = max_hypotheses
        self.memory = memory
        self.tenant = tenant

    def analyse(
        self,
        incident_id: str,
        events: list[Event],
        onset: datetime | None = None,
        agent: str | None = None,
    ) -> Reasoning:
        """Produce hypotheses for one incident.

        The evidence set passed to the model is also the set citations are checked
        against, so a hypothesis can only cite something the model was actually
        shown. That equivalence is the whole guarantee — if the two ever came from
        different places, verification would silently start passing things it
        should reject.
        """
        if not events:
            # Nothing observed means nothing to explain. Returning an empty
            # result is honest; asking a model to speculate without evidence is
            # asking it to invent, and it would.
            return Reasoning()

        onset = onset or min(event.occurred_at for event in events)
        changes = correlate_changes(events, onset)
        evidence = self._as_evidence(events, changes)
        recollections = self._recall(incident_id, events)
        evidence.extend(self._as_memory_evidence(recollections))
        known_refs = {item.ref for item in evidence}

        response = self.gateway.complete(
            ModelRequest(
                purpose="hypothesis",
                schema_name="hypothesis_v1",
                instructions=HYPOTHESIS_INSTRUCTIONS,
                question=(
                    "What is the most likely root cause of this incident? "
                    "Cite only the refs shown above."
                ),
                evidence=evidence,
                incident_id=incident_id,
                agent=agent,
                effort=Effort.HIGH,
            )
        )

        result = Reasoning(changes=changes, recalled=recollections)
        proposals = response.output.get("hypotheses", [])
        result.proposed = len(proposals)

        seen: set[str] = set()
        for raw in proposals:
            hypothesis = self._admit(raw, known_refs, seen, result)
            if hypothesis is not None:
                result.hypotheses.append(hypothesis)
                seen.add(hypothesis.statement.strip().lower())

        result.hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        del result.hypotheses[self.max_hypotheses :]
        result.causal_chain = self._chain(result.hypotheses, events)
        return result

    # -- admission ------------------------------------------------------------

    def _admit(
        self,
        raw: dict[str, object],
        known_refs: set[str],
        seen: set[str],
        result: Reasoning,
    ) -> Hypothesis | None:
        """Decide whether one proposal survives, recording the reason if not."""
        statement = str(raw.get("statement", "")).strip()
        if not statement:
            result.suppressed.append(Suppressed("", SuppressionReason.EMPTY_STATEMENT))
            return None

        if statement.lower() in seen:
            result.suppressed.append(Suppressed(statement, SuppressionReason.DUPLICATE))
            return None

        refs = [str(ref) for ref in raw.get("evidence_refs", []) or []]
        if not refs:
            result.suppressed.append(Suppressed(statement, SuppressionReason.NO_EVIDENCE))
            return None

        fabricated = [ref for ref in refs if ref not in known_refs]
        if fabricated:
            # The whole hypothesis goes, not just the bad ref. Keeping it with
            # the fabrication stripped would leave a claim standing on evidence
            # the model did not actually have — which is the failure, not the
            # citation formatting.
            result.suppressed.append(
                Suppressed(
                    statement,
                    SuppressionReason.FABRICATED_CITATION,
                    f"cited unknown ref(s): {', '.join(sorted(fabricated))}",
                )
            )
            return None

        # Counter-evidence is filtered rather than rejected: a fabricated
        # contradiction weakens a hypothesis, so dropping the whole thing would
        # let a bad ref suppress a good claim.
        contradicted = [ref for ref in (raw.get("contradicted_by") or []) if ref in known_refs]

        confidence = float(raw.get("confidence", 0.0))
        return Hypothesis(
            statement=statement,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=refs,
            contradicted_by=[str(ref) for ref in contradicted],
        )

    # -- memory ---------------------------------------------------------------

    def _recall(self, incident_id: str, events: list[Event]) -> list["Recollection"]:
        """Ask Smriti whether anything like this has happened before.

        Scoped by the entities and signals actually present in this incident, so
        the query is structured rather than a prose similarity search — the
        distinction the Smriti ADR turns on.

        The current incident is excluded, or an incident already written to
        memory recalls itself and the system cites its own guess as precedent.
        """
        if self.memory is None or self.tenant is None:
            return []

        entities = {event.entity_ref.key() for event in events}
        signals = {
            name
            for event in events
            if (name := getattr(event.payload, "name", None)) is not None
        }
        text = " ".join(
            f"{event.event_class} {event.entity_ref.name}" for event in events[:20]
        )
        return self.memory.recall(
            self.tenant, text, entities=entities, signals=signals, exclude=incident_id
        )

    @staticmethod
    def _as_memory_evidence(recollections: list["Recollection"]) -> list[Evidence]:
        """Offer prior incidents as citable evidence — carrying their outcomes.

        Past incidents are platform-authored, so they are marked trusted: unlike
        telemetry, nobody outside wrote them. Runbooks and decision records are
        not, and are passed through only once promoted — an unverified document
        is a document, and a document is untrusted input.

        The outcome travels with the memory, and a wrong prior diagnosis is
        stated in the evidence itself. A model shown "this resembles INC-42"
        without being told INC-42 was misdiagnosed will confidently repeat the
        earlier mistake, and cite history while doing it.
        """
        evidence: list[Evidence] = []
        for recollection in recollections:
            record = recollection.record
            trusted = record.kind is MemoryKind.INCIDENT or record.trust is Trust.VERIFIED

            content = f"{recollection.describe()}\n{record.text}"
            if record.outcome is not None and (warning := record.outcome.warning):
                content = f"WARNING: {warning}\n{content}"
            if not recollection.is_precedent:
                content = (
                    "NOTE: this shares no entity or signal with the current incident; "
                    "it merely reads similarly and is not a precedent.\n" + content
                )

            evidence.append(
                Evidence(
                    ref=record.id,
                    source=f"smriti:{record.kind}",
                    content=content,
                    trusted=trusted,
                )
            )
        return evidence

    # -- evidence assembly ----------------------------------------------------

    @staticmethod
    def _as_evidence(events: list[Event], changes: list[ChangeCandidate]) -> list[Evidence]:
        """Render events as gateway evidence, untrusted by default.

        Deploy candidates are annotated with their timing relative to onset, since
        "18 minutes before" is the part that makes a deployment worth considering
        and the raw timestamp buries it.
        """
        timing = {change.event_id: change for change in changes}
        evidence: list[Evidence] = []

        for event in events:
            content = f"[{event.event_class}] {event.entity_ref.key()} @ {event.occurred_at.isoformat()}\n"
            content += event.payload.model_dump_json()
            if change := timing.get(event.id):
                content += f"\nTIMING: {change.describe()}"
            evidence.append(
                Evidence(ref=event.id, source=event.source, content=content)
            )
        return evidence

    # -- causal chain ---------------------------------------------------------

    @staticmethod
    def _chain(hypotheses: list[Hypothesis], events: list[Event]) -> list[CausalLink]:
        """Assemble the chain from the surviving top hypothesis.

        Built from the *admitted* hypothesis only, so every link inherits
        citations that have already been verified — the chain cannot be the place
        an unverified ref sneaks back in.

        Ordered by the observation time of the cited evidence rather than by the
        model's narrative order. A model asked for a sequence will produce one
        whether or not the timestamps agree, and when the two disagree the
        timestamps are right.
        """
        top = max(hypotheses, key=lambda h: h.confidence, default=None)
        if top is None:
            return []

        by_id = {event.id: event for event in events}
        cited = [by_id[ref] for ref in top.evidence if ref in by_id]
        cited.sort(key=lambda event: event.occurred_at)

        return [
            CausalLink(
                entity=event.entity_ref,
                transition=f"{event.event_class} observed at {event.occurred_at.isoformat()}",
                evidence=[event.id],
            )
            for event in cited
        ]


# --- measurement --------------------------------------------------------------


@dataclass
class DiagnosisQuality:
    """How often the top hypothesis was right, and how well it was grounded.

    The Phase 2 exit criterion is "top-1 root cause correct ≥70% on 20 labelled
    incidents, and every hypothesis cites its telemetry". That is two claims, so
    this reports two numbers — an accurate diagnosis that cannot be traced back
    to the telemetry supporting it fails the second half regardless of the first,
    and averaging them into one score would hide exactly that case.
    """

    correct: int = 0
    incorrect: int = 0
    abstained: int = 0
    """Produced no hypothesis at all. Counted separately from wrong: declining to
    guess is the behaviour we want when evidence does not support a conclusion,
    and folding it into the error rate would punish it."""

    uncited: int = 0
    """Surfaced hypotheses whose citations did not resolve. Should be zero — if it
    is not, admission is broken, and the accuracy number is not trustworthy."""

    @property
    def total(self) -> int:
        return self.correct + self.incorrect + self.abstained

    @property
    def top1_accuracy(self) -> float:
        """Over every labelled incident, abstentions included.

        Abstentions count against accuracy on purpose: a system that declines
        everything is not a 100%-accurate system, it is an unused one.
        """
        return round(self.correct / self.total, 4) if self.total else 0.0

    @property
    def precision_when_answering(self) -> float:
        """Accuracy over the incidents where it did commit to an answer.

        Read beside `top1_accuracy`: the gap between them is the cost of caution,
        and it is the number to look at when deciding whether the abstention
        threshold is set sensibly.
        """
        answered = self.correct + self.incorrect
        return round(self.correct / answered, 4) if answered else 0.0

    @property
    def fully_grounded(self) -> bool:
        return self.uncited == 0

    def summary(self) -> dict[str, object]:
        return {
            "incidents": self.total,
            "top1_accuracy": self.top1_accuracy,
            "precision_when_answering": self.precision_when_answering,
            "abstained": self.abstained,
            "uncited": self.uncited,
            "fully_grounded": self.fully_grounded,
        }


def score_diagnoses(
    cases: list[tuple[Reasoning, str]],
    matches: "Callable[[Hypothesis, str], bool] | None" = None,
) -> DiagnosisQuality:
    """Score reasoning output against labelled root causes.

    `cases` pairs each result with the known cause, labelled in the scenario
    before the reasoner ran — the same rule the benchmark follows, and for the
    same reason: a label written after seeing the output is not a label.

    `matches` decides whether a hypothesis states the known cause. Substring
    matching is the crude default and it is deliberately a parameter: judging
    semantic equivalence is its own research problem, and hard-coding a weak
    answer would quietly cap the measured accuracy of every future improvement.
    """
    if matches is None:

        def matches(hypothesis: Hypothesis, cause: str) -> bool:
            return cause.strip().lower() in hypothesis.statement.lower()

    quality = DiagnosisQuality()
    for result, cause in cases:
        top = result.top
        if top is None:
            quality.abstained += 1
            continue
        if not top.evidence:  # pragma: no cover — admission should prevent this
            quality.uncited += 1
        if matches(top, cause):
            quality.correct += 1
        else:
            quality.incorrect += 1
    return quality
