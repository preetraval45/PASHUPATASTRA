"""In-memory store.

Placeholder until Phase 0.5 lands the Postgres schema. Kept behind one object so
the swap touches a single seam. Seeded with the demo incident so the dashboard
and the killer demo have something to render before connectors exist.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pashupatastra import (
    CausalLink,
    EntityKind,
    EntityRef,
    Hypothesis,
    Impact,
    Incident,
    IncidentSeverity,
    IncidentState,
    PlanStep,
    Verdict,
    incident_id,
)
from pashupatastra.registry import get as get_action


def _ref(kind: EntityKind, name: str) -> EntityRef:
    return EntityRef(kind=kind, id=name, name=name)


class Store:
    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self.verdicts: dict[str, Verdict] = {}

    def seed_demo(self) -> Incident:
        """The Phase-6 demo incident: DB connection exhaustion from a bad deploy."""
        opened = datetime.now().astimezone() - timedelta(minutes=8)
        incident = Incident(
            id=incident_id(2026, 810),
            severity=IncidentSeverity.CRITICAL,
            opened_at=opened,
            affected_entities=[
                _ref(EntityKind.SERVICE, "checkout-api"),
                _ref(EntityKind.DATABASE, "postgres-primary"),
            ],
            impact=Impact(
                estimated_users_affected=1240,
                affected_services=["checkout-api", "frontend"],
                blast_radius_entities=3,
            ),
            hypotheses=[
                Hypothesis(
                    statement=(
                        "Deployment v4.21 introduced an N+1 query in the checkout path, "
                        "saturating the PostgreSQL connection pool."
                    ),
                    confidence=0.91,
                    evidence=["evt-deploy-421", "evt-pg-connections", "evt-api-5xx"],
                    contradicted_by=[],
                    mechanism=[
                        "deployment v4.21",
                        "query volume increase",
                        "connection pool saturation",
                        "request queue growth",
                        "request timeout",
                        "5xx rate increase",
                        "transaction failure",
                    ],
                ),
                Hypothesis(
                    statement="Organic traffic growth exceeded provisioned pool size.",
                    confidence=0.06,
                    evidence=["evt-request-rate"],
                    contradicted_by=["evt-request-rate-flat"],
                ),
            ],
            causal_chain=[
                CausalLink(
                    entity=_ref(EntityKind.DEPLOYMENT, "checkout-api@v4.21"),
                    transition="deployed v4.20 → v4.21",
                    evidence=["evt-deploy-421"],
                ),
                CausalLink(
                    entity=_ref(EntityKind.DATABASE, "postgres-primary"),
                    transition="connections 41% → 98%",
                    evidence=["evt-pg-connections"],
                ),
                CausalLink(
                    entity=_ref(EntityKind.SERVICE, "checkout-api"),
                    transition="5xx rate 0.2% → 14%",
                    evidence=["evt-api-5xx"],
                ),
            ],
            plan=[
                PlanStep(
                    order=1,
                    action_id="disable_deployment",
                    expected_post_state=get_action("disable_deployment").expected_post_state,
                    rollback_action_id="redeploy_version",
                ),
                PlanStep(
                    order=2,
                    action_id="rollback_deployment",
                    expected_post_state=get_action("rollback_deployment").expected_post_state,
                    rollback_action_id="redeploy_version",
                ),
            ],
        )
        incident.transition_to(
            IncidentState.CORRELATED,
            "agent:incident",
            "5 alerts across 3 topology-adjacent entities within 210s",
        )
        incident.transition_to(
            IncidentState.DIAGNOSED,
            "agent:incident",
            "deployment v4.21 correlated with connection saturation onset",
        )
        incident.transition_to(
            IncidentState.AWAITING_APPROVAL,
            "dharma",
            "rollback_deployment in prod scores 60 → approval tier",
        )
        self.incidents[incident.id] = incident
        return incident


STORE = Store()
STORE.seed_demo()
