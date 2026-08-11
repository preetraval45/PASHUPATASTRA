"""Normalized event model (v0).

Every connector emits into this shape; every engine reads only this shape.
See docs/specs/Event Model.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

import ulid
from pydantic import BaseModel, Field

SCHEMA_VERSION = "v0"


class EventClass(StrEnum):
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    STATE_CHANGE = "state_change"
    DEPLOYMENT = "deployment"
    SECURITY = "security"
    ALERT = "alert"
    HUMAN_ACTION = "human_action"


class EntityKind(StrEnum):
    SERVICE = "service"
    HOST = "host"
    CONTAINER = "container"
    POD = "pod"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    LOADBALANCER = "loadbalancer"
    ENDPOINT = "endpoint"
    USER = "user"
    DEPLOYMENT = "deployment"
    CLOUD_RESOURCE = "cloud_resource"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EntityRef(BaseModel):
    """Reference to a topology node. Events and the graph share one namespace."""

    kind: EntityKind
    id: str
    name: str
    cluster: str | None = None
    namespace: str | None = None

    def key(self) -> str:
        return f"{self.kind}:{self.id}"


class Provenance(BaseModel):
    """How a human re-retrieves the original record. Mandatory on every event."""

    source_system: str
    query: str | None = None
    url: str | None = None
    offset: str | None = None


# --- class-specific payloads -------------------------------------------------


class MetricPayload(BaseModel):
    kind: Literal["metric"] = "metric"
    name: str
    value: float
    unit: str | None = None
    window_seconds: int | None = None
    baseline: float | None = None
    deviation_sigma: float | None = None


class LogPayload(BaseModel):
    kind: Literal["log"] = "log"
    message: str
    level: str
    fields: dict[str, str] = Field(default_factory=dict)
    trace_id: str | None = None


class TracePayload(BaseModel):
    kind: Literal["trace"] = "trace"
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    duration_ms: float
    status: str
    service_hops: list[str] = Field(default_factory=list)


class StateChangePayload(BaseModel):
    kind: Literal["state_change"] = "state_change"
    resource: str
    previous_state: str | None
    new_state: str
    actor: str | None = None


class DeploymentPayload(BaseModel):
    """First-class because change correlation is the highest-yield causal signal."""

    kind: Literal["deployment"] = "deployment"
    service: str
    version: str
    previous_version: str | None = None
    actor: str | None = None
    commit: str | None = None
    strategy: str | None = None


class SecurityPayload(BaseModel):
    kind: Literal["security"] = "security"
    detection_type: str
    principal: str | None = None
    source_address: str | None = None
    asset: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class AlertPayload(BaseModel):
    kind: Literal["alert"] = "alert"
    rule_id: str
    condition: str
    upstream_severity: str | None = None
    upstream_state: str | None = None


class HumanActionPayload(BaseModel):
    kind: Literal["human_action"] = "human_action"
    operator: str
    action: str
    incident_ref: str | None = None
    rationale: str | None = None


Payload = Annotated[
    Union[
        MetricPayload,
        LogPayload,
        TracePayload,
        StateChangePayload,
        DeploymentPayload,
        SecurityPayload,
        AlertPayload,
        HumanActionPayload,
    ],
    Field(discriminator="kind"),
]


def new_event_id() -> str:
    """ULID: sortable by observation time."""
    return str(ulid.new())


class Event(BaseModel):
    """The one shape all telemetry is normalized into."""

    schema_version: str = SCHEMA_VERSION
    id: str = Field(default_factory=new_event_id)
    event_class: EventClass
    source: str
    source_version: str | None = None
    occurred_at: datetime
    observed_at: datetime
    entity_ref: EntityRef
    severity: Severity | None = None
    payload: Payload
    provenance: Provenance
    labels: dict[str, str] = Field(default_factory=dict)

    @property
    def ingestion_lag_seconds(self) -> float:
        """Gap between source time and observation. Matters for causal ordering."""
        return (self.observed_at - self.occurred_at).total_seconds()


class QuarantinedEvent(BaseModel):
    """An event whose entity could not be resolved into the topology graph.

    Unresolvable entities signal stale topology, so they are held and made
    visible rather than silently dropped.
    """

    raw: dict[str, object]
    source: str
    reason: str
    observed_at: datetime
