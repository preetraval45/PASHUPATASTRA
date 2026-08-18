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
    VerificationCheck,
    evaluate,
)
from pashupatastra.approvals import ApprovalLog, Decision
from pashupatastra.learning import Prediction
from pashupatastra.registry import all_actions, get as get_action
from pydantic import BaseModel

from ..config import get_settings
from ..engines import astra, loop as loop_engine, verification as verify_engine
from ..engines.audit import AUDIT, AuditKind, AuditRecord
from ..db import PostgresStore
from ..engines.buddhi import model_health
from ..graph import GraphStore
from ..store import STORE

GRAPH = GraphStore()

APPROVALS = ApprovalLog()
"""Process-wide, like the audit log. In-memory for now — the fatigue numbers are
per-process until this moves to Postgres alongside the audit trail."""

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
        # Which model is wired up, and what it has spent. `configured: false`
        # means the deterministic stub is answering — the correct default for a
        # fresh checkout, and something an operator should see rather than infer
        # from suspiciously empty reasoning output.
        "model": model_health(),
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


class RemediateRequest(BaseModel):
    action_id: str
    verdict: Verdict
    params: dict[str, str] = {}
    incident_ref: str | None = None
    actor: str = "agent:orchestrator"
    tenant: str = "default"
    summary: str | None = None
    predicted_entities: int | None = None
    predicted_users: int | None = None
    observed_entities: int | None = None
    observed_users: int | None = None
    entities: list[str] = []
    signals: list[str] = []


class RemediateResponse(BaseModel):
    action_id: str
    disposition: str
    reason: str
    verified: bool
    rollback_ran: bool
    learned: bool
    checks: list[VerificationCheck] = []


@router.post("/actions/remediate", response_model=RemediateResponse)
def remediate_action(request: RemediateRequest) -> RemediateResponse:
    """The closed loop: act, verify over a window, roll back, learn.

    Distinct from `/actions/execute`, which runs one action and stops. This one
    owns the consequences — and because a rollback is itself an execution, it is
    authorised by its own Dharma verdict rather than the one supplied here.
    """
    predicted = observed = None
    if request.predicted_entities is not None:
        predicted = Prediction(
            entities=request.predicted_entities, users=request.predicted_users or 0
        )
    if request.observed_entities is not None:
        observed = Prediction(
            entities=request.observed_entities, users=request.observed_users or 0
        )

    try:
        result, learned = loop_engine.remediate(
            request.action_id,
            request.verdict,
            params=request.params,
            incident_ref=request.incident_ref,
            actor=request.actor,
            tenant=request.tenant,
            summary=request.summary,
            predicted=predicted,
            observed=observed,
            entities=request.entities,
            signals=request.signals,
        )
    except PolicyViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RemediateResponse(
        action_id=result.action_id,
        disposition=result.disposition.value,
        reason=result.reason,
        verified=result.attempt.verified if result.attempt else False,
        rollback_ran=result.rollback is not None,
        learned=learned,
        checks=result.attempt.checks if result.attempt else [],
    )


class ApproveRequest(BaseModel):
    verdict: Verdict
    approver: str
    presented_at: datetime | None = None
    """When the request reached the operator's screen.

    Supplied by the client because only the client knows it. The gap between
    Dharma issuing a verdict and a human seeing it is queueing, not deliberation,
    and timing from issuance would flatter every measurement. Absent, the
    decision is recorded without a duration rather than with a wrong one.
    """


class DenyRequest(BaseModel):
    verdict: Verdict
    approver: str
    reason: str
    presented_at: datetime | None = None


@router.post("/policy/approve", response_model=Verdict)
def approve(request: ApproveRequest) -> Verdict:
    verdict = request.verdict
    if verdict.tier.value == "denied":
        raise HTTPException(status_code=403, detail="denied verdicts cannot be approved")
    if verdict.expires_at is not None and datetime.now().astimezone() > verdict.expires_at:
        # A stale approval must visibly fail rather than quietly succeed and then
        # be refused later by `is_executable`, which would leave the operator
        # believing they had authorised something.
        raise HTTPException(
            status_code=409,
            detail=f"verdict for {verdict.action_id} expired at {verdict.expires_at.isoformat()}",
        )

    now = datetime.now().astimezone()
    verdict.granted_by = f"human:{request.approver}"
    verdict.granted_at = now
    _record_decision(verdict, Decision.APPROVED, request.approver, request.presented_at, now)

    AUDIT.append(
        AuditRecord(
            kind=AuditKind.APPROVAL,
            actor=verdict.granted_by,
            incident_ref=verdict.incident_ref,
            summary=f"approved {verdict.action_id} at tier {verdict.tier}",
        )
    )
    return verdict


