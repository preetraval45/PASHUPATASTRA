"""Pashupatastra core domain model.

Contains no cloud-specific types by design (the Platform ADR) — this package must run on
a laptop, and it is the future open-source `pashupatastra-core`.
"""

from .agents import AgentSpec, Budget, BudgetLedger, EscalationReason, load_agent_spec
from .dharma import (
    ActionSpec,
    Environment,
    PolicyViolation,
    RiskContext,
    Tier,
    Verdict,
    evaluate,
    require_verdict,
    score,
)
from .events import (
    SCHEMA_VERSION,
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Provenance,
    QuarantinedEvent,
    Severity,
)
from .incidents import (
    CausalLink,
    Hypothesis,
    Impact,
    Incident,
    IncidentSeverity,
    IncidentState,
    PlanStep,
    Verification,
    VerificationCheck,
    incident_id,
)
from .topology import BlastRadius, Edge, Node, TopologyGraph

__version__ = "0.1.0"

__all__ = [
    "SCHEMA_VERSION",
    "__version__",
    "ActionSpec",
    "AgentSpec",
    "BlastRadius",
    "Budget",
    "BudgetLedger",
    "CausalLink",
    "Edge",
    "EntityKind",
    "EntityRef",
    "Environment",
    "EscalationReason",
    "Event",
    "EventClass",
    "Hypothesis",
    "Impact",
    "Incident",
    "IncidentSeverity",
    "IncidentState",
    "Node",
    "PlanStep",
    "PolicyViolation",
    "Provenance",
    "QuarantinedEvent",
    "RiskContext",
    "Severity",
    "Tier",
    "TopologyGraph",
    "Verdict",
    "Verification",
    "VerificationCheck",
    "evaluate",
    "incident_id",
    "load_agent_spec",
    "require_verdict",
    "score",
]
