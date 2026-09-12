"""API tests, centred on the Phase 3 exit criterion: no execution path reaches a
connector without a recorded policy verdict."""

from __future__ import annotations

import pytest
from app.main import app
from fastapi.testclient import TestClient
from pashupatastra import PolicyViolation

client = TestClient(app)

# A few tests assert the *infrastructure* fixture — its action ids and its demo
# incident. CI also runs this suite in the deployed configuration (security
# domain, demo scenarios seeded), because that is the only configuration in
# which the chat battery, the R20 proposal test and the Blue Team tests run at
# all; a suite whose most important tests skip on every run is green for the
# wrong reason. These three say which fixture they are about instead of failing.
from app.config import get_settings as _settings  # noqa: E402
from pashupatastra.dharma import ActionDomain as _Domain  # noqa: E402

infrastructure_fixture = pytest.mark.skipif(
    _settings().action_domain not in (None, _Domain.INFRASTRUCTURE),
    reason="asserts the infrastructure fixture; this run serves the security domain",
)


def evaluate(action_id: str, **kwargs: object) -> dict:
    body: dict[str, object] = {"action_id": action_id}
    body.update(kwargs)
    response = client.post("/api/v1/policy/evaluate", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_health_reports_dry_run_default() -> None:
    body = client.get("/api/v1/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert body["dry_run"] is True, "dry-run must be the default (SECURITY.md control 1)"


def test_health_flags_a_non_durable_audit_trail() -> None:
    """An in-memory audit trail must never report itself as healthy.

    Named against `memory` rather than a specific backend. Asserting
    `== "postgres"` encoded the bug it was meant to catch: it passed while a
    DynamoDB deployment reported the wrong store, and failed once the store
    started naming itself honestly.
    """
    body = client.get("/api/v1/health").json()
    assert (body["audit_storage"] == "memory") == (body["status"] == "degraded")


@infrastructure_fixture
def test_action_registry_is_exposed() -> None:
    actions = client.get("/api/v1/actions").json()
    ids = {a["id"] for a in actions}
    assert "rollback_deployment" in ids
    assert "delete_infrastructure" in ids


def test_unregistered_action_cannot_be_evaluated() -> None:
    response = client.post("/api/v1/policy/evaluate", json={"action_id": "rm_minus_rf"})
    assert response.status_code == 404


def test_a_draft_is_served_labelled_and_cited(seeded_incident: str = "") -> None:
    """R70, over the route. Every line has refs and the document says it is a
    draft — checked here as well as in core, because the shape a browser sees is
    what a reader is actually held to."""
    incidents = client.get("/api/v1/incidents").json()
    if not incidents:
        pytest.skip("no incidents are seeded in this configuration")
    incident_id = incidents[0]["id"]

    for kind in ("playbook", "post_incident"):
        body = client.get(f"/api/v1/incidents/{incident_id}/draft/{kind}").json()
        assert body["status"] == "draft"
        assert body["title"].lower().startswith("draft")
        assert body["adopt_action_id"] in ("adopt_playbook", "adopt_report")
        lines = [line for section in body["sections"] for line in section["lines"]]
        assert lines, f"{kind} rendered no lines"
        for line in lines:
            assert line["refs"], line["text"]


def test_an_unknown_draft_kind_is_a_404_rather_than_an_empty_document() -> None:
    incidents = client.get("/api/v1/incidents").json()
    if not incidents:
        pytest.skip("no incidents are seeded in this configuration")
    response = client.get(f"/api/v1/incidents/{incidents[0]['id']}/draft/executive_summary")
    assert response.status_code == 404


def test_adopting_a_draft_is_scored_like_any_other_action() -> None:
    """The clause that matters: there is no adopt path that skips policy. The
    id resolves in the registry, Dharma scores it, and the tier it lands in is
    the one that decides who may accept it."""
    verdict = evaluate("adopt_playbook")
    assert verdict["tier"] != "autonomous", (
        "a playbook the team follows next time must not be adoptable without a human"
    )
    assert verdict["effective_risk"] > 0


def test_a_verdict_carries_the_reasoning_that_produced_its_tier() -> None:
    """R65. The approval panel explains the tier from these, so the route has to
    serve them — a panel with nothing to render falls back to the arithmetic,
    which is the explanation that does not fit the interesting cases."""
    verdict = evaluate("force_password_reset")
    assert verdict["tier"] == "denied"
    steps = verdict["tier_reasons"]
    assert steps[0]["rule"] == "risk_band"
    assert steps[0]["to_tier"] == "autonomous", "the score alone would have allowed this"
    assert steps[-1]["to_tier"] == verdict["tier"]
    assert steps[-1]["factor"] == "reversibility"


def test_a_verdict_posted_back_without_its_reasoning_is_still_accepted() -> None:
    """A client that has not been redeployed yet still holds older verdicts.

    Refusing them would make the approval path fail during the window between
    the API rolling out and the dashboard following it — the one moment an
    operator is most likely to be approving something.
    """
    verdict = evaluate("restart_service")
    del verdict["tier_reasons"]
    result = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "restart_service", "verdict": verdict},
    )
    assert result.status_code == 200


