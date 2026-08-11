"""CI/CD deployment events.

Change correlation is the single highest-yield causal signal in incident
diagnosis: most production failures follow a deployment, and the interval
between "v4.21 shipped" and "errors rose" is the strongest evidence the
reasoning layer ever gets. That is why `deployment` is a first-class event class
rather than a variety of `state_change` (docs/specs/Event Model.md).

The connector is deliberately thin. It records *that* a version changed, when,
by whom, and at what commit. It does not read the diff, and it does not guess
whether the change was risky — deciding that a deployment caused a failure is
Buddhi's job, made against the timing and the topology, not the connector's.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from pashupatastra import EntityKind, EntityRef, Event, EventClass, Provenance
from pashupatastra.events import DeploymentPayload

from .base import Connector, Harvest, Window


class GithubDeploymentsConnector(Connector):
    """Reads GitHub Actions deployment history.

    Requires a read-only token with `repo:status` / `deployments:read`. A CI
    connector that could *trigger* a workflow would give perception the ability
    to change the system it observes, so this one only reads — the same rule
    every connector follows.
    """

    name = "github-deployments"

    def __init__(
        self,
        repository: str,
        token: str | None = None,
        base_url: str = "https://api.github.com",
        environments: tuple[str, ...] = ("production", "prod"),
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.repository = repository
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.environments = environments
        self.timeout = timeout
        self._client = client
        # Previous version per service, so a deployment event can say what it
        # replaced. Held in memory: on restart the first event of each service
        # simply has no predecessor, which is honest — inventing one would put a
        # fabricated "from" version in front of a root-cause analysis.
        self._last_version: dict[str, str] = {}

    def _http(self) -> httpx.Client:
        if self._client is None:
            headers = {"Accept": "application/vnd.github+json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.Client(timeout=self.timeout, headers=headers)
        return self._client

    def poll(self, window: Window) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        try:
            response = self._http().get(
                f"{self.base_url}/repos/{self.repository}/deployments",
                params={"per_page": 50},
            )
            response.raise_for_status()
            deployments = response.json()
        except Exception as exc:
            harvest.errors.append(f"{self.name}: {type(exc).__name__}: {exc}")
            return harvest

        for deployment in deployments:
            created = _parse_time(deployment.get("created_at"))
            if created is None or not (window.start < created <= window.end):
                continue

            environment = str(deployment.get("environment", ""))
            if self.environments and environment.lower() not in self.environments:
                continue

            service = _service_name(deployment) or self.repository.split("/")[-1]
            version = str(deployment.get("ref") or deployment.get("sha", ""))[:40]
            previous = self._last_version.get(service)
            self._last_version[service] = version

            harvest.events.append(
                Event(
                    event_class=EventClass.DEPLOYMENT,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=created,
                    observed_at=observed,
                    entity_ref=EntityRef(
                        kind=EntityKind.SERVICE, id=service, name=service
                    ),
                    # A deployment is not itself a problem. Severity stays unset
                    # so nothing downstream reads "a deploy happened" as "a
                    # deploy broke something" — that inference belongs to
                    # correlation, against timing and topology.
                    severity=None,
                    payload=DeploymentPayload(
                        service=service,
                        version=version,
                        previous_version=previous,
                        actor=(deployment.get("creator") or {}).get("login"),
                        commit=str(deployment.get("sha", ""))[:40] or None,
                        strategy=environment or None,
                    ),
                    provenance=Provenance(
                        source_system="github",
                        url=deployment.get("url"),
                        query=f"repos/{self.repository}/deployments/{deployment.get('id')}",
                    ),
                    labels={"environment": environment},
                )
            )

        return harvest


class WebhookDeployments:
    """Normalizes a deployment webhook pushed by any CI system.

    A receiver rather than a connector, for the same reason OTLP is: the sender
    chooses when to emit and does not retry, so a malformed payload is reported
    and the rest is kept.
    """

    name = "cicd-webhook"
    version = "0.1.0"

    def receive(self, payload: dict) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        service = payload.get("service")
        version = payload.get("version")
        if not service or not version:
            harvest.errors.append(
                f"{self.name}: payload needs both 'service' and 'version'"
            )
            return harvest

        harvest.events.append(
            Event(
                event_class=EventClass.DEPLOYMENT,
                source=self.name,
                source_version=self.version,
                occurred_at=_parse_time(payload.get("deployed_at")) or observed,
                observed_at=observed,
                entity_ref=EntityRef(
                    kind=EntityKind.SERVICE, id=str(service), name=str(service)
                ),
                severity=None,
                payload=DeploymentPayload(
                    service=str(service),
                    version=str(version),
                    previous_version=(
                        str(payload["previous_version"])
                        if payload.get("previous_version")
                        else None
                    ),
                    actor=str(payload.get("actor") or "") or None,
                    commit=str(payload.get("commit") or "") or None,
                    strategy=str(payload.get("strategy") or "") or None,
                ),
                provenance=Provenance(
                    source_system=str(payload.get("source") or "ci"),
                    url=str(payload.get("url") or "") or None,
                ),
                labels={"environment": str(payload.get("environment") or "")},
            )
        )
        return harvest


def _service_name(deployment: dict) -> str | None:
    payload = deployment.get("payload")
    if isinstance(payload, dict):
        for key in ("service", "app", "component"):
            if payload.get(key):
                return str(payload[key])
    task = deployment.get("task")
    if task and task != "deploy":
        return str(task)
    return None


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
