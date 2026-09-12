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
from ..graph import GraphStore, chain_times, entitystore, events_by_id
from .. import progress as progress_module
from ..progress import PROGRESS
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


@router.get("/incidents/{incident_id}/draft/{kind}")
def incident_draft(incident_id: str, kind: str) -> dict[str, object]:
    """A drafted playbook or post-incident report, assembled from stored records.

    Assembled on request rather than stored. A saved draft is a document that
    can go stale against the incident it describes, and the interesting failure
    is the one nobody notices: a report citing a plan step that has since been
    re-scored. Built from the incident each time, it cannot disagree with it.

    Every line carries the refs it rests on — enforced in `drafts.Line`, which
    refuses to construct one that cites nothing — and `adopt_action_id` names
    the registered action adopting it would require. The route does not evaluate
    that action: policy is Dharma's to decide, and an endpoint that scored the
    thing it is offering would be marking its own work.
    """
    from pashupatastra.drafts import build_draft

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")
    try:
        draft = build_draft(kind, incident)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "kind": draft.kind,
        "incident_ref": draft.incident_ref,
        "title": draft.title,
        "status": draft.status,
        "adopt_action_id": draft.adopt_action_id,
        "sections": [
            {
                "title": section.title,
                "lines": [{"text": line.text, "refs": list(line.refs)} for line in section.lines],
            }
            for section in draft.sections
        ],
    }


@router.get("/incidents/{incident_id}/detection-rule")
def incident_detection_rules(incident_id: str) -> dict[str, object]:
    """Which rules could be drafted from this incident, and for what.

    A list rather than one rule, because an incident is a sequence of techniques
    and a Sigma rule detects one thing. Fusing a C2 beacon and a scheduled task
    into a single selection produces a rule that fires only when all of it is
    present at once, which is after the intrusion has finished.
    """
    from pashupatastra.sigma import rule_techniques

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")
    return {
        "incident_ref": incident.id,
        "techniques": [
            {"id": t.id, "name": t.name, "tactic": t.tactic} for t in rule_techniques(incident)
        ],
    }


@router.get("/incidents/{incident_id}/detection-rule/{technique_id}")
def incident_detection_rule(incident_id: str, technique_id: str) -> dict[str, object]:
    """A Sigma rule drafted from one step of this incident (R71).

    The events are fetched by the ids the causal step cites, so the rule rests
    on exactly the records the chain says established that step. Fetched rather
    than trusted: a step citing an id the store no longer holds yields fewer
    events, and `draft_rule` refuses rather than drafting from records it did
    not read.

    A refusal is a 422 and not a 500. "This step's telemetry carries no field
    Sigma has a name for" is a correct answer about the data, and returning it
    as a server error would file the system's honesty as a malfunction.
    """
    from pashupatastra.sigma import SigmaError, draft_rule, validate

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")

    cited = [
        ref
        for link in incident.causal_chain
        if link.attack_technique is not None and link.attack_technique.id == technique_id
        for ref in link.evidence
    ]
    events = events_by_id(entitystore(), cited)

    try:
        rule = draft_rule(incident, events, technique_id)
    except SigmaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    text = rule.to_yaml(date=incident.opened_at.strftime("%Y/%m/%d"))
    problems = validate(text)
    return {
        "incident_ref": rule.incident_ref,
        "technique": (
            {
                "id": rule.technique.id,
                "name": rule.technique.name,
                "tactic": rule.technique.tactic,
            }
            if rule.technique
            else None
        ),
        "title": rule.title,
        "status": rule.status,
        "rule_id": rule.rule_id,
        "behavioural": rule.behavioural,
        "yaml": text,
        # Reported by the route rather than asserted by it. The clause R71 is
        # measured on is that this parses as Sigma, and a route claiming so
        # without reading its own output back would be marking its own work.
        "valid": problems == [],
        "problems": problems,
        "mappings": [
            {
                "sigma_field": m.sigma_field,
                "source_field": m.source_field,
                "value": str(m.value),
                "refs": list(m.refs),
                "generalises": m.generalises,
            }
            for m in rule.mappings
        ],
        "gaps": [{"sigma_field": g.sigma_field, "reason": g.reason} for g in rule.gaps],
        "not_mapped": [
            {"sigma_field": g.sigma_field, "reason": g.reason} for g in rule.unmapped
        ],
        "refs": rule.refs,
    }