def test_autonomous_action_executes() -> None:
    verdict = evaluate("restart_service")
    assert verdict["tier"] == "autonomous"
    result = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "restart_service", "verdict": verdict},
    )
    assert result.status_code == 200
    assert result.json()["dry_run"] is True


def test_approval_tier_is_refused_until_approved() -> None:
    verdict = evaluate("rollback_deployment", environment="prod")
    assert verdict["tier"] == "approval"

    refused = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "rollback_deployment", "verdict": verdict},
    )
    assert refused.status_code == 403

    approved = client.post(
        "/api/v1/policy/approve", json={"verdict": verdict, "approver": "preet"}
    ).json()
    allowed = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "rollback_deployment", "verdict": approved},
    )
    assert allowed.status_code == 200


def test_denied_verdict_cannot_be_approved() -> None:
    verdict = evaluate("delete_infrastructure")
    assert verdict["tier"] == "denied"
    response = client.post("/api/v1/policy/approve", json={"verdict": verdict, "approver": "preet"})
    assert response.status_code == 403


def test_verdict_for_another_action_is_rejected() -> None:
    verdict = evaluate("restart_service")
    response = client.post(
        "/api/v1/actions/execute",
        json={"action_id": "clear_cache", "verdict": verdict},
    )
    assert response.status_code == 403


def test_execute_requires_a_verdict_argument() -> None:
    response = client.post("/api/v1/actions/execute", json={"action_id": "restart_service"})
    assert response.status_code == 422, "verdict must be a required field, not optional"


def test_engine_level_bypass_is_impossible() -> None:
    """The guard lives in the engine, not only in the HTTP layer."""
    from app.engines import astra

    with pytest.raises(PolicyViolation):
        astra.execute("restart_service", verdict=None)


def test_policy_denials_are_audited() -> None:
    evaluate("delete_infrastructure", incident_ref="INC-TEST-0001")
    records = client.get("/api/v1/audit", params={"incident_ref": "INC-TEST-0001"}).json()
    assert any(r["kind"] == "policy_evaluation" for r in records)


def _ledger(incident_ref: str) -> int:
    return len(client.get("/api/v1/audit", params={"incident_ref": incident_ref}).json())


def test_a_preview_leaves_the_ledger_alone_and_an_evaluation_does_not() -> None:
    """R93. Reading a verdict is not making one.

    The incident page renders a verdict three times per view; through
    `/policy/evaluate` that was three audit records per page load, and 48% of
    the ledger was renders. Counted before and after rather than asserted on
    the route's word, because the bug was a route doing what it was written to
    do.
    """
    ref = "INC-TEST-R93"
    body = {"action_id": "isolate_host", "incident_ref": ref, "blast_radius_entities": 5}
    before = _ledger(ref)
    previews = [client.post("/api/v1/policy/preview", json=body) for _ in range(10)]
    assert all(r.status_code == 200 for r in previews)
    assert _ledger(ref) == before, "ten page views wrote to the audit ledger"

    recorded = client.post("/api/v1/policy/evaluate", json=body)
    assert recorded.status_code == 200
    assert _ledger(ref) == before + 1, "authorising must still record exactly one"

    # The arithmetic is the same; only the ledger differs.
    preview, verdict = previews[0].json(), recorded.json()
    for field in ("action_id", "effective_risk", "tier", "required_approvers", "tier_reasons"):
        assert preview[field] == verdict[field]


