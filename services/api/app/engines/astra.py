"""Astra — the action engine.

Every path to a connector's write API runs through `execute`, and `execute`
requires a Dharma verdict as an argument. There is no bypass, including in dev
tooling and test fixtures (docs/specs/Policy%20Model.md).
"""

from __future__ import annotations

from datetime import datetime

from pashupatastra import ActionSpec, Verdict, require_verdict
from pashupatastra.registry import get as get_action
from pydantic import BaseModel

from ..config import get_settings
from .audit import AUDIT, AuditKind, AuditRecord


class ExecutionResult(BaseModel):
    action_id: str
    started_at: datetime
    finished_at: datetime
    succeeded: bool
    dry_run: bool
    output: str


class Executor:
    """Maps an action ID to a connector call.

    Phase 3 replaces these stubs with real connectors. The signature is the
    contract: an executor never receives a raw command, only a registered action
    and its parameters.
    """

    def run(self, action: ActionSpec, params: dict[str, str]) -> str:
        raise NotImplementedError


class DryRunExecutor(Executor):
    def run(self, action: ActionSpec, params: dict[str, str]) -> str:
        return f"[dry-run] would execute {action.id} with {params or '{}'}"


def live_executor() -> Executor:
    """The real write path, built only when both gates are open.

    Constructed lazily rather than at import: a process that is not permitted to
    write should not hold a configured cluster client at all, so a bug cannot
    reach one.
    """
    from .executors import KubernetesExecutor, NotifyExecutor, Router

    settings = get_settings()
    return Router(  # type: ignore[return-value]
        KubernetesExecutor(context=settings.kube_context),
        NotifyExecutor(),
    )


def execute(
    action_id: str,
    verdict: Verdict | None,
    params: dict[str, str] | None = None,
    actor: str = "agent:orchestrator",
    executor: Executor | None = None,
) -> ExecutionResult:
    """The single execution path. A missing or invalid verdict raises."""
    action = get_action(action_id)
    verdict = require_verdict(verdict, action)

    settings = get_settings()
    # Three ways to stay in dry-run and only one way out. `live_execution_enabled`
    # already requires both `dry_run: false` and this environment being named in
    # `live_environments`; a per-verdict constraint can additionally force dry-run
    # but never grant live execution. Every gate can veto; none can override.
    dry_run = (
        not settings.live_execution_enabled
        or verdict.constraints.get("dry_run") == "true"
    )
    params = params or {}

    # Written before execution, not after — a crash mid-action must still leave
    # evidence that the attempt happened.
    AUDIT.append(
        AuditRecord(
            kind=AuditKind.EXECUTION_ATTEMPT,
            actor=actor,
            incident_ref=verdict.incident_ref,
            summary=f"executing {action.id} (tier={verdict.tier}, risk={verdict.effective_risk})",
            detail={"params": params, "dry_run": dry_run},
        )
    )

    started = datetime.now().astimezone()
    runner = executor or (DryRunExecutor() if dry_run else live_executor())
    try:
        output = runner.run(action, params) if not dry_run else DryRunExecutor().run(action, params)
        succeeded = True
    except Exception as exc:  # noqa: BLE001 - failure is a recorded outcome, not a crash
        output, succeeded = f"{type(exc).__name__}: {exc}", False

    result = ExecutionResult(
        action_id=action.id,
        started_at=started,
        finished_at=datetime.now().astimezone(),
        succeeded=succeeded,
        dry_run=dry_run,
        output=output,
    )
    AUDIT.append(
        AuditRecord(
            kind=AuditKind.EXECUTION_RESULT,
            actor=actor,
            incident_ref=verdict.incident_ref,
            summary=f"{action.id} {'succeeded' if succeeded else 'failed'}",
            detail=result.model_dump(mode="json"),
        )
    )
    return result
