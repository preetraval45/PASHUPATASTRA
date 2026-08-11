"""Docker connector.

Reads the local container runtime — the reference stack the benchmark injects
faults into, and the on-prem path's compute source.

Shells out to the `docker` CLI rather than opening the daemon socket directly.
That is a deliberate trade: the CLI is slower, but the socket is a root-equivalent
capability on most hosts, and a *read-only* connector should not hold one. The
CLI also means no daemon-API version negotiation across Docker releases.
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
from pashupatastra.events import MetricPayload, StateChangePayload

from .base import Connector, Harvest, Window

# Container state → severity. `restarting` is a warning rather than info because
# a container that keeps restarting is the crash-loop signature, and the loop is
# only visible across polls.
_STATE_SEVERITY = {
    "running": Severity.INFO,
    "created": Severity.INFO,
    "paused": Severity.WARNING,
    "restarting": Severity.WARNING,
    "removing": Severity.WARNING,
    "exited": Severity.CRITICAL,
    "dead": Severity.CRITICAL,
}


class DockerConnector(Connector):
    name = "docker"

    def __init__(self, binary: str = "docker", timeout: float = 15.0) -> None:
        self.binary = binary
        self.timeout = timeout

    # --- cli ----------------------------------------------------------------

    def _run(self, *args: str) -> str:
        executable = shutil.which(self.binary) or self.binary
        completed = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout).strip()[:300])
        return completed.stdout

    def _containers(self) -> list[dict]:
        # `--all` so stopped containers are visible: a container that vanished
        # from `ps` is exactly the thing an incident needs to know about, and
        # listing only running ones would make a crash look like absence.
        raw = self._run("ps", "--all", "--no-trunc", "--format", "{{json .}}")
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def _inspect(self, container_id: str) -> dict:
        return json.loads(self._run("inspect", container_id))[0]

    # --- normalization ------------------------------------------------------

    @staticmethod
    def _ref(name: str, container_id: str) -> EntityRef:
        return EntityRef(
            kind=EntityKind.CONTAINER,
            id=container_id[:12],
            name=name.lstrip("/"),
        )

    def poll(self, window: Window) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        try:
            containers = self._containers()
        except Exception as exc:
            harvest.errors.append(f"{self.name}: {type(exc).__name__}: {exc}")
            return harvest

        for summary in containers:
            container_id = summary.get("ID") or summary.get("Id") or ""
            name = summary.get("Names") or summary.get("Name") or container_id
            if not container_id:
                continue

            try:
                detail = self._inspect(container_id)
            except Exception as exc:
                harvest.errors.append(f"{self.name}: inspect {name}: {exc}")
                continue

            state = detail.get("State", {})
            status = str(state.get("Status", "unknown")).lower()
            ref = self._ref(name, container_id)
            labels = {
                k: str(v)
                for k, v in (detail.get("Config", {}).get("Labels") or {}).items()
                if not k.startswith("desktop.")
            }
            labels["image"] = str(detail.get("Config", {}).get("Image", ""))

            harvest.events.append(
                Event(
                    event_class=EventClass.STATE_CHANGE,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=_parse_time(state.get("StartedAt")) or observed,
                    observed_at=observed,
                    entity_ref=ref,
                    severity=_STATE_SEVERITY.get(status, Severity.WARNING),
                    payload=StateChangePayload(
                        resource=ref.name,
                        previous_state=None,
                        new_state=status,
                        actor="docker",
                    ),
                    provenance=Provenance(
                        source_system="docker",
                        query=f"docker inspect {container_id[:12]}",
                    ),
                    labels=labels,
                )
            )

            # Restart count is the crash-loop signal. It is emitted every poll,
            # not only when it changes, so the reasoning layer sees the rate
            # rather than having to reconstruct it from edges.
            # Top-level in `docker inspect`, not under State.
            restarts = detail.get("RestartCount")
            if isinstance(restarts, int):
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
                            name="container_restart_count",
                            value=float(restarts),
                            unit="count",
                        ),
                        provenance=Provenance(
                            source_system="docker",
                            query=f"docker inspect {container_id[:12]}",
                        ),
                        labels={"image": labels["image"]},
                    )
                )

        return harvest


def _parse_time(value: str | None) -> datetime | None:
    """Docker emits RFC3339 with nanosecond precision, which `fromisoformat`
    cannot parse before 3.11 and still dislikes at 9 digits."""
    if not value or value.startswith("0001-01-01"):
        return None
    cleaned = value.replace("Z", "+00:00")
    if "." in cleaned:
        head, _, tail = cleaned.partition(".")
        fraction, sign, offset = _split_offset(tail)
        cleaned = f"{head}.{fraction[:6]}{sign}{offset}"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _split_offset(tail: str) -> tuple[str, str, str]:
    for sign in ("+", "-"):
        if sign in tail:
            fraction, _, offset = tail.partition(sign)
            return fraction, sign, offset
    return tail, "", ""