def test_a_preview_verdict_cannot_be_approved() -> None:
    """A verdict nobody recorded must not become an approval with no
    evaluation before it in the trail — the mark is what makes a preview a
    preview rather than an evaluation that forgot to write."""
    preview = client.post(
        "/api/v1/policy/preview", json={"action_id": "block_ip", "incident_ref": "INC-TEST-R93"}
    ).json()
    assert "preview" in preview["constraints"]
    refused = client.post(
        "/api/v1/policy/approve", json={"verdict": preview, "approver": "operator"}
    )
    assert refused.status_code == 409
    assert "preview" in refused.json()["detail"]


def test_execution_is_audited_before_and_after() -> None:
    verdict = evaluate("restart_service", incident_ref="INC-TEST-0002")
    client.post(
        "/api/v1/actions/execute",
        json={"action_id": "restart_service", "verdict": verdict},
    )
    kinds = [r["kind"] for r in client.get(
        "/api/v1/audit", params={"incident_ref": "INC-TEST-0002"}
    ).json()]
    assert "execution_attempt" in kinds
    assert "execution_result" in kinds


def test_verification_grades_thresholds() -> None:
    body = client.post(
        "/api/v1/verification/observe",
        json={
            "action_id": "rollback_deployment",
            "observed": {"version": "previous", "error_rate": "0.2%"},
        },
    ).json()
    assert all(check["passed"] for check in body["checks"])


def test_missing_observation_fails_verification() -> None:
    """Absent telemetry means 'don't know', which must never grade as success."""
    body = client.post(
        "/api/v1/verification/observe",
        json={"action_id": "rollback_deployment", "observed": {"version": "previous"}},
    ).json()
    failed = [c for c in body["checks"] if not c["passed"]]
    assert [c["name"] for c in failed] == ["error_rate"]


@infrastructure_fixture
def test_demo_incident_is_available() -> None:
    """Looked up by id rather than by position: the store also holds incidents
    written by other tests, and ordering is by recency."""
    incidents = client.get("/api/v1/incidents").json()
    assert incidents, "expected at least the seeded demo incident"

    demo = next((i for i in incidents if i["id"] == "INC-2026-0810"), None)
    assert demo is not None, "the seeded demo incident should be present"
    assert demo["impact"]["estimated_users_affected"] == 1240
    assert demo["hypotheses"][0]["evidence"], "hypotheses must cite evidence"


@infrastructure_fixture
def test_incident_detail_keeps_plan_and_causal_chain() -> None:
    """The detail route once returned an incident with an empty plan and no
    causal chain, and rendered without complaint — an empty section looks like
    'nothing to show' rather than 'we lost it'."""
    incident = client.get("/api/v1/incidents/INC-2026-0810").json()
    assert incident["plan"], "plan must survive the round trip"
    assert incident["causal_chain"], "causal chain must survive the round trip"
    assert incident["transitions"], "timeline must survive the round trip"
    assert all(link["evidence"] for link in incident["causal_chain"])


def test_an_open_incident_colours_the_map() -> None:
    """Telemetry severity is windowed — the worst thing seen in fifteen minutes
    — which is right for a live system and wrong for an entity with an open
    critical incident and no new events. The map read "no data" for every host
    on the board while three incidents sat open.
    """
    from app.api.routes import _overlay_open_incidents
    from app.store import STORE

    incidents = STORE.all()
    if not incidents:
        pytest.skip("no incidents seeded in this configuration")

    keys = {e.key() for i in incidents for e in i.affected_entities}
    if not keys:
        pytest.skip("seeded incidents name no entities")

    snapshot = {"nodes": [{"key": key, "severity": None} for key in keys], "edges": []}
    _overlay_open_incidents(snapshot)

    assert all(node["severity"] is not None for node in snapshot["nodes"])


