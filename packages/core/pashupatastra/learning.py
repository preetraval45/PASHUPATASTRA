"""What the system learns from having acted.

Three things feed back: outcomes into Smriti, execution history into the novelty
penalty, and predicted-vs-actual blast radius into a published estimation error.

The bias worth designing against is that successes are easier to record than
failures. A loop that remembers what worked and quietly forgets what did not
gets more confident over time without getting better, so `learn()` is a single
path that writes either way.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from .dharma import Environment, RiskContext
from .remediation import Disposition, Remediation
from .smriti import MemoryKind, MemoryRecord, Outcome, Smriti, Trust

# How long an execution stays relevant to novelty. An action last run a year ago
# in an infrastructure that has since been rebuilt is closer to novel than to
# familiar.
NOVELTY_HORIZON = timedelta(days=180)


class Familiarity(StrEnum):
    NOVEL = "novel"
    ATTEMPTED = "attempted"
    """Run here before, but never successfully. Not the same as untried."""

    PROVEN = "proven"


@dataclass(frozen=True)
class Prediction:
    """A blast-radius estimate, or the observation it is later graded against."""

    entities: int
    users: int


@dataclass(frozen=True)
class ExecutionRecord:
    action_id: str
    environment: Environment
    at: datetime
    disposition: Disposition
    incident_ref: str | None = None
    predicted: Prediction | None = None
    observed: Prediction | None = None

    @property
    def succeeded(self) -> bool:
        return self.disposition is Disposition.RESOLVED


@dataclass(frozen=True)
class EstimationError:
    """How wrong the blast-radius prediction was, and in which direction.

    Signed and split rather than averaged. Under-estimation is the dangerous
    direction — it is what lets an action run autonomously that should have gone
    to a human — and a mean absolute error reports it identically to the
    harmless direction.
    """

    samples: int = 0
    underestimates: int = 0
    overestimates: int = 0
    exact: int = 0
    worst_underestimate: int = 0
    total_signed_entities: int = 0

    @property
    def underestimate_rate(self) -> float:
        return round(self.underestimates / self.samples, 4) if self.samples else 0.0

    @property
    def mean_signed_entities(self) -> float:
        """Positive means the system predicts too small on average."""
        return round(self.total_signed_entities / self.samples, 3) if self.samples else 0.0

    @property
    def calibrated(self) -> bool:
        """Never under-estimated. The only bar that matters for the risk path."""
        return self.underestimates == 0

    def summary(self) -> dict[str, object]:
        return {
            "samples": self.samples,
            "underestimates": self.underestimates,
            "overestimates": self.overestimates,
            "exact": self.exact,
            "underestimate_rate": self.underestimate_rate,
            "mean_signed_entities": self.mean_signed_entities,
            "worst_underestimate": self.worst_underestimate,
            "calibrated": self.calibrated,
        }


class ExecutionHistory:
    """Append-only record of what has actually been run, and how it went."""

    def __init__(self, horizon: timedelta = NOVELTY_HORIZON) -> None:
        self.horizon = horizon
        self._records: list[ExecutionRecord] = []

    def record(self, record: ExecutionRecord) -> ExecutionRecord:
        self._records.append(record)
        return record

    def __len__(self) -> int:
        return len(self._records)

    @property
    def records(self) -> tuple[ExecutionRecord, ...]:
        """Append-only: handed out as a tuple so a caller cannot rewrite history."""
        return tuple(self._records)

    def _relevant(
        self, action_id: str, environment: Environment, now: datetime
    ) -> list[ExecutionRecord]:
        return [
            r
            for r in self._records
            if r.action_id == action_id
            and r.environment is environment
            and now - r.at <= self.horizon
        ]

    def familiarity(
        self, action_id: str, environment: Environment, now: datetime
    ) -> Familiarity:
        """Per environment, because succeeding in dev says nothing about prod."""
        relevant = self._relevant(action_id, environment, now)
        if not relevant:
            return Familiarity.NOVEL
        if any(r.succeeded for r in relevant):
            return Familiarity.PROVEN
        return Familiarity.ATTEMPTED

    def failures(self, action_id: str, environment: Environment, now: datetime) -> int:
        return sum(1 for r in self._relevant(action_id, environment, now) if not r.succeeded)

    def context_for(
        self,
        action_id: str,
        environment: Environment,
        now: datetime,
        base: RiskContext,
    ) -> RiskContext:
        """Fill the history-derived fields of a risk context from real records.

        `RiskContext.executed_here_before` defaults to True, which suppresses the
        novelty penalty for any caller that forgets to set it. Deriving it here
        means the safe answer comes from the absence of evidence rather than from
        a caller remembering.
        """
        familiarity = self.familiarity(action_id, environment, now)
        return base.model_copy(
            update={
                "executed_here_before": familiarity is not Familiarity.NOVEL,
                "failed_here_before": self.failures(action_id, environment, now),
            }
        )

    def estimation_error(self, action_id: str | None = None) -> EstimationError:
        """Grade past blast-radius predictions against what was observed."""
        graded = [
            r
            for r in self._records
            if r.predicted is not None
            and r.observed is not None
            and (action_id is None or r.action_id == action_id)
        ]
        if not graded:
            return EstimationError()

        under = over = exact = 0
        worst = 0
        signed_total = 0
        for r in graded:
            assert r.predicted is not None and r.observed is not None
            delta = r.observed.entities - r.predicted.entities
            signed_total += delta
            if delta > 0:
                under += 1
                worst = max(worst, delta)
            elif delta < 0:
                over += 1
            else:
                exact += 1

        return EstimationError(
            samples=len(graded),
            underestimates=under,
            overestimates=over,
            exact=exact,
            worst_underestimate=worst,
            total_signed_entities=signed_total,
        )


@dataclass
class Lesson:
    """What one closed incident contributed."""

    memory: MemoryRecord
    execution: ExecutionRecord


def learn(
    *,
    memory: Smriti,
    history: ExecutionHistory,
    tenant: str,
    incident_ref: str,
    remediation: Remediation,
    environment: Environment,
    now: datetime,
    summary: str,
    diagnosis_correct: bool | None = None,
    predicted: Prediction | None = None,
    observed: Prediction | None = None,
    entities: Iterable[str] = (),
    signals: Iterable[str] = (),
) -> Lesson:
    """Write one outcome to memory and to execution history.

    Deliberately has no `only_on_success` switch and no early return for a failed
    remediation: the record is written the same way either way, with the same
    kind and retention, so a failure is as recallable later as a success.
    """
    resolved = remediation.disposition is Disposition.RESOLVED
    outcome = Outcome(
        resolved=resolved,
        diagnosis_correct=diagnosis_correct,
        action_taken=remediation.action_id,
        verification_passed=resolved,
        note=remediation.reason,
    )

    record = memory.remember(
        MemoryRecord(
            id=incident_ref,
            tenant=tenant,
            kind=MemoryKind.INCIDENT,
            text=summary,
            source="pashupatastra",
            at=now,
            # Platform-authored: this is the system's own record of its own
            # actions, not an ingested document.
            trust=Trust.VERIFIED,
            entities=frozenset(entities),
            signals=frozenset(signals),
            outcome=outcome,
        )
    )

    execution = history.record(
        ExecutionRecord(
            action_id=remediation.action_id,
            environment=environment,
            at=now,
            disposition=remediation.disposition,
            incident_ref=incident_ref,
            predicted=predicted,
            observed=observed,
        )
    )
    return Lesson(memory=record, execution=execution)


@dataclass
class LearningReport:
    """What the loop has learned, in the form it should publish about itself."""

    executions: int = 0
    resolved: int = 0
    rolled_back: int = 0
    escalated: int = 0
    estimation: EstimationError = field(default_factory=EstimationError)

    @property
    def success_rate(self) -> float:
        return round(self.resolved / self.executions, 4) if self.executions else 0.0

    def summary(self) -> dict[str, object]:
        return {
            "executions": self.executions,
            "resolved": self.resolved,
            "rolled_back": self.rolled_back,
            "escalated": self.escalated,
            "success_rate": self.success_rate,
            "estimation": self.estimation.summary(),
        }


def report(history: ExecutionHistory) -> LearningReport:
    records = history.records
    return LearningReport(
        executions=len(records),
        resolved=sum(1 for r in records if r.disposition is Disposition.RESOLVED),
        rolled_back=sum(1 for r in records if r.disposition is Disposition.ROLLED_BACK),
        escalated=sum(
            1
            for r in records
            if r.disposition in (Disposition.ESCALATED, Disposition.ROLLBACK_FAILED)
        ),
        estimation=history.estimation_error(),
    )
