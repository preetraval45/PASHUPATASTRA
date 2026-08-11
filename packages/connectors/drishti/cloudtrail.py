"""CloudTrail — AWS control-plane changes.

Two distinct jobs, and conflating them would lose the more valuable one.

**Perception.** Someone resized an RDS instance, changed a security group, or
rolled a deployment. Control-plane changes are `state_change` events and are
prime causal candidates, for the same reason application deployments are: most
failures follow a change.

**Independent verification.** CloudTrail records what AWS *actually executed*,
written by AWS rather than by this platform. That makes it the only source able
to check the system's account of its own actions — an internal audit log is
evidence about the world, but an audit log that grades itself is not evidence
about the audit log. Divergence between the two is a reportable defect
(docs/DEPLOYMENT.md), and reconciling them is a result worth publishing.

`boto3` lives here rather than in `packages/core`, which contains zero AWS
imports by design (Platform ADR). Credentials come from the connector's
read-only IAM role — a control-plane reader that could also write would let
perception change what it observes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pashupatastra import (
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Provenance,
    QuarantinedEvent,
    Severity,
)
from pashupatastra.events import SecurityPayload, StateChangePayload

from .base import Connector, Harvest, Window

# Events worth reasoning about. CloudTrail is enormous and mostly reads; an
# unfiltered feed would bury the handful of changes that matter under millions
# of Describe calls.
MUTATING_PREFIXES = (
    "Create",
    "Delete",
    "Update",
    "Modify",
    "Put",
    "Attach",
    "Detach",
    "Terminate",
    "Reboot",
    "Restore",
    "Start",
    "Stop",
)

# Control-plane actions that are security-relevant regardless of outcome. These
# become `security` events rather than `state_change`, because "someone changed
# an IAM policy" is a different kind of fact from "someone resized a database".
SECURITY_EVENTS = {
    "ConsoleLogin",
    "AssumeRole",
    "CreateAccessKey",
    "DeleteTrail",
    "StopLogging",
    "PutUserPolicy",
    "AttachUserPolicy",
    "AttachRolePolicy",
    "CreateUser",
    "DeleteUser",
    "UpdateAssumeRolePolicy",
    "DisableKey",
    "ScheduleKeyDeletion",
}

_SERVICE_KIND = {
    "rds.amazonaws.com": EntityKind.DATABASE,
    "elasticache.amazonaws.com": EntityKind.CACHE,
    "eks.amazonaws.com": EntityKind.SERVICE,
    "ec2.amazonaws.com": EntityKind.HOST,
    "elasticloadbalancing.amazonaws.com": EntityKind.LOADBALANCER,
    "sqs.amazonaws.com": EntityKind.QUEUE,
}


class CloudTrailConnector(Connector):
    name = "cloudtrail"

    def __init__(self, client=None, region: str = "us-east-1", max_results: int = 200) -> None:
        """`client` is a boto3 CloudTrail client. It is injected rather than
        constructed here so this module imports without AWS configured, and so
        the tests exercise normalization without a cloud."""
        self._client = client
        self.region = region
        self.max_results = max_results

    def _lookup(self, window: Window) -> list[dict]:
        if self._client is None:
            raise RuntimeError("no CloudTrail client configured")
        events, token = [], None
        while True:
            kwargs = {
                "StartTime": window.start,
                "EndTime": window.end,
                "MaxResults": min(50, self.max_results),
            }
            if token:
                kwargs["NextToken"] = token
            page = self._client.lookup_events(**kwargs)
            events.extend(page.get("Events", []))
            token = page.get("NextToken")
            if not token or len(events) >= self.max_results:
                return events[: self.max_results]

    def poll(self, window: Window) -> Harvest:
        harvest = Harvest()
        observed = datetime.now().astimezone()

        try:
            raw_events = self._lookup(window)
        except Exception as exc:
            harvest.errors.append(f"{self.name}: {type(exc).__name__}: {exc}")
            return harvest

        for raw in raw_events:
            name = str(raw.get("EventName", ""))
            security = name in SECURITY_EVENTS
            if not security and not name.startswith(MUTATING_PREFIXES):
                continue  # a read; nothing changed

            resources = raw.get("Resources") or []
            source = str(raw.get("EventSource", ""))
            resource_name = (
                str(resources[0].get("ResourceName", "")) if resources else ""
            ) or str(raw.get("EventId", ""))[:12]

            if not resource_name:
                harvest.quarantined.append(
                    QuarantinedEvent(
                        raw={"EventName": name, "EventId": raw.get("EventId")},
                        source=self.name,
                        reason="control-plane event names no resource",
                        observed_at=observed,
                    )
                )
                continue

            ref = EntityRef(
                kind=_SERVICE_KIND.get(source, EntityKind.CLOUD_RESOURCE),
                id=resource_name,
                name=resource_name.rsplit("/", 1)[-1] or resource_name,
                cluster=self.region,
            )
            actor = str(raw.get("Username") or "unknown")
            occurred = _as_utc(raw.get("EventTime")) or observed
            provenance = Provenance(
                source_system="cloudtrail",
                query=f"lookup-events --lookup-attributes EventId={raw.get('EventId')}",
            )

            if security:
                harvest.events.append(
                    Event(
                        event_class=EventClass.SECURITY,
                        source=self.name,
                        source_version=self.version,
                        occurred_at=occurred,
                        observed_at=observed,
                        entity_ref=ref,
                        # Deliberately not "critical": an AssumeRole is normal
                        # a thousand times a day. Kavach decides what is an
                        # attack by correlating, and a connector that cried
                        # critical on every login would train operators to
                        # ignore it.
                        severity=Severity.WARNING,
                        payload=SecurityPayload(
                            detection_type=name,
                            principal=actor,
                            source_address=str(raw.get("SourceIPAddress") or "") or None,
                            asset=resource_name,
                            confidence=0.5,
                        ),
                        provenance=provenance,
                        labels={"event_source": source, "region": self.region},
                    )
                )
                continue

            harvest.events.append(
                Event(
                    event_class=EventClass.STATE_CHANGE,
                    source=self.name,
                    source_version=self.version,
                    occurred_at=occurred,
                    observed_at=observed,
                    entity_ref=ref,
                    severity=None,
                    payload=StateChangePayload(
                        resource=resource_name,
                        # CloudTrail reports the call, not the prior state.
                        # Leaving this None is honest; reconstructing it would
                        # be a guess placed in front of a root-cause analysis.
                        previous_state=None,
                        new_state=name,
                        actor=actor,
                    ),
                    provenance=provenance,
                    labels={"event_source": source, "region": self.region},
                )
            )

        return harvest


def _as_utc(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