def test_the_overlay_never_downgrades_live_telemetry() -> None:
    """An entity reporting critical right now must not be softened because the
    incident against it is merely high."""
    from app.api.routes import _overlay_open_incidents
    from app.store import STORE

    incidents = STORE.all()
    if not incidents:
        pytest.skip("no incidents seeded in this configuration")
    key = next((e.key() for i in incidents for e in i.affected_entities), None)
    if key is None:
        pytest.skip("seeded incidents name no entities")

    snapshot = {"nodes": [{"key": key, "severity": "critical"}], "edges": []}
    _overlay_open_incidents(snapshot)
    assert snapshot["nodes"][0]["severity"] == "critical"


def test_the_committed_openapi_spec_is_current() -> None:
    """The spec is a published artefact, and it drifted.

    Phase 4 added eight routes — the whole chat and game surface — without
    regenerating it, and nothing noticed because nothing was looking. A stale
    spec is worse than none: it is a contract that describes a system that no
    longer exists, and the reader has no way to tell.

    Compared on paths rather than byte-for-byte, so that a FastAPI version bump
    reformatting a description does not fail the suite over nothing.
    """
    import json
    from pathlib import Path

    from app.main import app

    committed = Path(__file__).resolve().parents[1] / "openapi.json"
    if not committed.exists():
        pytest.skip("no committed spec in this checkout")

    stored = set(json.loads(committed.read_text(encoding="utf-8"))["paths"])
    live = set(app.openapi()["paths"])

    missing = sorted(live - stored)
    extra = sorted(stored - live)
    assert not missing, f"regenerate openapi.json — missing {missing}"
    assert not extra, f"regenerate openapi.json — removed routes still listed: {extra}"


def test_the_palette_index_carries_every_incident() -> None:
    """Read from `STORE.all()` rather than `STORE.incidents`.

    The in-memory dict is empty on a durable deployment, where incidents live in
    DynamoDB — so the index had zero incidents in production and every incident
    on a laptop, which is the shape of bug that passes local tests and ships.
    """
    listed = {incident["id"] for incident in client.get("/api/v1/incidents").json()}
    indexed = {
        item["label"]
        for item in client.get("/api/v1/search/index").json()["items"]
        if item["kind"] == "incident"
    }
    assert listed, "no incidents to index — this test would prove nothing"
    assert listed == indexed


def test_the_palette_index_stays_small() -> None:
    """It is fetched on the server for every page render and handed to every
    visitor. A per-record payload that grows silently is a page-weight
    regression nobody attributes to search."""
    items = client.get("/api/v1/search/index").json()["items"]
    assert all(set(item) <= {"kind", "label", "hint", "href"} for item in items)


# --- R71: a drafted detection rule --------------------------------------------
#
# These seed their own incident rather than reading whichever one the deployment
# happens to hold. The seeded infrastructure incident carries no ATT&CK mapping,
# so every one of these skipped against it — three clauses of R71 reporting green
# while measuring nothing, which is the failure this codebase keeps naming.


@pytest.fixture(scope="module")
def drafted() -> tuple[str, str]:
    """An incident with one technique and the events its step cites, stored."""
    from datetime import datetime, timedelta

    from app.graph import entitystore
    from app.store import STORE
    from pashupatastra.events import (
        EntityKind,
        EntityRef,
        Event,
        EventClass,
        Provenance,
        SecurityPayload,
        Severity,
    )
    from pashupatastra.incidents import (
        AttackTechnique,
        CausalLink,
        Hypothesis,
        Incident,
        IncidentSeverity,
    )

    now = datetime.now().astimezone()
    host = EntityRef(kind=EntityKind.HOST, id="ws-r71", name="ws-r71")
    event = Event(
        id="R71-a",
        event_class=EventClass.SECURITY,
        source="test",
        occurred_at=now - timedelta(minutes=5),
        observed_at=now - timedelta(minutes=5),
        entity_ref=host,
        severity=Severity.CRITICAL,
        payload=SecurityPayload(detection_type="new_smb_peer", principal="ws-r71", confidence=0.9),
        provenance=Provenance(source_system="test"),
        labels={"summary": "ws-r71 opened SMB to two hosts never contacted before"},
    )
    entitystore().save_events([event])
    incident = Incident(
        id="INC-2026-0971",
        severity=IncidentSeverity.CRITICAL,
        opened_at=now,
        affected_entities=[host],
        hypotheses=[Hypothesis(statement="Lateral movement.", confidence=0.9, evidence=["R71-a"])],
        causal_chain=[
            CausalLink(
                entity=host,
                transition="SMB opened to two hosts never previously contacted",
                evidence=["R71-a"],
                attack_technique=AttackTechnique(
                    id="T1021.002", name="SMB/Windows Admin Shares", tactic="Lateral Movement"
                ),
            )
        ],
    )
    STORE.save(incident)
    return incident.id, "T1021.002"


