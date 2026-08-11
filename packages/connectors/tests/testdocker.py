"""Docker connector.

Normalization is tested against canned CLI output; one test runs against the
real daemon when it is available.
"""

from __future__ import annotations

import json

import pytest
from drishti import DockerConnector, Window
from pashupatastra import EntityKind, EventClass, Severity


class FakeDocker(DockerConnector):
    """Substitutes the CLI, leaving all normalization under test."""

    def __init__(self, containers: list[dict], details: dict[str, dict]) -> None:
        super().__init__()
        self._containers_data = containers
        self._details = details

    def _run(self, *args: str) -> str:
        if args[0] == "ps":
            return "\n".join(json.dumps(c) for c in self._containers_data)
        if args[0] == "inspect":
            return json.dumps([self._details[args[1]]])
        raise AssertionError(f"unexpected docker call: {args}")


def detail(status: str, restarts: int = 0, started: str = "2026-08-11T10:00:00.123456789Z") -> dict:
    return {
        "State": {"Status": status, "StartedAt": started},
        "RestartCount": restarts,
        "Config": {"Image": "postgres:16-alpine", "Labels": {"com.docker.compose.service": "db"}},
    }


def connector(status: str = "running", restarts: int = 0, **kwargs) -> FakeDocker:
    return FakeDocker(
        [{"ID": "abc123def456789", "Names": "/pashupatastra-postgres-1"}],
        {"abc123def456789": detail(status, restarts, **kwargs)},
    )


def test_container_becomes_a_state_change_event() -> None:
    harvest = connector().poll(Window.trailing(300))
    event = next(e for e in harvest.events if e.event_class is EventClass.STATE_CHANGE)
    assert event.entity_ref.kind is EntityKind.CONTAINER
    assert event.entity_ref.name == "pashupatastra-postgres-1"
    assert event.payload.new_state == "running"


def test_container_id_is_truncated_to_the_short_form() -> None:
    harvest = connector().poll(Window.trailing(60))
    assert harvest.events[0].entity_ref.id == "abc123def456"


def test_exited_container_is_critical() -> None:
    harvest = connector(status="exited").poll(Window.trailing(60))
    assert harvest.events[0].severity is Severity.CRITICAL


def test_restarting_is_a_warning_not_info() -> None:
    """A container that keeps restarting is the crash-loop signature, and the
    loop is only visible across polls."""
    harvest = connector(status="restarting").poll(Window.trailing(60))
    assert harvest.events[0].severity is Severity.WARNING


def test_restart_count_is_emitted_every_poll() -> None:
    """Emitted even when unchanged, so the reasoning layer sees a rate rather
    than having to reconstruct one from edges."""
    harvest = connector(restarts=0).poll(Window.trailing(60))
    metric = next(e for e in harvest.events if e.event_class is EventClass.METRIC)
    assert metric.payload.name == "container_restart_count"
    assert metric.payload.value == 0.0


def test_high_restart_count_is_flagged() -> None:
    harvest = connector(restarts=7).poll(Window.trailing(60))
    metric = next(e for e in harvest.events if e.event_class is EventClass.METRIC)
    assert metric.severity is Severity.WARNING


def test_nanosecond_timestamps_parse() -> None:
    """Docker emits RFC3339 with nine fractional digits, which trips the stdlib."""
    harvest = connector(started="2026-08-11T10:00:00.123456789Z").poll(Window.trailing(60))
    assert harvest.events[0].occurred_at.year == 2026


def test_never_started_container_falls_back_to_observation_time() -> None:
    harvest = connector(status="created", started="0001-01-01T00:00:00Z").poll(Window.trailing(60))
    assert harvest.events[0].occurred_at.year >= 2026


def test_provenance_names_the_inspect_command() -> None:
    harvest = connector().poll(Window.trailing(60))
    assert "docker inspect abc123def456" in harvest.events[0].provenance.query


def test_daemon_failure_is_reported_not_raised() -> None:
    class Broken(DockerConnector):
        def _run(self, *args: str) -> str:
            raise RuntimeError("Cannot connect to the Docker daemon")

    harvest = Broken().poll(Window.trailing(60))
    assert harvest.events == []
    assert not harvest.healthy
    assert "daemon" in harvest.errors[0]


@pytest.mark.skipif(not DockerConnector().check(), reason="Docker daemon not running")
def test_against_the_live_daemon() -> None:
    harvest = DockerConnector().poll(Window.trailing(300))
    assert harvest.healthy
    assert all(e.provenance.query for e in harvest.events)