@router.get("/incidents/{incident_id}/timeline")
def incident_timeline(incident_id: str) -> dict[str, object]:
    """The causal chain placed in time, and the moments worth asking about.

    Offered rather than left free-form. The interesting counterfactuals sit at
    the boundaries between steps, and a caller made to invent a timestamp will
    invent one the records do not support — then get a refusal it reads as the
    feature being broken.
    """
    from pashupatastra.counterfactual import moments

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")

    steps = moments(incident, chain_times(entitystore(), incident))
    return {
        "incident_ref": incident.id,
        "steps": [
            {
                "index": step.index,
                "entity_key": step.entity_key,
                "transition": step.transition,
                "at": step.at.isoformat(),
                "refs": list(step.refs),
            }
            for step in steps
        ],
        # One entity per step, because those are the things an intervention
        # could have been applied to. Entities the incident merely mentions are
        # excluded: what blocking something it never recorded would have done is
        # not a question its records can answer.
        "askable": sorted({step.entity_key for step in steps}),
    }


@router.get("/incidents/{incident_id}/counterfactual")
def incident_counterfactual(incident_id: str, entity_key: str, at: str) -> dict[str, object]:
    """What acting on that entity at that moment would have prevented (R72).

    A refusal is a 422. "The timeline does not support that question" is a
    correct answer about the records — most often because the moment asked about
    precedes anything that would have justified acting — and returning it as a
    server error would file the system's honesty as a malfunction.

    The reach is walked here and the judgement is made in `packages/core`, which
    holds no store. What that split protects is that a laptop and a deployment
    cannot disagree about what a timeline and a set of edges mean together.
    """
    from pashupatastra.counterfactual import CounterfactualRefused, Intervention, counterfactual

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")
    try:
        moment = datetime.fromisoformat(at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{at!r} is not an ISO timestamp") from exc

    reach = GRAPH.blast_radius(entity_key).affected
    try:
        result = counterfactual(
            incident,
            Intervention(entity_key=entity_key, at=moment),
            chain_times(entitystore(), incident),
            reach,
        )
    except CounterfactualRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store = entitystore()
    users = 0
    for key in result.avoided_entities:
        row = store.entity(key)
        if row is not None:
            users += int(row.get("estimated_users") or 0)

    def _step(step) -> dict[str, object]:
        return {
            "index": step.index,
            "entity_key": step.entity_key,
            "transition": step.transition,
            "at": step.at.isoformat(),
            "refs": list(step.refs),
        }

    return {
        "incident_ref": result.incident_ref,
        "entity_key": entity_key,
        "at": moment.isoformat(),
        "earliest_defensible": result.earliest_defensible.isoformat(),
        "summary": result.describe(),
        "prevented": [_step(s) for s in result.prevented],
        "unavoidable": [_step(s) for s in result.unavoidable],
        "already_happened": [_step(s) for s in result.already_happened],
        "untimed": [
            {"index": u.index, "entity_key": u.entity_key, "reason": u.reason}
            for u in result.untimed
        ],
        "avoided_entities": result.avoided_entities,
        # Counted from the entities the prevented steps actually touched, not
        # from everything reachable. Reachability says what could have been
        # affected; crediting the intervention with all of it would report harm
        # that never happened as harm avoided.
        "avoided_users": users,
        "gap_seconds": result.gap_seconds,
        "basis": list(result.basis),
        "reach": list(result.reach),
        "refs": result.refs,
    }


def _resolvable(incident) -> set[str]:
    """Which of this incident's cited refs resolve to a stored record.

    Every ref any hypothesis names, checked against the store. This is what
    turns "the incident says the alternative was ruled out" into "something
    stored rules it out" — the difference the whole adjudication turns on.
    """
    store = entitystore()
    claimed = {
        ref
        for hypothesis in incident.hypotheses
        for ref in (*hypothesis.evidence, *hypothesis.contradicted_by)
    }
    return {ref for ref in claimed if store.event(ref) is not None}


@router.get("/incidents/{incident_id}/contest")
def incident_contest(incident_id: str) -> dict[str, object]:
    """The case for the other explanation, and what answers it (R73).

    The Blue Team rubric tells a player that one of the explanations is
    plausible and wrong and scores them on opening the evidence that rules it
    out. This holds the agent to the same standard on the same incidents.

    A refusal is a 422. "There is no rival here worth arguing" is a correct
    answer about the records — an incident with one hypothesis, or with two that
    are one claim written twice — and manufacturing a contest to avoid an empty
    panel is the rigour-shaped version of having none.
    """
    from pashupatastra.contest import ContestRefused, contest

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")
    try:
        result = contest(incident, _resolvable(incident))
    except ContestRefused as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _case(case) -> dict[str, object]:
        return {
            "ref": case.ref,
            "statement": case.statement,
            "confidence": case.confidence,
            "supported_by": list(case.supported_by),
            "uncited": list(case.uncited),
        }

    return {
        "incident_ref": result.incident_ref,
        "verdict": result.verdict.value,
        "leader": _case(result.leader),
        "rival": _case(result.rival),
        "argument": result.describe(),
        "ruled_out_by": list(result.ruled_out_by),
        "unresolved_rejection": list(result.unresolved_rejection),
        "shared": list(result.shared),
        "separators": list(result.separators),
        "unexplained_by_leader": list(result.unexplained_by_leader),
        "refs": result.refs,
    }


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


PREVIEW_CONSTRAINT = "preview"
"""Marks a verdict that was computed to be shown, not to authorise anything.

A preview is the same arithmetic as an evaluation with the ledger left alone,
so the two verdicts are indistinguishable by their numbers. The mark is what
lets `/policy/approve` refuse one: approving a verdict nobody recorded would put
an approval in the trail with no evaluation before it.
"""


def _evaluate(request: EvaluateRequest) -> tuple[ActionSpec, Verdict]:
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
    return action, verdict


@router.post("/policy/preview", response_model=Verdict)
def preview_policy(request: EvaluateRequest) -> Verdict:
    """Dharma's verdict, for display. Writes nothing.

    Computing a verdict to *show* is not the act of authorising one. The incident
    page asks what an action would need and from whom; asking that through
    `/policy/evaluate` appended a record per page view, and 48% of the ledger
    became renders (R93). Rule 6 audits decisions, approvals and executions —
    not somebody reading a page.
    """
    _, verdict = _evaluate(request)
    verdict.constraints[PREVIEW_CONSTRAINT] = "not recorded; evaluate before authorising"
    return verdict


@router.post("/policy/evaluate", response_model=Verdict)
def evaluate_policy(request: EvaluateRequest) -> Verdict:
    """Dharma. The only way to obtain authorization to execute."""
    action, verdict = _evaluate(request)
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


@router.get("/policy/model")
def policy_model_route() -> dict[str, object]:
    """The policy this deployment enforces, generated from the engine.

    Serves the page that explains the risk tiers. That page must not restate
    them: a table written from memory is a second answer to "who may approve
    this", and on the day the two disagree the wrong one is the one on the
    marketing site.

    The gates are here for the same reason. "This deployment is in dry run and
    its environment is not on the live list" is a claim the front page makes,
    and it is worth exactly as much as the reader's ability to check it.
    """
    from pashupatastra.dharma import policy_model

    settings = get_settings()
    model = policy_model()
    model["gates"] = {
        "dry_run": settings.dry_run,
        "environment": str(settings.environment),
        "live_environments": [str(env) for env in settings.live_environments],
        # Both must open. `not dry_run` alone is not enough, which is the whole
        # point of there being two — see `Settings.live_execution_enabled`.
        "live_execution_enabled": settings.live_execution_enabled,
    }
    return model


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
    if PREVIEW_CONSTRAINT in verdict.constraints:
        raise HTTPException(
            status_code=409,
            detail="preview verdicts cannot be approved; obtain one from /policy/evaluate",
        )
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
    reached, edges = _cited_paths(entity_key, set(radius.affected), max_depth)
    return {
        "origin": radius.origin,
        "affected": radius.affected,
        "entity_count": radius.entity_count,
        "estimated_users": radius.estimated_users,
        # The same reach, expressed as a walk that can be checked.
        #
        # `affected` is the authoritative set and comes from the graph function
        # that risk scoring uses; these two are for drawing it. They are kept
        # separate rather than merged because the walk refuses to cross an edge
        # carrying no evidence, so it can legitimately reach *fewer* entities —
        # and that gap is a fact about how much of the reach is provable, which
        # is worth showing rather than papering over.
        "reached": reached,
        "edges": edges,
        "uncited": sorted(set(radius.affected) - {r["key"] for r in reached}),
    }


def _cited_paths(
    origin: str, affected: set[str], max_depth: int
) -> tuple[list[dict], list[dict]]:
    """Breadth-first from the origin, across edges that carry evidence.

    **An edge with no citation is not traversed.** R50's rule, applied to the
    walk rather than to the drawing: filtering at render time would leave the
    node reachable and the reason invisible, which is how a diagram ends up
    asserting a relationship nobody can check. Refusing the hop is the same rule
    enforced one layer earlier, where it cannot be forgotten.

    Depth is carried out so the view can be radial — a ring per hop — rather
    than a shape someone has to infer from the arrows.
    """
    snapshot = GRAPH.snapshot(limit=400)
    outgoing: dict[str, list[dict]] = {}
    for edge in snapshot.get("edges", []):
        if not edge.get("evidence"):
            continue
        outgoing.setdefault(edge["source"], []).append(edge)
        # Undirected for reach: a dependency is a path in both directions when
        # the question is "what does trouble here touch".
        outgoing.setdefault(edge["target"], []).append(edge)

    names = {node["key"]: node for node in snapshot.get("nodes", [])}
    reached: list[dict] = []
    drawn: list[dict] = []
    seen = {origin}
    frontier = [origin]

    for depth in range(1, max_depth + 1):
        following: list[str] = []
        for key in frontier:
            for edge in outgoing.get(key, []):
                other = edge["target"] if edge["source"] == key else edge["source"]
                if other in seen or other not in affected:
                    continue
                seen.add(other)
                following.append(other)
                node = names.get(other, {})
                reached.append(
                    {
                        "key": other,
                        "name": node.get("name") or other.split(":", 1)[-1],
                        "kind": node.get("kind") or other.split(":", 1)[0],
                        "severity": node.get("severity"),
                        "estimated_users": node.get("estimated_users") or 0,
                        "depth": depth,
                    }
                )
                drawn.append(
                    {
                        "source": key,
                        "target": other,
                        "kind": edge.get("kind"),
                        "evidence": edge.get("evidence") or [],
                        "depth": depth,
                    }
                )
        if not following:
            break
        frontier = following

    return reached, drawn


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
    from ..feeds.ingest import FEEDS

    known = sorted(FEEDS)
    sources = [source] if source else known
    if source and source not in known:
        raise HTTPException(
            status_code=404, detail=f"unknown source {source}; known: {', '.join(known)}"
        )

    from ..feeds.grouping import GROUPING_WINDOW, group

    store = entitystore()
    reader = getattr(store, "recent_events", None)
    entries = reader(sources=sources, limit=min(limit, 200)) if reader else []
    groups = group(entries)

    return {
        "sources": known,
        # Both counts, because they answer different questions: how many
        # indicators there are, and how many times they were reported. A page
        # that showed only the second was the bug.
        "count": len(groups),
        "reports": len(entries),
        "window_hours": int(GROUPING_WINDOW.total_seconds() // 3600),
        "groups": groups,
    }


@router.get("/search/index")
def search_index(advisories: int = 40) -> dict[str, object]:
    """Everything the command palette can jump to, in one compact list.

    Built here rather than assembled in the browser from four separate calls,
    because the palette's whole claim is that it is faster than the navigation
    it replaces. A palette that fires a request per keystroke is slower than
    clicking a link, and one that fires four on open is slower than the page it
    is opened from.

    Compact on purpose: a label, a hint and a href. The palette matches text and
    then navigates, so anything else on the record is weight sent to every
    visitor on every page for no reason. Advisories are capped because the feeds
    hold thousands and the palette is for reaching a thing you can name.
    """
    items: list[dict[str, str]] = []

    # `STORE.all()`, not `STORE.incidents` — the in-memory dict is empty on a
    # durable deployment, where incidents live in DynamoDB. Reading the dict
    # gave the palette an index with zero incidents on the deployed site while
    # working perfectly on a laptop.
    for incident in STORE.all():
        statement = incident.hypotheses[0].statement if incident.hypotheses else ""
        items.append(
            {
                "kind": "incident",
                "label": incident.id,
                "hint": statement[:120],
                "href": f"/incidents/{incident.id}",
            }
        )

    snapshot = GRAPH.snapshot(limit=400)
    for node in snapshot.get("nodes", []):
        key = node.get("key") or ""
        if not key:
            continue
        items.append(
            {
                "kind": "entity",
                "label": node.get("name") or key,
                "hint": key,
                "href": f"/entity/{key}",
            }
        )

    for action in all_actions():
        items.append(
            {
                "kind": "action",
                "label": action.id,
                "hint": action.description[:120],
                "href": "/actions",
            }
        )

    from ..feeds.grouping import group

    store = entitystore()
    reader = getattr(store, "recent_events", None)
    from ..feeds.ingest import FEEDS

    entries = reader(sources=sorted(FEEDS), limit=advisories * 2) if reader else []
    for entry in group(entries)[:advisories]:
        items.append(
            {
                "kind": "advisory",
                "label": str(entry.get("title") or entry.get("entity_key") or ""),
                "hint": str(entry.get("entity_key") or ""),
                "href": f"/observatory?source={entry.get('source')}",
            }
        )

    return {"count": len(items), "items": items}


STALE_AFTER_HOURS = 3
"""A feed polled hourly that has not answered in three hours has missed three
runs, which is a fault rather than a slow afternoon. Named because the page
prints the number and a literal in two places is one chance to disagree."""


@router.get("/intel/status")
def intel_status() -> dict[str, object]:
    """How current each feed is — three different facts, kept apart.

    **Synced** is when the feed last answered. **Moved** is when it last had
    something new. **Stale** is synced being too long ago.

    Conflating the first two is the bug this route existed with: the cursor only
    advances when something is stored, so a healthy feed with nothing new to
    report looked exactly like one that had stopped answering. "Quiet" and
    "broken" are the whole question a reader has about a live feed, and the page
    could not tell them apart.

    Timestamps go out as ISO strings and the age is computed from them. A page
    that derived "synced just now" from its own load time would say the feed was
    current at the moment it was actually broken.
    """
    from ..backend import durable
    from ..feeds.ingest import FEEDS

    backend = durable()
    now = datetime.now().astimezone()
    feeds: dict[str, dict[str, object]] = {}
    freshest: datetime | None = None

    for name in sorted(FEEDS):
        read_cursor = getattr(backend, "get_feed_cursor", None)
        read_sync = getattr(backend, "get_feed_sync", None)
        sync = read_sync(name) if read_sync else None

        synced_at = (sync or {}).get("at")
        age_seconds: float | None = None
        if synced_at:
            try:
                stamp = datetime.fromisoformat(str(synced_at))
                age_seconds = (now - stamp).total_seconds()
                if freshest is None or stamp > freshest:
                    freshest = stamp
            except ValueError:
                age_seconds = None

        feeds[name] = {
            "cursor": read_cursor(name) if read_cursor else None,
            "synced_at": synced_at,
            "age_seconds": age_seconds,
            "ok": bool((sync or {}).get("ok", False)) if sync else None,
            "error": (sync or {}).get("error") or None,
            # Never synced is not stale — it is a deployment that has not polled
            # yet, and calling that a fault would cry wolf on every fresh start.
            "stale": (
                age_seconds is not None and age_seconds > STALE_AFTER_HOURS * 3600
            ),
        }

    return {
        "feeds": feeds,
        "synced_at": freshest.isoformat() if freshest else None,
        "stale_after_hours": STALE_AFTER_HOURS,
        "durable": backend is not None,
    }


@router.get("/incidents/{incident_id}/graph")
def incident_graph(incident_id: str) -> dict[str, object]:
    """The sub-graph this incident's own evidence names.

    Filtered here rather than in the browser. The alternative is shipping the
    whole estate to draw three nodes, which works at eleven entities and stops
    working at the first real deployment — and the incident page is the one
    screen that has to load while somebody is waiting.

    An edge is included only when **both** ends are in the incident. A path from
    one of these entities out to something the incident never mentions is real,
    and drawing it here would say the incident reached further than its evidence
    establishes — the same rule R50 applied to inventing edges, applied to
    borrowing them.
    """
    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")

    keys = {entity.key() for entity in incident.affected_entities}
    keys |= {link.entity.key() for link in incident.causal_chain}

    snapshot = GRAPH.snapshot()
    _overlay_open_incidents(snapshot)

    nodes = [node for node in snapshot["nodes"] if node["key"] in keys]
    edges = [
        edge
        for edge in snapshot["edges"]
        if edge["source"] in keys and edge["target"] in keys
    ]

    # What these entities can reach *beyond* the incident, counted but not
    # drawn. Zero would be a claim; the number is what makes the difference
    # between "contained" and "not looked at yet" visible.
    reach: set[str] = set()
    for key in keys:
        reach.update(GRAPH.blast_radius(key).affected)

    return {
        "incident_id": incident.id,
        "nodes": nodes,
        "edges": edges,
        "beyond": sorted(reach - keys),
    }


# --- blue team mode ----------------------------------------------------------


@router.get("/game/scenarios")
def game_scenarios() -> list[dict[str, object]]:
    """What can be played, without saying what any of them are.

    Severity and the opening alert only. A list that summarised each incident
    would answer the question the exercise asks before it is opened.
    """
    from .. import game

    graph = entitystore()
    out = []
    for incident in STORE.all():
        alert = game.opening_alert(incident, graph)
        out.append(
            {
                "incident_id": incident.id,
                "severity": str(incident.severity),
                "opened_at": incident.opened_at.isoformat(),
                "opening": (alert or {}).get("summary", ""),
                "steps": len(incident.causal_chain),
            }
        )
    return out


@router.get("/game/{incident_id}/briefing")
def game_briefing(incident_id: str) -> dict[str, object]:
    from .. import game

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")
    settings = get_settings()
    return game.briefing(incident, entitystore(), domain=settings.action_domain)


class InvestigateRequest(BaseModel):
    entity_key: str


@router.post("/game/{incident_id}/investigate")
def game_investigate(incident_id: str, request: InvestigateRequest) -> dict[str, object]:
    from .. import game

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")
    result = game.investigate(incident, entitystore(), request.entity_key)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=str(result["reason"]))
    return result


class AnswerRequest(BaseModel):
    diagnosis_id: str
    action_id: str
    investigated: list[str] = []
    player_id: str | None = None
    """An opaque token the browser generated and keeps locally. Optional: the
    exercise works without one, and someone who declines to be remembered
    across visits should still be able to play."""


@router.post("/game/{incident_id}/answer")
def game_answer(incident_id: str, request: AnswerRequest) -> dict[str, object]:
    """Mark the attempt and reveal the chain.

    The only route that returns the answer, and it returns it *after* an
    attempt — which is what keeps the briefing honest.
    """
    from .. import game

    incident = STORE.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"unknown incident {incident_id}")

    result = game.score(
        incident,
        entitystore(),
        diagnosis_id=request.diagnosis_id,
        action_id=request.action_id,
        investigated=request.investigated,
    )
    AUDIT.append(
        AuditRecord(
            at=datetime.now().astimezone(),
            kind=AuditKind.OBSERVATION,
            actor="human:trainee",
            incident_ref=incident.id,
            # The token is deliberately absent from the audit line. The trail is
            # public, and a pseudonymous id printed beside a timestamp on a
            # public page is a thing that can be correlated.
            summary=(
                f"blue team attempt: {result['total']}/100 ({result['grade']})"
            ),
        )
    )

    # Recorded from the marked total, never from anything the client sent. A
    # score a player can choose is not a score.
    result["progress"] = PROGRESS.add(
        request.player_id or "", incident.id, int(result["total"])
    )
    return result