def test_the_incident_lists_what_could_be_drafted(drafted: tuple[str, str]) -> None:
    incident_id, technique_id = drafted
    body = client.get(f"/api/v1/incidents/{incident_id}/detection-rule").json()
    assert [t["id"] for t in body["techniques"]] == [technique_id]


def test_a_drafted_rule_parses_as_sigma_over_the_route(drafted: tuple[str, str]) -> None:
    """R71's first clause, checked on the shape a browser receives. The route
    reads its own output back rather than asserting it is valid, so `valid` is
    a measurement and this asserts the measurement came out clean."""
    incident_id, technique_id = drafted
    body = client.get(f"/api/v1/incidents/{incident_id}/detection-rule/{technique_id}").json()

    assert body["valid"] is True, body["problems"]
    assert body["problems"] == []
    assert body["status"] == "experimental"
    assert body["yaml"].lstrip().startswith("#")


def test_every_mapped_field_names_its_source_field_and_its_records(
    drafted: tuple[str, str],
) -> None:
    """R71's second clause. A Sigma field whose origin is unstated cannot be
    told apart from one the writer invented."""
    incident_id, technique_id = drafted
    body = client.get(f"/api/v1/incidents/{incident_id}/detection-rule/{technique_id}").json()

    assert body["mappings"], "a rule with no mapped field should not have been served"
    for mapping in body["mappings"]:
        assert mapping["source_field"], mapping["sigma_field"]
        assert mapping["refs"] == ["R71-a"], mapping["sigma_field"]


def test_the_uncertainty_is_inside_the_document_not_only_beside_it(
    drafted: tuple[str, str],
) -> None:
    """R71's third clause. The YAML is what gets copied into a detection
    repository; the JSON fields around it do not travel with it."""
    incident_id, technique_id = drafted
    body = client.get(f"/api/v1/incidents/{incident_id}/detection-rule/{technique_id}").json()
    text = body["yaml"]

    assert "DRAFT" in text
    assert "x-provenance" in text
    assert body["gaps"] and "x-gaps" in text
    assert body["behavioural"] is False
    assert "x-warning" in text and "WARNING" in text


def test_a_hostname_never_reaches_a_username_field_over_the_route(
    drafted: tuple[str, str],
) -> None:
    """The category error, checked where a reader would meet it. `principal` on
    this event is a hostname, and a rule carrying it as SubjectUserName parses,
    cites a real value and matches nothing."""
    incident_id, technique_id = drafted
    body = client.get(f"/api/v1/incidents/{incident_id}/detection-rule/{technique_id}").json()

    assert "SubjectUserName" not in {m["sigma_field"] for m in body["mappings"]}
    assert any(
        g["sigma_field"] == "SubjectUserName" and "not an account" in g["reason"]
        for g in body["not_mapped"]
    )


def test_a_technique_this_incident_does_not_carry_is_refused(drafted: tuple[str, str]) -> None:
    incident_id, _ = drafted
    response = client.get(f"/api/v1/incidents/{incident_id}/detection-rule/T9999")
    assert response.status_code == 422
    assert "T9999" in response.json()["detail"]


def test_an_unknown_incident_has_no_rules() -> None:
    assert client.get("/api/v1/incidents/INC-9999-9999/detection-rule").status_code == 404
    assert (
        client.get("/api/v1/incidents/INC-9999-9999/detection-rule/T1021.002").status_code == 404
    )


