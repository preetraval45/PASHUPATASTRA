"""Kubernetes connector.

Kubernetes is the one source allowed to assert dependency edges from structure,
because ownerReferences are a declaration by the platform rather than an
inference from behaviour. The tests below pin both the normalization and that
boundary.
"""

from __future__ import annotations

import json

import pytest
from drishti import KubernetesConnector, Window
from pashupatastra import EntityKind, EventClass, Severity


class FakeKubectl(KubernetesConnector):
    def __init__(self, **resources: list[dict]) -> None:
        super().__init__(context="test")
        self._resources = resources

    def _run(self, *args: str) -> str:
        resource = args[1]
        return json.dumps({"items": self._resources.get(resource, [])})


def pod(
    name: str = "checkout-api-abc",
    phase: str = "Running",
    ready: bool = True,
    restarts: int = 0,
    owner: str | None = "checkout-api-7d9f",
) -> dict:
    meta: dict = {"name": name, "namespace": "default", "labels": {"app": "checkout"}}
    if owner:
        meta["ownerReferences"] = [{"kind": "ReplicaSet", "name": owner}]
    return {
        "metadata": meta,
        "status": {
            "phase": phase,
            "startTime": "2026-08-11T10:00:00Z",
            "containerStatuses": [{"name": "app", "ready": ready, "restartCount": restarts}],
        },
    }


def deployment(name: str = "checkout-api", replicas: int = 3, ready: int = 3) -> dict:
    return {
        "metadata": {"name": name, "namespace": "default", "creationTimestamp": "2026-08-01T09:00:00Z"},
        "spec": {
            "strategy": {"type": "RollingUpdate"},
            "template": {"spec": {"containers": [{"image": "checkout:v4.21"}]}},
        },
        "status": {"replicas": replicas, "readyReplicas": ready},
    }


def test_pod_becomes_a_state_change_event() -> None:
    harvest = FakeKubectl(pods=[pod()]).poll(Window.trailing(300))
    event = next(e for e in harvest.events if e.entity_ref.kind is EntityKind.POD)
    assert event.payload.new_state == "Running"
    assert event.severity is Severity.INFO


def test_running_but_unready_is_a_warning() -> None:
    """The failure mode phase alone hides: scheduled, alive, serving nothing."""
    harvest = FakeKubectl(pods=[pod(ready=False)]).poll(Window.trailing(60))
    event = harvest.events[0]
    assert event.severity is Severity.WARNING
    assert event.payload.new_state == "Running/NotReady"


def test_failed_pod_is_critical() -> None:
    harvest = FakeKubectl(pods=[pod(phase="Failed")]).poll(Window.trailing(60))
    assert harvest.events[0].severity is Severity.CRITICAL


def test_owner_reference_becomes_a_structural_edge() -> None:
    harvest = FakeKubectl(pods=[pod()]).poll(Window.trailing(60))
    assert len(harvest.edges) == 1
    edge = harvest.edges[0]
    assert edge.source == "pod:default/checkout-api-abc"
    assert edge.target == "service:default/checkout-api-7d9f"
    assert edge.kind == "owned_by"


def test_pod_without_an_owner_creates_no_edge() -> None:
    """A bare pod is owned by nothing; inventing an edge would be a guess."""
    harvest = FakeKubectl(pods=[pod(owner=None)]).poll(Window.trailing(60))
    assert harvest.edges == []


def test_restart_count_is_emitted_only_when_nonzero() -> None:
    quiet = FakeKubectl(pods=[pod(restarts=0)]).poll(Window.trailing(60))
    assert not [e for e in quiet.events if e.event_class is EventClass.METRIC]

    noisy = FakeKubectl(pods=[pod(restarts=9)]).poll(Window.trailing(60))
    metric = next(e for e in noisy.events if e.event_class is EventClass.METRIC)
    assert metric.payload.value == 9.0
    assert metric.severity is Severity.WARNING


def test_deployment_version_comes_from_the_image_tag() -> None:
    harvest = FakeKubectl(deployments=[deployment()]).poll(Window.trailing(60))
    event = next(e for e in harvest.events if e.event_class is EventClass.DEPLOYMENT)
    assert event.payload.version == "v4.21"
    assert event.payload.strategy == "RollingUpdate"


def test_deployment_with_no_ready_replicas_is_critical() -> None:
    harvest = FakeKubectl(deployments=[deployment(replicas=3, ready=0)]).poll(Window.trailing(60))
    event = next(e for e in harvest.events if e.event_class is EventClass.DEPLOYMENT)
    assert event.severity is Severity.CRITICAL


def test_partial_rollout_is_a_warning_on_the_ready_ratio() -> None:
    harvest = FakeKubectl(deployments=[deployment(replicas=4, ready=1)]).poll(Window.trailing(60))
    metric = next(e for e in harvest.events if e.event_class is EventClass.METRIC)
    assert metric.payload.name == "deployment_ready_ratio"
    assert metric.payload.value == 25.0
    assert metric.severity is Severity.WARNING


def test_system_namespaces_are_labelled_infrastructure() -> None:
    """Included, because a failing CoreDNS is very much an incident — but marked
    so blast radius can tell infrastructure from workload."""
    system = pod()
    system["metadata"]["namespace"] = "kube-system"
    harvest = FakeKubectl(pods=[system]).poll(Window.trailing(60))
    assert harvest.events[0].labels["tier"] == "infrastructure"


def test_one_failing_resource_does_not_lose_the_others() -> None:
    class PartiallyBroken(FakeKubectl):
        def _run(self, *args: str) -> str:
            if args[1] == "deployments":
                raise RuntimeError("forbidden")
            return super()._run(*args)

    harvest = PartiallyBroken(pods=[pod()]).poll(Window.trailing(60))
    assert harvest.events, "pods still came through"
    assert not harvest.healthy
    assert "deployments" in harvest.errors[0]


def test_provenance_is_a_runnable_kubectl_command() -> None:
    harvest = FakeKubectl(pods=[pod()]).poll(Window.trailing(60))
    assert harvest.events[0].provenance.query.startswith("kubectl get pod")


@pytest.mark.skipif(
    not KubernetesConnector(context="kind-pashupatastra").check(),
    reason="kind cluster not running",
)
def test_against_the_live_cluster() -> None:
    harvest = KubernetesConnector(context="kind-pashupatastra").poll(Window.trailing(300))
    assert harvest.healthy
    assert harvest.events
    assert harvest.edges, "expected ownerReferences from kube-system workloads"
