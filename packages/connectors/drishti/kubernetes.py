"""Kubernetes connector.

The richest topology source, because ownership is **structural** rather than
inferred: a pod's ownerReferences state which ReplicaSet owns it, and a Service's
selector states which pods it fronts. Those are declarations by the platform
itself, not guesses from correlated behaviour — which is why this connector is
allowed to create edges where the Prometheus one is not.

Reads via `kubectl` against the active kubeconfig context. On EKS the same calls
work unchanged; only authentication differs, and that is the connector's
read-only IAM role rather than anything in this file (Platform ADR).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone

from pashupatastra import (
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Provenance,
    Severity,
)
from pashupatastra.events import DeploymentPayload, MetricPayload, StateChangePayload
from pashupatastra.topology import Edge

from .base import Connector, Harvest, Window

_PHASE_SEVERITY = {
    "Running": Severity.INFO,
    "Succeeded": Severity.INFO,
    "Pending": Severity.WARNING,
    "Unknown": Severity.WARNING,
    "Failed": Severity.CRITICAL,
}

# Namespaces whose churn is the platform's own, not the customer's. Included by
# default anyway — a failing CoreDNS or kube-proxy is very much an incident — but
# labelled so blast radius can distinguish infrastructure from workload.
_SYSTEM_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "local-path-storage"}


class KubernetesConnector(Connector):
    name = "kubernetes"

    def __init__(
        self,
        context: str | None = None,
        namespaces: list[str] | None = None,
        binary: str = "kubectl",
        timeout: float = 20.0,
    ) -> None:
        self.context = context
        self.namespaces = namespaces
        self.binary = binary
        self.timeout = timeout

    # --- cli ----------------------------------------------------------------

    def _run(self, *args: str) -> str:
        executable = shutil.which(self.binary) or self.binary
        command = [executable]
        if self.context:
            command += ["--context", self.context]
        command += list(args)
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=self.timeout, check=False
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout).strip()[:300])
        return completed.stdout

    def _list(self, resource: str) -> list[dict]:
        scope = ["--all-namespaces"] if not self.namespaces else []
        items: list[dict] = []
        if self.namespaces:
            for namespace in self.namespaces:
                raw = self._run("get", resource, "-n", namespace, "-o", "json")
                items += json.loads(raw).get("items", [])
        else:
            raw = self._run("get", resource, *scope, "-o", "json")
            items = json.loads(raw).get("items", [])
        return items

    # --- normalization ------------------------------------------------------

    @staticmethod
    def _ref(kind: EntityKind, name: str, namespace: str | None) -> EntityRef:
        return EntityRef(
            kind=kind,
            id=f"{namespace}/{name}" if namespace else name,
            name=name,
            namespace=namespace,
        )

    def poll(self, window: Window) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        for resource, handler in (
            ("pods", self._pods),
            ("deployments", self._deployments),
            ("services", self._services),
        ):
            try:
                handler(self._list(resource), harvest, observed)
            except Exception as exc:
                harvest.errors.append(f"{self.name}: {resource}: {type(exc).__name__}: {exc}")

        return harvest

    def _pods(self, items: list[dict], harvest: Harvest, observed: datetime) -> None:
        for pod in items:
            meta = pod.get("metadata", {})
            status = pod.get("status", {})
            namespace = meta.get("namespace")
            ref = self._ref(EntityKind.POD, meta.get("name", ""), namespace)
            phase = status.get("phase", "Unknown")

            container_statuses = status.get("containerStatuses") or []
            restarts = sum(int(c.get("restartCount", 0)) for c in container_statuses)
            not_ready = [c["name"] for c in container_statuses if not c.get("ready")]

            harvest.events.append(
                Event(
                    event_class=EventClass.STATE_CHANGE,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=_parse_time(status.get("startTime")) or observed,
                    observed_at=observed,
                    entity_ref=ref,
                    # A Running pod with unready containers is the failure mode
                    # that phase alone hides: it is scheduled and alive, and
                    # serving nothing.
                    severity=(
                        Severity.WARNING
                        if phase == "Running" and not_ready
                        else _PHASE_SEVERITY.get(phase, Severity.WARNING)
                    ),
                    payload=StateChangePayload(
                        resource=ref.name,
                        previous_state=None,
                        new_state=phase if not not_ready else f"{phase}/NotReady",
                        actor="kubernetes",
                    ),
                    provenance=Provenance(
                        source_system="kubernetes",
                        query=f"kubectl get pod {meta.get('name')} -n {namespace} -o json",
                    ),
                    labels=_labels(meta, namespace),
                )
            )

            if restarts:
                harvest.events.append(
                    Event(
                        event_class=EventClass.METRIC,
                        source=self.name,
                        source_version=self.version,
                        occurred_at=observed,
                        observed_at=observed,
                        entity_ref=ref,
                        severity=Severity.WARNING if restarts > 3 else None,
                        payload=MetricPayload(
                            name="pod_restart_count", value=float(restarts), unit="count"
                        ),
                        provenance=Provenance(
                            source_system="kubernetes",
                            query=f"kubectl get pod {meta.get('name')} -n {namespace}",
                        ),
                        labels=_labels(meta, namespace),
                    )
                )

            # Ownership: pod → ReplicaSet/StatefulSet/DaemonSet. Declared by the
            # platform, so it is a fact rather than an inference.
            for owner in meta.get("ownerReferences", []) or []:
                owner_ref = self._ref(EntityKind.SERVICE, owner.get("name", ""), namespace)
                harvest.edges.append(
                    Edge(source=ref.key(), target=owner_ref.key(), kind="owned_by")
                )

    def _deployments(self, items: list[dict], harvest: Harvest, observed: datetime) -> None:
        for deployment in items:
            meta = deployment.get("metadata", {})
            status = deployment.get("status", {})
            namespace = meta.get("namespace")
            ref = self._ref(EntityKind.DEPLOYMENT, meta.get("name", ""), namespace)

            containers = (
                deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            )
            image = containers[0].get("image", "") if containers else ""
            version = image.rpartition(":")[2] if ":" in image else "unknown"

            desired = int(status.get("replicas", 0) or 0)
            ready = int(status.get("readyReplicas", 0) or 0)

            harvest.events.append(
                Event(
                    event_class=EventClass.DEPLOYMENT,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=_parse_time(meta.get("creationTimestamp")) or observed,
                    observed_at=observed,
                    entity_ref=ref,
                    severity=Severity.CRITICAL if desired and not ready else None,
                    payload=DeploymentPayload(
                        service=ref.name,
                        version=version,
                        previous_version=None,
                        actor="kubernetes",
                        strategy=deployment.get("spec", {}).get("strategy", {}).get("type"),
                    ),
                    provenance=Provenance(
                        source_system="kubernetes",
                        query=f"kubectl get deployment {ref.name} -n {namespace} -o json",
                    ),
                    labels={**_labels(meta, namespace), "image": image},
                )
            )

            if desired:
                harvest.events.append(
                    Event(
                        event_class=EventClass.METRIC,
                        source=self.name,
                        source_version=self.version,
                        occurred_at=observed,
                        observed_at=observed,
                        entity_ref=ref,
                        severity=Severity.WARNING if ready < desired else None,
                        payload=MetricPayload(
                            name="deployment_ready_ratio",
                            value=round(100.0 * ready / desired, 2),
                            unit="percent",
                        ),
                        provenance=Provenance(
                            source_system="kubernetes",
                            query=f"kubectl get deployment {ref.name} -n {namespace}",
                        ),
                        labels=_labels(meta, namespace),
                    )
                )

    def _services(self, items: list[dict], harvest: Harvest, observed: datetime) -> None:
        for service in items:
            meta = service.get("metadata", {})
            namespace = meta.get("namespace")
            ref = self._ref(EntityKind.SERVICE, meta.get("name", ""), namespace)

            harvest.events.append(
                Event(
                    event_class=EventClass.STATE_CHANGE,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=_parse_time(meta.get("creationTimestamp")) or observed,
                    observed_at=observed,
                    entity_ref=ref,
                    payload=StateChangePayload(
                        resource=ref.name,
                        previous_state=None,
                        new_state=service.get("spec", {}).get("type", "ClusterIP"),
                        actor="kubernetes",
                    ),
                    provenance=Provenance(
                        source_system="kubernetes",
                        query=f"kubectl get service {ref.name} -n {namespace} -o json",
                    ),
                    labels=_labels(meta, namespace),
                )
            )


def _labels(meta: dict, namespace: str | None) -> dict[str, str]:
    labels = {str(k): str(v) for k, v in (meta.get("labels") or {}).items()}
    labels["namespace"] = str(namespace or "")
    if namespace in _SYSTEM_NAMESPACES:
        labels["tier"] = "infrastructure"
    return labels


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