# --- R72: what acting earlier would have prevented -----------------------------
#
# Seeds its own incident for the reason the R71 tests do: the counterfactual
# needs a chain with more than one timed step and an access edge between them,
# and no seeded incident is guaranteed to have both.


@pytest.fixture(scope="module")
def gap() -> tuple[str, str, str]:
    """An incident whose chain runs flow -> host over ninety minutes, with the
    edge that makes the second step depend on the first."""
    from datetime import datetime, timedelta

    from app.api.routes import GRAPH
    from app.graph import entitystore
    from app.store import STORE
    from pashupatastra import Edge, Node
    from pashupatastra.events import (
        EntityKind,
        EntityRef,
        Event,
        EventClass,
        Provenance,
        SecurityPayload,
        Severity,
    )
    from pashupatastra.incidents import (
        CausalLink,
        Hypothesis,
        Incident,
        IncidentSeverity,
    )

    now = datetime.now().astimezone()
    flow = EntityRef(
        kind=EntityKind.NETWORK_FLOW, id="ws-r72->198.51.100.9:8443", name="beacon-r72"
    )
    host = EntityRef(kind=EntityKind.HOST, id="ws-r72", name="ws-r72")

    def event(event_id: str, entity: EntityRef, minutes: int) -> Event:
        return Event(
            id=event_id,
            event_class=EventClass.SECURITY,
            source="test",
            occurred_at=now - timedelta(minutes=minutes),
            observed_at=now - timedelta(minutes=minutes),
            entity_ref=entity,
            severity=Severity.CRITICAL,
            payload=SecurityPayload(detection_type="rare_destination", confidence=0.9),
            provenance=Provenance(source_system="test"),
        )

    entitystore().save_events([event("R72-a", flow, 120), event("R72-b", host, 30)])
    GRAPH.upsert_nodes([Node(ref=flow), Node(ref=host)])
    # The host depends on the flow: cutting the flow reaches the host.
    GRAPH.upsert_edges(
        [Edge(source=host.key(), target=flow.key(), kind="controlled_over", evidence=["R72-a"])]
    )

    incident = Incident(
        id="INC-2026-0972",
        severity=IncidentSeverity.CRITICAL,
        opened_at=now,
        affected_entities=[host],
        hypotheses=[Hypothesis(statement="Beaconing.", confidence=0.9, evidence=["R72-a"])],
        causal_chain=[
            CausalLink(entity=flow, transition="outbound to a rare destination",
                       evidence=["R72-a"]),
            CausalLink(entity=host, transition="SMB to two new hosts", evidence=["R72-b"]),
        ],
    )
    STORE.save(incident)
    return incident.id, flow.key(), host.key()


def test_the_timeline_places_each_step_and_offers_what_can_be_asked(
    gap: tuple[str, str, str],
) -> None:
    incident_id, flow, host = gap
    body = client.get(f"/api/v1/incidents/{incident_id}/timeline").json()

    assert [s["entity_key"] for s in body["steps"]] == [flow, host]
    assert body["askable"] == sorted([flow, host])
    assert all(s["refs"] for s in body["steps"])


def test_acting_early_reports_an_estimate_derived_from_the_records(
    gap: tuple[str, str, str],
) -> None:
    """R72's first two clauses over the route: derived from stored timeline and
    graph, and presented as an estimate with its basis stated."""
    incident_id, flow, host = gap
    timeline = client.get(f"/api/v1/incidents/{incident_id}/timeline").json()
    at = timeline["steps"][0]["at"]

    body = client.get(
        f"/api/v1/incidents/{incident_id}/counterfactual",
        params={"entity_key": flow, "at": at},
    ).json()

    assert body["summary"].startswith("Estimate.")
    assert [s["entity_key"] for s in body["prevented"]] == [host]
    assert body["avoided_entities"] == [host]
    assert body["refs"] == ["R72-b"]
    assert body["gap_seconds"] > 0
    joined = " ".join(body["basis"])
    assert "immediate and complete" in joined
    assert "another route" in joined