@router.get("/game/progress/{player_id}")
def game_progress(player_id: str) -> dict[str, object]:
    """One player's own record, by the token their browser holds.

    There is no route that lists players, and that absence is the feature: an
    enumerable set of scores is a leaderboard, and a leaderboard is what this
    was asked not to be. A token can read only itself, and nothing joins a token
    to a person.
    """
    if not progress_module.valid(player_id):
        raise HTTPException(status_code=400, detail="not a valid player token")
    return {
        "player": PROGRESS.get(player_id),
        "durable": PROGRESS.durable,
    }


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
            + (" · WITHHELD" if result.withheld else "")
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
            # The readings that were open and what closed them, stored with the
            # answer rather than regenerated later. Asking the model the same
            # question next month produces a different trace under a different
            # prompt; this one is the trace that produced *this* answer.
            "considered": result.considered,
            "dropped_considered": result.dropped_considered,
            "proposed_action_id": result.proposed_action_id,
            "answer": result.answer,
            # What the model said when its text was withheld from the visitor.
            # In the ledger and nowhere else: the visitor saw the sentence in
            # `answer`, and this is what a reviewer reads to decide whether the
            # model was inventing a record or claiming to have acted.
            "withheld": result.withheld,
            "withheld_answer": result.withheld_text,
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
