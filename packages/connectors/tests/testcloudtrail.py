"""CloudTrail — control-plane changes and independent verification."""

from __future__ import annotations

from datetime import datetime, timezone

from drishti import CloudTrailConnector, Window
from pashupatastra import EntityKind, EventClass, Severity

NOW = datetime.now(timezone.utc)


class FakeCloudTrail:
    def __init__(self, events: list[dict]) -> None:
        self._events = events

    def lookup_events(self, **kwargs) -> dict:
        return {"Events": self._events}


def event(name: str, source: str = "rds.amazonaws.com", resource: str = "pashupatastra-prod", **extra) -> dict:
    return {
        "EventId": "e-1",
        "EventName": name,
        "EventSource": source,
        "EventTime": NOW,
        "Username": "preet",
        "Resources": [{"ResourceName": resource}] if resource else [],
        **extra,
    }


def connector(events: list[dict]) -> CloudTrailConnector:
    return CloudTrailConnector(client=FakeCloudTrail(events))


def test_mutating_call_becomes_a_state_change() -> None:
    harvest = connector([event("ModifyDBInstance")]).poll(Window.trailing(300))
    e = harvest.events[0]
    assert e.event_class is EventClass.STATE_CHANGE
    assert e.payload.new_state == "ModifyDBInstance"
    assert e.payload.actor == "preet"


def test_reads_are_filtered_out() -> None:
    """CloudTrail is mostly Describe calls; an unfiltered feed buries the
    handful of changes that matter."""
    harvest = connector(
        [event("DescribeDBInstances"), event("ListBuckets"), event("GetObject")]
    ).poll(Window.trailing(300))
    assert harvest.events == []


def test_previous_state_is_not_invented() -> None:
    """CloudTrail reports the call, not the prior state. Reconstructing one
    would put a guess in front of a root-cause analysis."""
    harvest = connector([event("ModifyDBInstance")]).poll(Window.trailing(300))
    assert harvest.events[0].payload.previous_state is None


def test_entity_kind_follows_the_aws_service() -> None:
    harvest = connector([event("ModifyDBInstance", source="rds.amazonaws.com")]).poll(
        Window.trailing(300)
    )
    assert harvest.events[0].entity_ref.kind is EntityKind.DATABASE

    harvest = connector([event("TerminateInstances", source="ec2.amazonaws.com")]).poll(
        Window.trailing(300)
    )
    assert harvest.events[0].entity_ref.kind is EntityKind.HOST


def test_security_relevant_calls_become_security_events() -> None:
    harvest = connector(
        [event("CreateAccessKey", source="iam.amazonaws.com", SourceIPAddress="203.0.113.5")]
    ).poll(Window.trailing(300))
    e = harvest.events[0]
    assert e.event_class is EventClass.SECURITY
    assert e.payload.principal == "preet"
    assert e.payload.source_address == "203.0.113.5"


def test_security_events_are_not_automatically_critical() -> None:
    """An AssumeRole happens a thousand times a day. Crying critical on every
    login trains operators to ignore the signal."""
    harvest = connector([event("AssumeRole", source="sts.amazonaws.com")]).poll(
        Window.trailing(300)
    )
    assert harvest.events[0].severity is Severity.WARNING


def test_stopping_the_trail_is_itself_recorded() -> None:
    """Disabling audit logging is the first move of anyone covering tracks."""
    harvest = connector([event("StopLogging", source="cloudtrail.amazonaws.com")]).poll(
        Window.trailing(300)
    )
    assert harvest.events[0].event_class is EventClass.SECURITY


def test_provenance_is_a_runnable_lookup() -> None:
    harvest = connector([event("ModifyDBInstance")]).poll(Window.trailing(300))
    assert "EventId=e-1" in harvest.events[0].provenance.query


def test_missing_client_is_reported_not_raised() -> None:
    harvest = CloudTrailConnector().poll(Window.trailing(300))
    assert harvest.events == []
    assert not harvest.healthy
    assert "client" in harvest.errors[0]


def test_api_failure_is_reported_not_raised() -> None:
    class Broken:
        def lookup_events(self, **kwargs):
            raise RuntimeError("AccessDenied")

    harvest = CloudTrailConnector(client=Broken()).poll(Window.trailing(300))
    assert not harvest.healthy
    assert "AccessDenied" in harvest.errors[0]