def test_acting_before_the_first_record_is_refused(gap: tuple[str, str, str]) -> None:
    """R72's third clause. The question asks what we would have done knowing
    something nothing had yet observed, and answering it measures clairvoyance
    rather than response time."""
    from datetime import datetime, timedelta

    incident_id, flow, _ = gap
    timeline = client.get(f"/api/v1/incidents/{incident_id}/timeline").json()
    too_early = (
        datetime.fromisoformat(timeline["steps"][0]["at"]) - timedelta(hours=1)
    ).isoformat()

    response = client.get(
        f"/api/v1/incidents/{incident_id}/counterfactual",
        params={"entity_key": flow, "at": too_early},
    )
    assert response.status_code == 422
    assert "clairvoyance" in response.json()["detail"]


def test_an_entity_the_incident_never_recorded_is_refused(gap: tuple[str, str, str]) -> None:
    incident_id, _, _ = gap
    timeline = client.get(f"/api/v1/incidents/{incident_id}/timeline").json()
    response = client.get(
        f"/api/v1/incidents/{incident_id}/counterfactual",
        params={"entity_key": "host:not-in-this-incident", "at": timeline["steps"][0]["at"]},
    )
    assert response.status_code == 422
    assert "not on" in response.json()["detail"]


def test_a_malformed_moment_is_refused_rather_than_guessed(gap: tuple[str, str, str]) -> None:
    incident_id, flow, _ = gap
    response = client.get(
        f"/api/v1/incidents/{incident_id}/counterfactual",
        params={"entity_key": flow, "at": "yesterday afternoon"},
    )
    assert response.status_code == 422


def test_acting_last_prevents_nothing_and_says_so(gap: tuple[str, str, str]) -> None:
    incident_id, flow, _ = gap
    from datetime import datetime, timedelta

    timeline = client.get(f"/api/v1/incidents/{incident_id}/timeline").json()
    late = (datetime.fromisoformat(timeline["steps"][-1]["at"]) + timedelta(minutes=5)).isoformat()

    body = client.get(
        f"/api/v1/incidents/{incident_id}/counterfactual",
        params={"entity_key": flow, "at": late},
    ).json()
    assert body["prevented"] == []
    assert body["gap_seconds"] == 0
    assert "prevented nothing" in body["summary"]


def test_an_unknown_incident_has_no_timeline() -> None:
    assert client.get("/api/v1/incidents/INC-9999-9999/timeline").status_code == 404


# --- R73: argue the other side -------------------------------------------------
#
# Both verdicts are seeded. The demo incidents all rule their alternative out, so
# the case that matters most — the one where it does not get ruled out — would
# otherwise never be exercised; and the fallback infrastructure incident cites
# events that were never stored, so it refuses. A skip here would report three
# clauses of R73 green while measuring none of them.


