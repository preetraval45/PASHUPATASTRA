"""Pashupatastra core domain model.

Contains no cloud-specific types by design (the Platform ADR) — this package must run on
a laptop, and it is the future open-source `pashupatastra-core`.
"""

from .baselines import Band, Baseline, BaselineStore, Reading
from .correlation import Cluster, CorrelationResult, Correlator, MergeQuality, measure_merges
from .detection import Detector, Finding, UpstreamRules
from .evaluation import Score, Series, compare, evaluate as evaluate_detector, winner
from .strategies import STRATEGIES, DetectionStrategy, Ewma, RobustZScore, SeasonalNaive
from .agents import AgentSpec, Budget, BudgetLedger, EscalationReason, load_agent_spec
from .dharma import (
    ActionSpec,
    Environment,
    PolicyViolation,
    RiskContext,
    RiskFactor,
    Tier,
    TierStep,
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
    AttackTechnique,
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
from .relations import Overlap, Relation, relate
from .topology import BlastRadius, Edge, Node, TopologyGraph

__version__ = "0.1.0"

__all__ = [
    "SCHEMA_VERSION",
    "__version__",
    "ActionSpec",
    "Band",
    "Baseline",
    "BaselineStore",
    "AgentSpec",
    "BlastRadius",
    "Budget",
    "BudgetLedger",
    "AttackTechnique",
    "CausalLink",
    "Cluster",
    "CorrelationResult",
    "Correlator",
    "STRATEGIES",
    "DetectionStrategy",
    "Detector",
    "Ewma",
    "Edge",
    "EntityKind",
    "EntityRef",
    "Environment",
    "EscalationReason",
    "Event",
    "Finding",
    "EventClass",
    "Hypothesis",
    "Impact",
    "MergeQuality",
    "Incident",
    "IncidentSeverity",
    "IncidentState",
    "Node",
    "PlanStep",
    "PolicyViolation",
    "Provenance",
    "Reading",
    "RobustZScore",
    "Score",
    "SeasonalNaive",
    "Series",
    "QuarantinedEvent",
    "Overlap",
    "Relation",
    "RiskContext",
    "RiskFactor",
    "Severity",
    "Tier",
    "TierStep",
    "relate",
    "TopologyGraph",
    "UpstreamRules",
    "Verdict",
    "Verification",
    "VerificationCheck",
    "compare",
    "evaluate",
    "evaluate_detector",
    "winner",
    "incident_id",
    "measure_merges",
    "load_agent_spec",
    "require_verdict",
    "score",
]
