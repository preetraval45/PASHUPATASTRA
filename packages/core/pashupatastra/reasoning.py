"""Buddhi — hypotheses, contradiction, change correlation, causal chains.

The model proposes; this module decides what survives. Citations are checked
against the evidence actually shown, not merely required to be present. See
docs/adr/Grounding.md.
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

# Long enough to catch a rollout whose damage takes a few minutes to show, short
# enough that the lunchtime deploy isn't offered as evidence for an evening
# outage. A tunable the benchmark should settle.
DEPLOY_LOOKBACK = timedelta(minutes=30)

MAX_HYPOTHESES = 5


class SuppressionReason(StrEnum):
    NO_EVIDENCE = "no_evidence"
    # Cited an ID that doesn't exist here. The dangerous one: it satisfies every
    # structural check while being ungrounded.
    FABRICATED_CITATION = "fabricated_citation"
    EMPTY_STATEMENT = "empty_statement"
    DUPLICATE = "duplicate"


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

    @property
    def precedents(self) -> list[Recollection]:
        """Separated from `recalled` so a text-only resemblance can't be shown as history."""
        return [r for r in self.recalled if r.is_precedent]

    @property
    def suppression_rate(self) -> float:
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
    """Deployments shortly before the onset, nearest first."""
    candidates: list[ChangeCandidate] = []
    for event in events:
        if event.event_class is not EventClass.DEPLOYMENT:
            continue
        payload = event.payload
        service = getattr(payload, "service", None)
        version = getattr(payload, "version", None)
        if service is None or version is None:
            continue

        # Negative delta means the deploy started after onset, so it can't have
        # caused it. Offering it invites the post-hoc reasoning this prevents.
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

    Takes a Gateway rather than a client, so this module never learns which model
    answered.
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
        """Produce hypotheses for one incident."""
        if not events:
            return Reasoning()

        onset = onset or min(event.occurred_at for event in events)
        changes = correlate_changes(events, onset)
        evidence = self._as_evidence(events, changes)
        recollections = self._recall(incident_id, events)
        evidence.extend(self._as_memory_evidence(recollections))

        # The set shown to the model *is* the set citations are checked against.
        # If these two ever came from different places, verification would
        # silently start passing things it should reject.
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
            # The whole hypothesis goes, not just the bad ref — stripping it would
            # leave a claim standing on evidence the model never had.
            result.suppressed.append(
                Suppressed(
                    statement,
                    SuppressionReason.FABRICATED_CITATION,
                    f"cited unknown ref(s): {', '.join(sorted(fabricated))}",
                )
            )
            return None

        # Filtered rather than rejected: a fabricated contradiction weakens a
        # hypothesis, so dropping the whole thing would let a bad ref suppress a
        # good claim.
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
        """Ask Smriti whether anything like this has happened before."""
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
        # Excluding the current incident: once written to memory it would recall
        # itself, and the system would cite its own guess as precedent.
        return self.memory.recall(
            self.tenant, text, entities=entities, signals=signals, exclude=incident_id
        )

    @staticmethod
    def _as_memory_evidence(recollections: list["Recollection"]) -> list[Evidence]:
        """Offer prior incidents as citable evidence, carrying their outcomes."""
        evidence: list[Evidence] = []
        for recollection in recollections:
            record = recollection.record
            # Past incidents are platform-authored. Runbooks and decision records
            # are not, and count as trusted only once promoted.
            trusted = record.kind is MemoryKind.INCIDENT or record.trust is Trust.VERIFIED

            content = f"{recollection.describe()}\n{record.text}"
            # A model shown "this resembles INC-42" without being told INC-42 was
            # misdiagnosed will repeat the mistake and cite history doing it.
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
        """Render events as gateway evidence, untrusted by default."""
        timing = {change.event_id: change for change in changes}
        evidence: list[Evidence] = []

        for event in events:
            content = f"[{event.event_class}] {event.entity_ref.key()} @ {event.occurred_at.isoformat()}\n"
            content += event.payload.model_dump_json()
            # "18 minutes before" is the part that makes a deploy worth
            # considering, and the raw timestamp buries it.
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

        Built from the admitted hypothesis only, so every link inherits citations
        already verified.
        """
        top = max(hypotheses, key=lambda h: h.confidence, default=None)
        if top is None:
            return []

        by_id = {event.id: event for event in events}
        cited = [by_id[ref] for ref in top.evidence if ref in by_id]
        # Ordered by observation time, not the model's narrative order. A model
        # asked for a sequence produces one whether or not the timestamps agree.
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

    Two numbers rather than one: an accurate diagnosis that cannot be traced back
    to its telemetry fails the grounding half regardless of the accuracy half,
    and averaging would hide that.
    """

    correct: int = 0
    incorrect: int = 0

    # Counted separately from wrong: declining to guess is the behaviour we want
    # when evidence doesn't support a conclusion.
    abstained: int = 0

    # Should be zero. If it isn't, admission is broken and the accuracy number
    # is not trustworthy.
    uncited: int = 0

    @property
    def total(self) -> int:
        return self.correct + self.incorrect + self.abstained

    @property
    def top1_accuracy(self) -> float:
        """Abstentions count against: a system that declines everything is unused,
        not accurate."""
        return round(self.correct / self.total, 4) if self.total else 0.0

    @property
    def precision_when_answering(self) -> float:
        """The gap from top1_accuracy is the cost of caution."""
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
    """Score reasoning output against root causes labelled before the run.

    `matches` is a parameter because judging semantic equivalence is its own
    problem, and hard-coding the crude substring default would quietly cap the
    measured accuracy of every future improvement.
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
