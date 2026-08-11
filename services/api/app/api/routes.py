"""HTTP surface."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pashupatastra import (
    ActionSpec,
    Environment,
    Incident,
    PolicyViolation,
    RiskContext,
    Verdict,
    Verification,
    evaluate,
)
from pashupatastra.registry import all_actions, get as get_action
from pydantic import BaseModel

from ..config import get_settings
from ..engines import astra, verification as verify_engine
from ..engines.audit import AUDIT, AuditKind, AuditRecord
from ..store import STORE

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    durable = AUDIT.durable
    return {
        # "degraded" when the audit trail is in memory: it survives no restart,
        # which is a correctness problem in production, not a convenience one.
        "status": "ok" if durable and STORE.durable else "degraded",
        "environment": settings.environment,
        "dry_run": settings.dry_run,
        "audit_storage": "postgres" if durable else "memory",
        "incidents": len(STORE.all()),
        "audit_records": len(AUDIT),
    }


# --- incidents ---------------------------------------------------------------


@router.get("/incidents", response_model=list[Incident])
def list_incidents() -> list[Incident]:
    return STORE.all()


@router.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str) -> Incident:
    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")
    return incident


# --- actions & policy --------------------------------------------------------


@router.get("/actions", response_model=list[ActionSpec])
def list_actions() -> list[ActionSpec]:
    """The closed registry. Actions not listed here cannot be executed."""
    return all_actions()


class EvaluateRequest(BaseModel):
    action_id: str
    incident_ref: str | None = None
    environment: Environment | None = None
    blast_radius_entities: int = 0
    blast_radius_users: int = 0
    diagnostic_confidence: float = 1.0
    executed_here_before: bool = True
    agent_risk_limit: int | None = None


@router.post("/policy/evaluate", response_model=Verdict)
def evaluate_policy(request: EvaluateRequest) -> Verdict:
    """Dharma. The only way to obtain authorization to execute."""
    settings = get_settings()
    try:
        action = get_action(request.action_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    verdict = evaluate(
        action,
        RiskContext(
            environment=request.environment or settings.environment,
            blast_radius_entities=request.blast_radius_entities,
            blast_radius_users=request.blast_radius_users,
            diagnostic_confidence=request.diagnostic_confidence,
            executed_here_before=request.executed_here_before,
            dry_run=settings.dry_run,
        ),
        incident_ref=request.incident_ref,
        agent_risk_limit=request.agent_risk_limit,
    )
    # Denials are recorded too — they document where autonomy stopped and why.
    AUDIT.append(
        AuditRecord(
            kind=AuditKind.POLICY_EVALUATION,
            actor="dharma",
            incident_ref=request.incident_ref,
            summary=f"{action.id}: risk {verdict.effective_risk} → {verdict.tier}",
            detail=verdict.model_dump(mode="json"),
        )
    )
    STORE.verdicts[f"{action.id}:{verdict.granted_at or datetime.now().astimezone()}"] = verdict
    return verdict


class ExecuteRequest(BaseModel):
    action_id: str
    verdict: Verdict
    params: dict[str, str] = {}
    actor: str = "human:operator"


@router.post("/actions/execute", response_model=astra.ExecutionResult)
def execute_action(request: ExecuteRequest) -> astra.ExecutionResult:
    try:
        return astra.execute(
            request.action_id,
            request.verdict,
            params=request.params,
            actor=request.actor,
        )
    except PolicyViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ApproveRequest(BaseModel):
    verdict: Verdict
    approver: str


@router.post("/policy/approve", response_model=Verdict)
def approve(request: ApproveRequest) -> Verdict:
    verdict = request.verdict
    if verdict.tier.value == "denied":
        raise HTTPException(status_code=403, detail="denied verdicts cannot be approved")
    verdict.granted_by = f"human:{request.approver}"
    verdict.granted_at = datetime.now().astimezone()
    AUDIT.append(
        AuditRecord(
            kind=AuditKind.APPROVAL,
            actor=verdict.granted_by,
            incident_ref=verdict.incident_ref,
            summary=f"approved {verdict.action_id} at tier {verdict.tier}",
        )
    )
    return verdict


# --- verification ------------------------------------------------------------


class VerifyRequest(BaseModel):
    action_id: str
    observed: dict[str, str]
    incident_ref: str | None = None
    window_seconds: int = 60


@router.post("/verification/observe", response_model=Verification)
def observe(request: VerifyRequest) -> Verification:
    try:
        action = get_action(request.action_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    verification = Verification(
        window_seconds=request.window_seconds,
        checks=verify_engine.build_checks(action.expected_post_state),
    )
    return verify_engine.observe(verification, request.observed, incident_ref=request.incident_ref)


# --- audit -------------------------------------------------------------------


@router.get("/audit", response_model=list[AuditRecord])
def audit(incident_ref: str | None = None, limit: int = 100) -> list[AuditRecord]:
    return AUDIT.records(incident_ref=incident_ref, limit=limit)
