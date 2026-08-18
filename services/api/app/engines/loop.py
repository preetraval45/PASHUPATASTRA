"""The remediation loop, wired to real executors.

Act, observe over a window, roll back if it did not hold, then learn from what
happened. `packages/core` owns the sequencing; this module supplies the runner,
the observer, and the policy authority it needs.

The part worth reading twice is `_authorise`. A rollback is an execution, so it
needs its own Dharma verdict — the one issued for the original action names a
different action ID and `require_verdict` rejects it. Reusing it would be a
policy bypass wearing the shape of a convenience.
"""

from __future__ import annotations

from datetime import datetime

from pashupatastra import (
    ActionSpec,
    Environment,
    RiskContext,
    Verdict,
    evaluate,
    require_verdict,
)
from pashupatastra.learning import ExecutionHistory, Prediction, learn
from pashupatastra.incidents import VerificationCheck
from pashupatastra.observation import WindowObserver, as_checks
from pashupatastra.registry import get as get_action
from pashupatastra.remediation import Disposition, Remediation, Remediator
from pashupatastra.smriti import Smriti
from pydantic import BaseModel

from ..config import get_settings
from . import astra
from .audit import AUDIT, AuditKind, AuditRecord

HISTORY = ExecutionHistory()
"""Process-wide, like the audit log. In-memory until it moves to Postgres — the
novelty penalty is per-process until then, which understates familiarity after a
restart rather than overstating it."""

MEMORY = Smriti()


class ExecutionFailed(RuntimeError):
    """The executor ran and reported failure. Distinct from refusing to run."""


class LoopResult(BaseModel):
    incident_ref: str | None
    action_id: str
    disposition: Disposition
    reason: str
    verified: bool
    checks: list[dict[str, object]] = []
    rollback_action_id: str | None = None
    learned: bool = False


def _authorise(
    action: ActionSpec,
    incident_ref: str | None,
    environment: Environment,
    now: datetime,
) -> Verdict:
    """Issue a fresh verdict for an action the loop decided to take on its own.

    Used for rollbacks. The context is derived from execution history rather than
    supplied, so an undo that has failed here before is scored as riskier — and
    if Dharma will not grant it autonomously, the caller raises rather than
    executing, which surfaces as ROLLBACK_FAILED and reaches a human.
    """
    context = HISTORY.context_for(
        action.id,
        environment,
        now,
        RiskContext(environment=environment, dry_run=get_settings().dry_run),
    )
    verdict = evaluate(action, context, incident_ref=incident_ref)
    AUDIT.append(
        AuditRecord(
            kind=AuditKind.POLICY_EVALUATION,
            actor="astra:loop",
            incident_ref=incident_ref,
            summary=(
                f"rollback {action.id}: risk {verdict.effective_risk} → {verdict.tier}"
            ),
            detail=verdict.model_dump(mode="json"),
        )
    )
    return verdict


def _runner(
    primary: ActionSpec,
    verdict: Verdict,
    incident_ref: str | None,
    environment: Environment,
    actor: str,
    now: datetime,
):
    """Adapt astra.execute into the loop's Runner, which raises on failure."""

    def run(action: ActionSpec, params: dict[str, str]) -> str:
        # The supplied verdict authorises exactly one action. Anything else the
        # loop decides to run — the rollback — is authorised separately.
        authority = (
            verdict
            if action.id == primary.id
            else _authorise(action, incident_ref, environment, now)
        )
        result = astra.execute(action.id, authority, params=params, actor=actor)
        if not result.succeeded:
            raise ExecutionFailed(result.output)
        return result.output

    return run


def _executor():
    """The live router, or None when this process may not write."""
    settings = get_settings()
    if not settings.live_execution_enabled:
        return None
    return astra.live_executor()


def remediate(
    action_id: str,
    verdict: Verdict,
    params: dict[str, str] | None = None,
    incident_ref: str | None = None,
    actor: str = "agent:orchestrator",
    tenant: str = "default",
    summary: str | None = None,
    predicted: Prediction | None = None,
    observed: Prediction | None = None,
    diagnosis_correct: bool | None = None,
    entities: list[str] | None = None,
    signals: list[str] | None = None,
    observer: WindowObserver | None = None,
) -> tuple[Remediation, bool]:
    """Run one guarded remediation end to end, and learn from the result.

    Returns the remediation and whether it was written to memory. Learning is
    skipped only when there is no incident to file it against, never because the
    outcome was bad.
    """
    action = get_action(action_id)

    # Checked before the loop starts, not inside the runner. Remediator treats
    # any runner exception as "the execution failed" and responds by rolling
    # back — so a PolicyViolation swallowed there would turn an unauthorised
    # request into a real rollback, authorised on its own verdict, undoing
    # something that never ran. Refusing up front is the only safe order.
    require_verdict(verdict, action)

    settings = get_settings()
    environment = settings.environment
    now = datetime.now().astimezone()

    router = _executor()
    watcher = observer or WindowObserver()

    def observe(spec: ActionSpec, spec_params: dict[str, str]):
        if router is None:
            # Dry-run: nothing was changed, so there is no post-state to read and
            # nothing to wait for. Returning immediately rather than opening a
            # window — sampling an unchanged system for two minutes only delays
            # the same answer. Unobserved, never passed: missing observation does
            # not count as success.
            return [
                VerificationCheck(
                    name="observation",
                    expected="observable",
                    observed="dry-run: nothing was changed to observe",
                    passed=None,
                )
            ]

        return as_checks(watcher.watch(spec.id, lambda: router.observe(spec, spec_params)))

    def capture(spec: ActionSpec, spec_params: dict[str, str]) -> dict[str, str]:
        return router.capture(spec, spec_params) if router is not None else {}

    remediator = Remediator(
        runner=_runner(action, verdict, incident_ref, environment, actor, now),
        observer=observe,
        rollback_of=lambda aid: _rollback_spec(aid),
        capture=capture,
    )
    result = remediator.remediate(action, verdict, params or {})

    AUDIT.append(
        AuditRecord(
            kind=AuditKind.EXECUTION_RESULT,
            actor=actor,
            incident_ref=incident_ref,
            summary=f"loop: {action.id} → {result.disposition}",
            detail={"reason": result.reason, "disposition": result.disposition.value},
        )
    )

    if incident_ref is None:
        return result, False

    learn(
        memory=MEMORY,
        history=HISTORY,
        tenant=tenant,
        incident_ref=incident_ref,
        remediation=result,
        environment=environment,
        now=now,
        summary=summary or f"{action.id}: {result.reason}",
        diagnosis_correct=diagnosis_correct,
        predicted=predicted,
        observed=observed,
        entities=entities or [],
        signals=signals or [],
    )
    return result, True


def _rollback_spec(action_id: str) -> ActionSpec | None:
    spec = get_action(action_id)
    if spec.rollback_action_id is None:
        return None
    try:
        return get_action(spec.rollback_action_id)
    except KeyError:
        return None
