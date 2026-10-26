"""Kaal's incident generator: labelled synthetic incidents for training Sati-RCA (RP-17).

The fault model is [adr/KaalGenerator](../../../../docs/adr/KaalGenerator.md), proposed and awaiting the
owner's decision. In outline:

* **Topology:** a random layered service graph. Calls go down only (edge → API
  → backend → datastores), so the graph has no cycles.
* **Fault:** chosen from a catalogue mapped to PIB's eight categories. It moves
  the origin's own metrics, then propagates **up** to every caller, with a
  delay per hop, attenuation and noise. Callers show latency and errors, never
  the origin's metrics, so the loudest service is often not the cause.
* **Decoys and negatives:** an unrelated deploy or a noisy neighbour in about
  40% of incidents, and no fault at all in about 20%.

Deterministic: a seed and an index fully determine an incident. Pure Python, no
cloud; it runs wherever `packages/core` runs.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from pashupatastra.events import (
    DeploymentPayload,
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    LogPayload,
    MetricPayload,
    Provenance,
    Severity,
)

VERSION = "kaal-generator-v0"
DECOY_SHARE = 0.4
NEGATIVE_SHARE = 0.2
FADE_SIGMA = 1.5
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)

LAYERS = (
    ("edge", EntityKind.SERVICE, (1, 2)),
    ("api", EntityKind.SERVICE, (2, 4)),
    ("backend", EntityKind.SERVICE, (2, 5)),
    ("store", None, (1, 3)),
)
STORE_KINDS = (EntityKind.DATABASE, EntityKind.CACHE, EntityKind.QUEUE)


@dataclass(frozen=True)
class Fault:
    name: str
    category: str
    origin: tuple[str, ...]
    """Layers (or, for stores, entity kinds) the fault may start in."""
    metrics: tuple[tuple[str, int], ...]
    """Metrics the origin shows, with direction (+1 up, -1 down)."""
    action: str | None
    outcome: str


FAULTS = (
    Fault("connection_pool_saturation", "database", ("database",),
          (("db_connections", 1), ("latency_p99_ms", 1)), "scale_service", "remediate"),
    Fault("eviction_storm", "cache", ("cache",), (("cache_hit_rate", -1), ("latency_p99_ms", 1)),
          "warm_cache", "remediate"),
    Fault("memory_leak", "compute", ("backend",), (("memory_bytes", 1), ("restarts", 1)), "restart_service", "remediate"),
    Fault("cpu_saturation", "compute", ("api", "backend"), (("cpu_ratio", 1), ("latency_p99_ms", 1)),
          "scale_service", "remediate"),
    Fault("bad_release", "deployment", ("api", "backend"), (("error_rate", 1), ("latency_p99_ms", 1)),
          "rollback_deployment", "remediate"),
    Fault("consumer_lag", "queue", ("queue",), (("queue_depth", 1), ("message_age_s", 1)), "scale_service", "remediate"),
    Fault("third_party_outage", "dependency", ("edge", "api"), (("error_rate", 1),), None, "escalate"),
    Fault("packet_loss", "network", ("edge", "api"), (("latency_p99_ms", 1), ("timeouts", 1)), None, "escalate"),
    Fault("credential_stuffing", "security", ("edge",), (("auth_failures", 1), ("login_rate", 1)), None, "escalate"),
)

BASELINES = {
    "db_connections": 40.0, "latency_p99_ms": 180.0, "cache_hit_rate": 0.93, "memory_bytes": 6.0e8, "restarts": 0.0,
    "cpu_ratio": 0.35, "error_rate": 0.004, "queue_depth": 120.0, "message_age_s": 2.0, "timeouts": 1.0,
    "auth_failures": 3.0, "login_rate": 40.0,
}


@dataclass
class Service:
    name: str
    layer: str
    kind: EntityKind


@dataclass
class Incident:
    id: str
    version: str
    services: list[Service]
    calls: list[tuple[str, str]]
    events: list[Event]
    label: dict[str, object]
    meta: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id, "version": self.version,
            "topology": {"services": [{**asdict(s), "kind": s.kind.value} for s in self.services],
                         "calls": [list(c) for c in self.calls]},
            "events": [e.model_dump(mode="json") for e in self.events],
            "label": self.label,
        }


def topology(rng: random.Random) -> tuple[list[Service], list[tuple[str, str]]]:
    services: list[Service] = []
    by_layer: dict[str, list[Service]] = {}
    for layer, kind, (lo, hi) in LAYERS:
        for _ in range(rng.randint(lo, hi)):
            k = kind or rng.choice(STORE_KINDS)
            s = Service(f"svc-{len(services):02d}", layer, k)
            services.append(s)
            by_layer.setdefault(layer, []).append(s)
    calls = []
    order = [layer for layer, _, _ in LAYERS]
    for upper, lower in pairwise(order):
        for caller in by_layer[upper]:
            for callee in rng.sample(by_layer[lower], rng.randint(1, min(3, len(by_layer[lower])))):
                calls.append((caller.name, callee.name))
        # Every service below is called by something, or it could never matter.
        called = {b for _, b in calls}
        for orphan in (s for s in by_layer[lower] if s.name not in called):
            calls.append((rng.choice(by_layer[upper]).name, orphan.name))
    return services, sorted(set(calls))


def callers_by_distance(origin: str, calls: list[tuple[str, str]]) -> list[tuple[str, int]]:
    """Every service that reaches `origin` through calls, with its hop count, nearest first."""
    up: dict[str, list[str]] = {}
    for a, b in calls:
        up.setdefault(b, []).append(a)
    seen, frontier, out = {origin}, [origin], []
    hops = 0
    while frontier:
        hops += 1
        nxt = []
        for s in frontier:
            for caller in sorted(up.get(s, [])):
                if caller not in seen:
                    seen.add(caller)
                    nxt.append(caller)
                    out.append((caller, hops))
        frontier = nxt
    return out


def _eligible(fault: Fault, services: list[Service]) -> list[Service]:
    return [s for s in services if s.layer in fault.origin or s.kind.value in fault.origin]


def _metric(service: Service, name: str, value: float, baseline: float, sigma: float, at: datetime) -> Event:
    return Event(
        event_class=EventClass.METRIC, source="kaal", occurred_at=at, observed_at=at + timedelta(seconds=15),
        entity_ref=EntityRef(kind=service.kind, id=service.name, name=service.name),
        severity=Severity.CRITICAL if abs(sigma) >= 4 else Severity.WARNING,
        payload=MetricPayload(name=name, value=round(value, 6), baseline=baseline, deviation_sigma=round(sigma, 2)),
        provenance=Provenance(source_system="kaal", query=VERSION),
    )


def _deploy(service: Service, version: str, at: datetime) -> Event:
    return Event(
        event_class=EventClass.DEPLOYMENT, source="kaal", occurred_at=at, observed_at=at + timedelta(seconds=5),
        entity_ref=EntityRef(kind=service.kind, id=service.name, name=service.name),
        payload=DeploymentPayload(service=service.name, version=version, previous_version="v1.0.0", actor="ci"),
        provenance=Provenance(source_system="kaal", query=VERSION),
    )


def _log(service: Service, message: str, at: datetime) -> Event:
    return Event(
        event_class=EventClass.LOG, source="kaal", occurred_at=at, observed_at=at + timedelta(seconds=2),
        entity_ref=EntityRef(kind=service.kind, id=service.name, name=service.name), severity=Severity.WARNING,
        payload=LogPayload(message=message, level="error"), provenance=Provenance(source_system="kaal", query=VERSION),
    )


def _shift(name: str, direction: int, sigma: float) -> float:
    base = BASELINES[name]
    spread = max(abs(base) * 0.08, 0.01 if base < 1 else 1.0)
    return max(0.0, base + direction * sigma * spread)


def incident(seed: int, index: int) -> Incident:
    """One labelled incident. The same (seed, index) always gives the same incident."""
    rng = random.Random(f"{seed}:{index}")
    services, calls = topology(rng)
    by_name = {s.name: s for s in services}
    start = EPOCH + timedelta(minutes=rng.randint(0, 60 * 24 * 300))
    events: list[Event] = []
    decoys: list[dict[str, str]] = []

    # Background noise: small deviations on a few services, nowhere near a fault.
    for s in rng.sample(services, rng.randint(1, max(1, len(services) // 3))):
        sigma = rng.uniform(0.5, 1.4) * rng.choice((-1, 1))
        events.append(_metric(s, "latency_p99_ms", _shift("latency_p99_ms", 1, sigma), BASELINES["latency_p99_ms"],
                              sigma, start + timedelta(minutes=rng.randint(0, 20))))

    negative = rng.random() < NEGATIVE_SHARE
    fault = None if negative else rng.choice([f for f in FAULTS if _eligible(f, services)])
    origin = rng.choice(_eligible(fault, services)) if fault else None
    affected: list[str] = []
    onset = start + timedelta(minutes=rng.randint(5, 15))

    if fault and origin:
        if fault.name == "bad_release":
            events.append(_deploy(origin, f"v1.{rng.randint(1, 40)}.0", onset - timedelta(minutes=rng.randint(1, 4))))
        if fault.name == "third_party_outage":
            events.append(_log(origin, "upstream payments-provider returned 503", onset))
        strength = rng.uniform(4.0, 9.0)
        for name, direction in fault.metrics:
            sigma = direction * strength * rng.uniform(0.8, 1.1)
            events.append(_metric(origin, name, _shift(name, direction, abs(sigma)), BASELINES[name], sigma,
                                  onset + timedelta(seconds=rng.randint(0, 50))))
        affected.append(origin.name)
        # Up the call graph: callers see latency and errors, delayed and attenuated.
        for caller, hops in callers_by_distance(origin.name, calls):
            sigma = strength * (rng.uniform(0.6, 0.9) ** hops) * rng.uniform(0.8, 1.6)
            if sigma < FADE_SIGMA:
                continue
            at = onset + timedelta(minutes=sum(rng.randint(1, 3) for _ in range(hops)))
            svc = by_name[caller]
            events.append(_metric(svc, "latency_p99_ms", _shift("latency_p99_ms", 1, sigma), BASELINES["latency_p99_ms"],
                                  sigma, at))
            if rng.random() < 0.6:
                err = sigma * rng.uniform(0.5, 1.0)
                events.append(_metric(svc, "error_rate", _shift("error_rate", 1, err), BASELINES["error_rate"], err,
                                      at + timedelta(seconds=30)))
            affected.append(caller)

    if rng.random() < DECOY_SHARE:
        # Prefer a service the fault did not touch; never the root.
        others = [s for s in services if s.name not in affected] or [s for s in services if s is not origin]
        decoy = rng.choice(others)
        at = start + timedelta(minutes=rng.randint(0, 25))
        if rng.random() < 0.5 and decoy.kind == EntityKind.SERVICE:
            events.append(_deploy(decoy, f"v2.{rng.randint(1, 40)}.0", at))
            decoys.append({"service": decoy.name, "kind": "unrelated_deploy"})
        else:
            sigma = rng.uniform(3.0, 6.0)
            events.append(_metric(decoy, "cpu_ratio", _shift("cpu_ratio", 1, sigma), BASELINES["cpu_ratio"], sigma, at))
            decoys.append({"service": decoy.name, "kind": "noisy_neighbour"})

    events.sort(key=lambda e: e.occurred_at)
    # Event ids default to ULIDs from the clock; here they come from the incident,
    # so the same seed gives byte-identical output.
    incident_id = f"kaal-{seed}-{index:06d}"
    events = [e.model_copy(update={"id": f"{incident_id}-e{k:03d}"}) for k, e in enumerate(events)]
    label: dict[str, object] = {
        "root_service": origin.name if origin else None,
        "fault_type": fault.name if fault else None,
        "category": fault.category if fault else None,
        "action": fault.action if fault else None,
        "outcome": fault.outcome if fault else "nothing",
        "affected": affected,
        "decoys": decoys,
    }
    return Incident(incident_id, VERSION, services, calls, events, label, {"seed": seed, "index": index})
