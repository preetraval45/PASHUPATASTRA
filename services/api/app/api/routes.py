"""HTTP surface."""

from __future__ import annotations

import logging

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
from ..engines.buddhi import model_health
from ..graph import GraphStore, entitystore
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
        # The backend names itself. This used to be hardcoded to "postgres",
        # which meant a DynamoDB deployment reported the wrong store — and the
        # whole point of this field is that a reader can trust what it says.
        "audit_storage": getattr(AUDIT._store(), "name", "memory") if durable else "memory",
        "incidents": len(STORE.all()),
        "audit_records": len(AUDIT),
        # Which model is wired up, and what it has spent. `configured: false`
        # means the deterministic stub is answering — the correct default for a
        # fresh checkout, and something an operator should see rather than infer
        # from suspiciously empty reasoning output.
        "model": model_health(),
        # Whether repeat questions cost anything. On a per-minute token
        # allowance this is the difference between serving a burst of visitors
        # and refusing them, and a cache that silently stops working looks
        # exactly like one that works — the answers stay correct, they just get
        # paid for again. So it reports itself.
        "chat_cache": _cache_health(),
    }


def _cache_health() -> dict[str, object]:
    from ..agent.cache import CACHE

    return {
        "durable": CACHE.durable,
        "in_process": len(CACHE._local),
        "store": type(CACHE.store).__name__ if CACHE.store else None,
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
    """The closed registry. Actions not listed here cannot be executed.

    Filtered to the deployment's domain when one is configured. Filtering the
    list does not narrow what `get` resolves — an action still registered but
    not listed remains executable if a plan names it, because a plan that
    referenced a rollback which quietly stopped resolving would fail at the
    moment the rollback was needed.
    """
    return all_actions(get_settings().action_domain)


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
    snapshot = GRAPH.snapshot(limit=limit)
    _overlay_open_incidents(snapshot)
    return snapshot


# An open incident outranks a quiet telemetry window, but only a critical one
# earns the map's top colour. The first version promoted `high` to critical too
# and turned all eleven nodes red — which tells a reader as little as all eleven
# grey did. A map is worth having only where it distinguishes.
_INCIDENT_SEVERITY = {"critical": "critical", "high": "warning",
                      "medium": "warning", "low": "info"}
_RANK = {"critical": 3, "warning": 2, "info": 1}


def _overlay_open_incidents(snapshot: dict) -> None:
    """Colour a node by any open incident that touches it.

    Telemetry severity is windowed — the worst thing seen in the last fifteen
    minutes — which is right for a live system and wrong for an entity with an
    open critical incident against it and no new events. The map read "no data"
    for every host on the board while three incidents sat open, because the
    scripted signals had aged out of the window. Nothing was broken; the map was
    answering a narrower question than the one a reader asks of it.

    So the two are combined, worst wins. An entity is shown as the most serious
    thing currently true about it, not the most recent thing said about it.
    """
    touched: dict[str, str] = {}
    for incident in STORE.all():
        if incident.state in {"resolved", "closed"}:
            continue
        level = _INCIDENT_SEVERITY.get(str(incident.severity), "warning")
        keys = {entity.key() for entity in incident.affected_entities}
        keys |= {link.entity.key() for link in incident.causal_chain}
        for key in keys:
            if _RANK[level] > _RANK.get(touched.get(key, ""), 0):
                touched[key] = level

    for node in snapshot.get("nodes", []):
        incident_level = touched.get(node["key"])
        if incident_level is None:
            continue
        current = node.get("severity")
        if _RANK[incident_level] > _RANK.get(current or "", 0):
            node["severity"] = incident_level


@router.get("/intel")
def intel(limit: int = 50, source: str | None = None) -> dict[str, object]:
    """Recent threat intelligence, as stored.

    Served from our own store, never proxied. A route that fetched from CISA or
    abuse.ch on request would tell those services who is reading what, and would
    fail whenever they do; the schedule already put this on disk.

    Entries keep their `verification` label. A reader deciding what to do with
    "somebody submitted this URL an hour ago" needs it to be distinguishable
    from "CISA has observed this being exploited", and by the time both are
    rendered as cards they look identical without it.
    """
    from ..feeds.sources import FEEDS

    known = sorted(FEEDS)
    sources = [source] if source else known
    if source and source not in known:
        raise HTTPException(
            status_code=404, detail=f"unknown source {source}; known: {', '.join(known)}"
        )

    store = entitystore()
    reader = getattr(store, "recent_events", None)
    entries = reader(sources=sources, limit=min(limit, 200)) if reader else []
    return {
        "sources": known,
        "count": len(entries),
        "entries": entries,
    }


@router.get("/intel/status")
def intel_status() -> dict[str, object]:
    """How current each feed is, and when it last moved.

    A feed that has quietly stopped looks exactly like a quiet feed. The cursor
    is the difference, so it is published rather than kept for debugging.
    """
    from ..backend import durable
    from ..feeds.sources import FEEDS

    backend = durable()
    cursors = {}
    for name in sorted(FEEDS):
        read = getattr(backend, "get_feed_cursor", None)
        cursors[name] = read(name) if read else None
    return {"feeds": cursors, "durable": backend is not None}


# --- entities ----------------------------------------------------------------


@router.get("/entities/{entity_key:path}")
def entity_detail(entity_key: str, events: int = 50) -> dict[str, object]:
    """One entity: what it is, what depends on it, and what it has been saying.

    Blast radius is included because "what breaks if this breaks" is the first
    question anyone asks about an entity, and making it a second request invites
    a view that renders without it.
    """
    store = entitystore()
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


@router.get("/events/{event_id}")
def event(event_id: str) -> dict[str, object]:
    """One event, so a citation can be followed to the thing it cites.

    Every hypothesis and every causal step names evidence by id. Without this
    the id is decoration: it looks checkable, a reader takes it on trust, and an
    invented reference is indistinguishable from a real one.
    """
    record = entitystore().event(event_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown event {event_id}")
    return record


# --- audit -------------------------------------------------------------------


@router.get("/audit", response_model=list[AuditRecord])
def audit(incident_ref: str | None = None, limit: int = 100) -> list[AuditRecord]:
    return AUDIT.records(incident_ref=incident_ref, limit=limit)


class ChatRequest(BaseModel):
    incident_id: str
    message: str


@router.post("/agent/chat")
def agent_chat(request: ChatRequest) -> dict[str, object]:
    """Ask Sati about one incident.

    Scoped to an incident on purpose. A general "ask the console anything" box
    on a public site is an interface for enumerating the estate, and there is no
    question worth answering here that is not about something already on screen.

    The route can read and nothing else. It holds no execute path, and the tools
    it offers are derived from `ActionSpec.read_only` rather than listed by hand
    — see `app/agent/tools.py`.
    """
    from ..agent import chat as chat_engine
    from ..engines.buddhi import gateway
    from pashupatastra.gateway import GatewayError

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message must not be empty")
    if len(message) > 2000:
        # A cap in characters, before any tokens are spent. The token ceiling
        # bounds the conversation; this bounds what one POST can put into it.
        raise HTTPException(status_code=422, detail="message is too long")

    incident = STORE.get(request.incident_id)
    if incident is None:
        raise HTTPException(
            status_code=404, detail=f"unknown incident {request.incident_id}"
        )

    provider = gateway().provider
    if not getattr(provider, "available", lambda: True)():
        # 503 rather than a fabricated reply. A chat panel that invents answers
        # when unconfigured is worse than one that is visibly switched off.
        raise HTTPException(
            status_code=503,
            detail="no model is configured; set the model API key to enable chat",
        )

    try:
        result = chat_engine.answer(
            incident=incident,
            message=message,
            store=STORE,
            graph=entitystore(),
            audit=AUDIT,
            gateway=gateway(),
        )
    except GatewayError as error:
        # Never the provider's own words. A rate-limit body from Groq carries
        # the organisation id and a billing upgrade link, and this endpoint is
        # public — so the detail is logged and a plain sentence is returned.
        logging.getLogger(__name__).warning("chat unavailable: %s", error)
        rate_limited = "429" in str(error) or "rate limit" in str(error).lower()
        raise HTTPException(
            status_code=429 if rate_limited else 503,
            detail=(
                "The assistant is busy right now — the free model allowance is "
                "per minute. Try again shortly."
                if rate_limited
                else "The assistant is unavailable right now."
            ),
        ) from error

    AUDIT.append(_turn_record(result, incident, message))

    if result.proposed_action_id:
        _queue_proposal(result, incident)

    return result.model_dump(mode="json")


MAX_RECORDED_QUESTION = 240


def _asked(message: str) -> str:
    """The question, made safe to keep and to show.

    It is worth keeping: "why did it say that" is unanswerable without knowing
    what it was asked. It is also text a stranger typed into a public box, on
    its way to an append-only record rendered on a public page — so it is capped
    and stripped of control characters first. Neither is about the model; both
    are about what a permanent public trail should accept from anyone.
    """
    cleaned = "".join(c for c in message if c.isprintable() or c == " ").strip()
    if len(cleaned) > MAX_RECORDED_QUESTION:
        return cleaned[:MAX_RECORDED_QUESTION] + "…"
    return cleaned


def _turn_record(result, incident, message: str) -> AuditRecord:
    """Everything needed to answer "why did it say that", months later.

    The summary is the line the audit page shows by default, so it carries the
    facts that decide whether to trust the answer — which model, whether it was
    grounded — and no visitor text. The detail carries the rest, including the
    tool-call trace and the prompt fingerprint.

    Recorded for cached turns too, with the cost and trace of the run that
    produced the answer. A cache hit is still an answer given to someone, and a
    trail that skips them would show a page of questions with no replies.
    """
    tools = [entry["name"] for entry in result.trace if entry.get("kind") == "tool_call"]
    return AuditRecord(
        at=datetime.now().astimezone(),
        kind=AuditKind.AGENT_TURN,
        actor="sati.analyst",
        incident_ref=incident.id,
        summary=(
            f"answered · {result.model or 'unknown model'} · "
            + ("from cache" if result.cached else f"{result.tokens} tokens")
            + (f" · called {', '.join(tools)}" if tools else "")
            + ("" if result.grounded else " · NOT GROUNDED")
            + ("" if result.answerable else " · not in the evidence")
        ),
        detail={
            "asked": _asked(message),
            "model": result.model,
            "provider": result.provider,
            "prompt_version": result.prompt_version,
            "prompt_digest": result.prompt_digest,
            "tokens": result.tokens,
            "cached": result.cached,
            "grounded": result.grounded,
            "answerable": result.answerable,
            "truncated": result.truncated,
            "evidence_refs": result.evidence_refs,
            "dropped_refs": result.dropped_refs,
            "proposed_action_id": result.proposed_action_id,
            "answer": result.answer,
            "trace": result.trace,
        },
    )


def _queue_proposal(result, incident) -> None:
    """Route a proposal through Dharma and into the approval queue.

    The same `evaluate` every other caller uses, and the same `ApprovalLog` a
    human's request lands in. There is no second path for AI-initiated actions
    — that is the whole of R20, and building a parallel one "for the agent"
    would be the exact shortcut the rule exists to forbid.

    Scored exactly as a person's request would be, and deliberately so.
    `agent_risk_limit` is *not* passed, which looks like the cautious choice
    until you follow it: it forces `DENIED`, and `/policy/approve` refuses a
    denied verdict. Every proposal would dead-end where R20 asks for it to
    reach a human. The flag answers "may this agent act alone" — always no
    here — and using it to answer "may a human approve this" conflates the two.

    What keeps the agent from acting is structural rather than a risk number:
    this route has no execute path, and no risk-bearing action is in its tool
    set. A verdict is queued; a visitor is anonymous, and an anonymous approval
    is not an approval.
    """
    from ..agent.roles import ANALYST

    settings = get_settings()
    action = get_action(result.proposed_action_id)
    verdict = evaluate(
        action,
        RiskContext(
            environment=settings.environment,
            blast_radius_entities=incident.impact.blast_radius_entities,
            blast_radius_users=incident.impact.estimated_users_affected,
            diagnostic_confidence=(
                incident.top_hypothesis.confidence if incident.top_hypothesis else 0.0
            ),
            dry_run=settings.dry_run,
        ),
        incident_ref=incident.id,
    )
    result.verdict = verdict.model_dump(mode="json")

    now = datetime.now().astimezone()
    request = APPROVALS.present(verdict, at=now)
    result.approval_id = f"{verdict.action_id}:{now.isoformat()}"

    AUDIT.append(
        AuditRecord(
            at=now,
            kind=AuditKind.POLICY_EVALUATION,
            actor=ANALYST.principal,
            incident_ref=incident.id,
            summary=(
                f"proposed {action.id}: risk {verdict.effective_risk} → "
                f"{verdict.tier}, awaiting a human"
            ),
            detail={"verdict": result.verdict, "pending": request.pending},
        )
    )
