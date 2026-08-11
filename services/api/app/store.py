"""Incident store.

Backed by Postgres when reachable, with an in-memory mirror so local
development and CI without a database still work. Seeded with the demo
incident so the dashboard has something to render before connectors exist.
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
    """Incident store.

    Reads and writes Postgres when it is reachable, and keeps an in-memory
    mirror so local development and CI without a database still work. Writes go
    to both, so a restart against a live database loses nothing.
    """

    def __init__(self) -> None:
        self.incidents: dict[str, Incident] = {}
        self.verdicts: dict[str, Verdict] = {}
        self._backend: object | None = None
        self._resolved = False

    def _durable(self):
        if not self._resolved:
            from .db import PostgresStore, is_available

            self._backend = PostgresStore() if is_available() else None
            self._resolved = True
        return self._backend

    @property
    def durable(self) -> bool:
        return self._durable() is not None

    def save(self, incident: Incident) -> Incident:
        self.incidents[incident.id] = incident
        backend = self._durable()
        if backend is not None:
            backend.save_incident(incident)
        return incident

    def get(self, incident_id: str) -> Incident | None:
        backend = self._durable()
        if backend is not None:
            stored = backend.get_incident(incident_id)
            if stored is not None:
                return stored
        return self.incidents.get(incident_id)

    def all(self) -> list[Incident]:
        backend = self._durable()
        if backend is not None:
            stored = backend.list_incidents()
            if stored:
                return stored
        return list(self.incidents.values())

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
        return self.save(incident)


STORE = Store()
STORE.seed_demo()