@pytest.fixture(scope="module")
def contested() -> tuple[str, str, str]:
    """One incident whose alternative is beaten, one whose is not, one with no
    alternative at all."""
    from datetime import datetime, timedelta

    from app.graph import entitystore
    from app.store import STORE
    from pashupatastra.events import (
        EntityKind,
        EntityRef,
        Event,
        EventClass,
        Provenance,
        SecurityPayload,
        Severity,
    )
    from pashupatastra.incidents import (
        CausalLink,
        Hypothesis,
        Incident,
        IncidentSeverity,
    )

    now = datetime.now().astimezone()
    host = EntityRef(kind=EntityKind.HOST, id="ws-r73", name="ws-r73")

    entitystore().save_events(
        [
            Event(
                id=ref,
                event_class=EventClass.SECURITY,
                source="test",
                occurred_at=now - timedelta(minutes=10),
                observed_at=now - timedelta(minutes=10),
                entity_ref=host,
                severity=Severity.WARNING,
                payload=SecurityPayload(detection_type="regular_interval", confidence=0.8),
                provenance=Provenance(source_system="test"),
            )
            for ref in ("R73-a", "R73-b", "R73-c")
        ]
    )

    def incident(incident_id: str, hypotheses: list[Hypothesis]) -> str:
        STORE.save(
            Incident(
                id=incident_id,
                severity=IncidentSeverity.HIGH,
                opened_at=now,
                affected_entities=[host],
                hypotheses=hypotheses,
                causal_chain=[
                    CausalLink(entity=host, transition="beaconed", evidence=["R73-a"])
                ],
            )
        )
        return incident_id

    upheld = incident(
        "INC-2026-0975",
        [
            Hypothesis(statement="Implant beaconing.", confidence=0.9,
                       evidence=["R73-a", "R73-b"]),
            Hypothesis(statement="A backup agent on its schedule.", confidence=0.05,
                       evidence=["R73-b"], contradicted_by=["R73-c"]),
        ],
    )
    unrefuted = incident(
        "INC-2026-0973",
        [
            Hypothesis(statement="Implant beaconing.", confidence=0.9,
                       evidence=["R73-a", "R73-b"]),
            # Ranked far below and contradicted by nothing stored.
            Hypothesis(statement="A backup agent on its schedule.", confidence=0.05,
                       evidence=["R73-b"]),
        ],
    )
    alone = incident(
        "INC-2026-0974",
        [Hypothesis(statement="Only one reading.", confidence=0.9, evidence=["R73-a"])],
    )
    return upheld, unrefuted, alone


def _contest(incident_id: str):
    return client.get(f"/api/v1/incidents/{incident_id}/contest")


def test_the_rival_is_argued_and_the_rejection_cites_records(
    contested: tuple[str, str, str],
) -> None:
    """R73's first two clauses over the route: a real competing hypothesis, and
    a rejection that names the record answering it."""
    upheld, _, _ = contested
    body = _contest(upheld).json()

    assert body["verdict"] == "upheld"
    assert body["argument"].startswith("The case for the alternative")
    assert body["shared"] == ["R73-b"], "the two explain none of the same observations"
    assert body["ruled_out_by"] == ["R73-c"]
    assert body["rival"]["supported_by"] == ["R73-b"]


def test_the_alternative_can_win_over_the_route(contested: tuple[str, str, str]) -> None:
    """R73's third clause. The same two statements as the case above, differing
    only in whether anything stored contradicts the rival."""
    _, unrefuted, _ = contested
    body = _contest(unrefuted).json()

    assert body["verdict"] == "unrefuted"
    assert body["ruled_out_by"] == []
    assert "Nothing stored rules it out" in body["argument"]
    assert "ranked below" in body["argument"]


def test_a_confidence_gap_alone_never_upholds_the_diagnosis(
    contested: tuple[str, str, str],
) -> None:
    """The property the module turns on, where a reader meets it: 0.90 against
    0.05 and the verdict is still that the rival stands."""
    _, unrefuted, _ = contested
    body = _contest(unrefuted).json()

    assert body["leader"]["confidence"] > body["rival"]["confidence"] * 10
    assert body["verdict"] == "unrefuted"


def test_an_incident_with_no_rival_is_refused_rather_than_given_one(
    contested: tuple[str, str, str],
) -> None:
    """Manufacturing a contest to avoid an empty panel is the rigour-shaped
    version of having none."""
    _, _, alone = contested
    response = _contest(alone)
    assert response.status_code == 422
    assert "no other side" in response.json()["detail"]


def test_the_demo_incidents_all_argue_a_rival_that_loses() -> None:
    """The rubric's own claim, checked against the scenarios the Blue Team game
    is played on: each has an explanation that is plausible and wrong, and
    something stored rules it out."""
    seen = 0
    for incident in client.get("/api/v1/incidents").json():
        response = _contest(incident["id"])
        if response.status_code != 200:
            continue
        body = response.json()
        if not body["incident_ref"].startswith("INC-2026-090"):
            continue
        seen += 1
        assert body["verdict"] == "upheld", body["incident_ref"]
        assert body["ruled_out_by"], body["incident_ref"]
    if seen == 0:
        pytest.skip("the security scenarios are not seeded in this configuration")


def test_an_unknown_incident_has_no_contest() -> None:
    assert _contest("INC-9999-9999").status_code == 404