@router.post("/policy/deny", response_model=Verdict)
def deny(request: DenyRequest) -> Verdict:
    """Refuse an action. A first-class outcome, not an error path.

    Returns the verdict with the refusal recorded rather than raising: a denial
    is the approval step working, and expressing it as an HTTP error would make
    the client's success path the one where a human said yes.
    """
    verdict = request.verdict
    now = datetime.now().astimezone()
    verdict.denial_reason = request.reason
    verdict.granted_by = None
    _record_decision(verdict, Decision.DENIED, request.approver, request.presented_at, now)

    AUDIT.append(
        AuditRecord(
            kind=AuditKind.APPROVAL,
            actor=f"human:{request.approver}",
            incident_ref=verdict.incident_ref,
            summary=f"denied {verdict.action_id}: {request.reason}",
        )
    )
    return verdict


def _record_decision(
    verdict: Verdict,
    decision: Decision,
    approver: str,
    presented_at: datetime | None,
    now: datetime,
) -> None:
    """Log the decision for the fatigue measurement."""
    request = APPROVALS.present(verdict, at=presented_at or now)
    APPROVALS.resolve(request, decision, at=now, approver=approver)


@router.get("/policy/approvals/fatigue")
def approval_fatigue() -> dict[str, object]:
    """Whether the approval step is doing anything.

    Exposed as an endpoint rather than buried in a log because a metric nobody
    looks at cannot change behaviour — and this one is meant to be uncomfortable.
    `looks_decorative` requires *both* near-total approval and near-instant
    decisions; either alone is consistent with a well-calibrated system.
    """
    APPROVALS.expire_stale(datetime.now().astimezone())
    fatigue = APPROVALS.fatigue()
    return {**fatigue.summary(), "by_approver": fatigue.by_approver()}


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


# --- ingestion ---------------------------------------------------------------


@router.post("/ingest/otlp")
def ingest_otlp(payload: dict) -> dict[str, object]:
    """OTLP/HTTP trace endpoint.

    Point an OpenTelemetry collector's OTLP/HTTP exporter here. Traces are the
    strongest edge source available: a span with a parent is direct evidence
    that one service called another.
    """
    from ..engines.drishti import Drishti

    result = Drishti(connectors=[]).receive_otlp(payload)
    return {
        "events_stored": result.events_stored,
        "nodes_upserted": result.nodes_upserted,
        "edges_upserted": result.edges_upserted,
        "quarantined": result.quarantined,
    }


# --- topology ----------------------------------------------------------------


@router.get("/topology/blast-radius/{entity_key:path}")
def blast_radius(entity_key: str, max_depth: int = 10) -> dict[str, object]:
    """What breaks when this breaks, and roughly how many users notice.

    An input to risk scoring, so it is served from the graph rather than
    recomputed here — a second implementation would be a second answer.
    """
    radius = GRAPH.blast_radius(entity_key, max_depth=max_depth)
    return {
        "origin": radius.origin,
        "affected": radius.affected,
        "entity_count": radius.entity_count,
        "estimated_users": radius.estimated_users,
    }


@router.get("/topology")
def topology() -> dict[str, int]:
    nodes, edges = GRAPH.counts()
    return {"nodes": nodes, "edges": edges}


@router.get("/topology/graph")
def topology_graph(limit: int = 400) -> dict:
    """Nodes and edges for the service map, each node carrying its worst recent
    severity rather than its latest — a service that went critical and then
    reported info seconds later is flapping, not healthy."""
    return GRAPH.snapshot(limit=limit)


# --- entities ----------------------------------------------------------------


@router.get("/entities/{entity_key:path}")
def entity_detail(entity_key: str, events: int = 50) -> dict[str, object]:
    """One entity: what it is, what depends on it, and what it has been saying.

    Blast radius is included because "what breaks if this breaks" is the first
    question anyone asks about an entity, and making it a second request invites
    a view that renders without it.
    """
    store = PostgresStore()
    node = store.entity(entity_key)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown entity {entity_key}")

    radius = GRAPH.blast_radius(entity_key)
    return {
        "entity": node,
        "blast_radius": {
            "affected": radius.affected,
            "entity_count": radius.entity_count,
            "estimated_users": radius.estimated_users,
        },
        "events": store.entity_events(entity_key, limit=events),
    }


# --- audit -------------------------------------------------------------------


@router.get("/audit", response_model=list[AuditRecord])
def audit(incident_ref: str | None = None, limit: int = 100) -> list[AuditRecord]:
    return AUDIT.records(incident_ref=incident_ref, limit=limit)
