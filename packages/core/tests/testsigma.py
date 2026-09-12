"""R71: a drafted rule parses, names where every field came from, and states
what it could not fill.

The tests that carry the weight are the ones about what is *not* emitted. Any
implementation produces a plausible Sigma rule; the ones worth having refuse to
put a hostname in a username field, refuse to emit a rule with no mappable
field, and say in the document itself that a rule keyed on one host is not a
detection for the technique.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import yaml

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
from pashupatastra.sigma import (
    TECHNIQUE_FIELDS,
    DetectionRule,
    Gap,
    Mapping,
    SigmaError,
    draft_rule,
    rule_techniques,
    validate,
)

NOW = datetime(2026, 8, 25, 12, 0).astimezone()

SMB = AttackTechnique(id="T1021.002", name="SMB/Windows Admin Shares", tactic="Lateral Movement")
C2 = AttackTechnique(id="T1071.001", name="Web Protocols", tactic="Command and Control")
TASK = AttackTechnique(id="T1053.005", name="Scheduled Task", tactic="Persistence")


def _ref(kind: EntityKind, id: str) -> EntityRef:
    return EntityRef(kind=kind, id=id, name=id)


def an_event(
    event_id: str,
    entity: EntityRef,
    detection: str = "new_smb_peer",
    principal: str | None = None,
    source_address: str | None = None,
    summary: str | None = None,
) -> Event:
    return Event(
        id=event_id,
        event_class=EventClass.SECURITY,
        source="demo",
        occurred_at=NOW - timedelta(minutes=5),
        observed_at=NOW - timedelta(minutes=5),
        entity_ref=entity,
        severity=Severity.CRITICAL,
        payload=SecurityPayload(
            detection_type=detection,
            principal=principal if principal is not None else entity.id,
            source_address=source_address,
            confidence=0.9,
        ),
        provenance=Provenance(source_system="test"),
        labels={"summary": summary} if summary else {},
    )


def an_incident(chain: list[CausalLink] | None = None) -> Incident:
    host = _ref(EntityKind.HOST, "ws-0148")
    return Incident(
        id="INC-2026-0903",
        severity=IncidentSeverity.CRITICAL,
        opened_at=NOW,
        affected_entities=[host],
        hypotheses=[
            Hypothesis(statement="Lateral movement.", confidence=0.9, evidence=["SEC-a"])
        ],
        causal_chain=chain
        if chain is not None
        else [
            CausalLink(
                entity=host,
                transition="SMB opened to two hosts never previously contacted",
                evidence=["SEC-a"],
                attack_technique=SMB,
            )
        ],
    )


# --- the citation rule, enforced where it cannot be forgotten -----------------


def test_a_mapping_that_cites_nothing_cannot_be_built() -> None:
    with pytest.raises(SigmaError, match="cites nothing"):
        Mapping(sigma_field="ShareName", source_field="entity_ref.id", value="ADMIN$", refs=())


def test_a_mapping_that_names_no_source_field_cannot_be_built() -> None:
    """The clause R71 is measured on. A Sigma field whose origin is unstated is
    indistinguishable from one the writer made up."""
    with pytest.raises(SigmaError, match="names no source field"):
        Mapping(sigma_field="ShareName", source_field="  ", value="ADMIN$", refs=("SEC-a",))


def test_a_gap_with_no_reason_cannot_be_built() -> None:
    with pytest.raises(SigmaError, match="states no reason"):
        Gap(sigma_field="ShareName", reason="")


def test_every_field_of_a_drafted_rule_names_its_source_and_its_records() -> None:
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    assert rule.mappings
    for mapping in rule.mappings:
        assert mapping.source_field, mapping.sigma_field
        assert mapping.refs, mapping.sigma_field
        assert set(mapping.refs) <= {"SEC-a"}


# --- what is refused ----------------------------------------------------------


def test_a_hostname_is_never_mapped_into_a_username_field() -> None:
    """The category error this module is most likely to make. `principal` on a
    host-scoped detection holds a hostname, and a rule with a hostname in
    SubjectUserName parses, cites a real value, and matches nothing."""
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host, principal="ws-0148")], "T1021.002")

    assert "SubjectUserName" not in {m.sigma_field for m in rule.mappings}
    refusal = [g for g in rule.unmapped if g.sigma_field == "SubjectUserName"]
    assert refusal, "the refusal is not reported, so it reads as an oversight"
    assert "not an account" in refusal[0].reason


def test_an_account_scoped_event_does_map_its_principal() -> None:
    """The other half of the same rule — the mapping is typed, not banned."""
    account = _ref(EntityKind.ACCOUNT, "j.rivera")
    chain = [
        CausalLink(
            entity=account,
            transition="signed in from a new ASN",
            evidence=["SEC-a"],
            attack_technique=SMB,
        )
    ]
    rule = draft_rule(an_incident(chain), [an_event("SEC-a", account, principal="j.rivera")], None)
    assert "SubjectUserName" in {m.sigma_field for m in rule.mappings}


def test_a_step_whose_evidence_maps_to_nothing_is_refused_not_invented() -> None:
    """An asset-scoped event carries no field Sigma has a name for. Emitting a
    rule anyway means inventing one, so this raises instead."""
    asset = _ref(EntityKind.ASSET, "sso-portal")
    chain = [
        CausalLink(
            entity=asset,
            transition="session issued",
            evidence=["SEC-a"],
            attack_technique=SMB,
        )
    ]
    with pytest.raises(SigmaError, match="maps to Sigma"):
        draft_rule(an_incident(chain), [an_event("SEC-a", asset)], None)


def test_prose_is_never_parsed_into_fields() -> None:
    """`labels.summary` names the hosts a stronger rule would key on, in a
    sentence. Reading them out of it would make the rule depend on grammar."""
    host = _ref(EntityKind.HOST, "ws-0148")
    event = an_event("SEC-a", host, summary="ws-0148 opened SMB to fs-02 and app-07")
    rule = draft_rule(an_incident(), [event], "T1021.002")

    values = " ".join(str(m.value) for m in rule.mappings)
    assert "fs-02" not in values and "app-07" not in values
    assert any(g.sigma_field == "(prose)" for g in rule.unmapped)


def test_our_own_detector_label_is_not_offered_as_a_log_field() -> None:
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host, detection="new_smb_peer")], "T1021.002")
    values = " ".join(str(m.value) for m in rule.mappings)
    assert "new_smb_peer" not in values
    assert any("detector label" in g.reason for g in rule.unmapped)


def test_an_incident_with_no_attack_technique_gets_no_rule() -> None:
    """The infrastructure domain has no ATT&CK mapping, and inventing one to
    fill the field would be worse than having none."""
    host = _ref(EntityKind.HOST, "ws-0148")
    chain = [CausalLink(entity=host, transition="pool saturated", evidence=["SEC-a"])]
    with pytest.raises(SigmaError, match="no causal step carrying an attack technique"):
        draft_rule(an_incident(chain), [an_event("SEC-a", host)], None)


def test_a_rule_cannot_be_built_with_no_mappings() -> None:
    with pytest.raises(SigmaError, match="no telemetry field could be mapped"):
        DetectionRule(
            incident_ref="INC-2026-0903",
            title="Draft",
            description="",
            logsource={"category": "security"},
            mappings=(),
        )


def test_a_rule_drafted_from_events_that_were_not_supplied_is_refused() -> None:
    """Otherwise the rule cites ids it never read — the citation failure this
    codebase treats as worse than no citation."""
    other = _ref(EntityKind.HOST, "other")
    with pytest.raises(SigmaError, match="none of which is among the events supplied"):
        draft_rule(an_incident(), [an_event("SEC-unrelated", other)], "T1021.002")


def test_an_unknown_technique_is_refused_and_says_what_is_available() -> None:
    with pytest.raises(SigmaError, match="T9999"):
        draft_rule(an_incident(), [an_event("SEC-a", _ref(EntityKind.HOST, "ws-0148"))], "T9999")


# --- uncertainty is in the document -------------------------------------------


def test_the_gaps_are_emitted_into_the_rule_and_not_only_beside_it() -> None:
    """A YAML file is copied into a detection repository; the panel that
    explained its limitations does not travel with it."""
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    document = yaml.safe_load(rule.to_yaml(date="2026/08/25"))

    assert document["x-gaps"], "the rule does not carry what it could not fill"
    for wanted in TECHNIQUE_FIELDS["T1021.002"]:
        if wanted not in {m.sigma_field for m in rule.mappings}:
            assert wanted in document["x-gaps"]


def test_the_provenance_table_is_in_the_document() -> None:
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    document = yaml.safe_load(rule.to_yaml(date="2026/08/25"))

    for mapping in rule.mappings:
        entry = document["x-provenance"][mapping.sigma_field]
        assert entry["source_field"] == mapping.source_field
        assert entry["observed_in"] == list(mapping.refs)


def test_an_indicator_match_says_so_in_the_rule() -> None:
    """A rule keyed only on this incident's hostname would have caught this
    incident and will never catch another."""
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    assert rule.behavioural is False

    text = rule.to_yaml(date="2026/08/25")
    assert "x-warning" in yaml.safe_load(text)
    assert "WARNING" in text, "a reviewer reading the header sees no caveat"


def test_a_behavioural_field_is_recognised_as_one() -> None:
    """A process name is the behaviour; a hostname is the incident. Without the
    distinction every rule looks equally good."""
    process = _ref(EntityKind.PROCESS, "app-07/schtasks")
    chain = [
        CausalLink(
            entity=process,
            transition="scheduled task created remotely",
            evidence=["SEC-a"],
            attack_technique=TASK,
        )
    ]
    rule = draft_rule(an_incident(chain), [an_event("SEC-a", process)], "T1053.005")
    assert rule.behavioural is True
    assert "x-warning" not in yaml.safe_load(rule.to_yaml(date="2026/08/25"))


def test_gaps_are_not_reported_as_false_positives() -> None:
    """Two different Sigma keys with two different meanings. A missing field in
    `falsepositives` misreports both to every tool that reads the document."""
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    document = yaml.safe_load(rule.to_yaml(date="2026/08/25"))

    joined = " ".join(document["falsepositives"])
    assert "inventing the value" not in joined
    assert "INC-2026-0903" in joined, "the real false positive is not stated"


def test_a_draft_never_claims_a_deployable_status() -> None:
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    assert rule.status == "experimental"
    assert yaml.safe_load(rule.to_yaml())["status"] == "experimental"
    assert rule.title.lower().startswith("draft")
    with pytest.raises(AttributeError):
        rule.status = "stable"  # type: ignore[misc]


# --- it parses as Sigma --------------------------------------------------------


def test_the_emitted_rule_passes_validation() -> None:
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    assert validate(rule.to_yaml(date="2026/08/25")) == []


def test_the_rule_id_is_stable_across_drafts() -> None:
    """Two reviewers comparing drafts of the same rule should see one rule, not
    two. A uuid4 would make every re-issue look like a new detection."""
    host = _ref(EntityKind.HOST, "ws-0148")
    first = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    second = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    assert first.rule_id == second.rule_id
    assert first.to_yaml(date="x") == second.to_yaml(date="x")


def test_a_port_is_emitted_as_a_number() -> None:
    """Quoted, it silently fails to match an integer field in half the backends
    Sigma compiles to — which looks like the rule simply never firing."""
    flow = _ref(EntityKind.NETWORK_FLOW, "ws-0148->198.51.100.74:8443")
    chain = [
        CausalLink(
            entity=flow, transition="beaconing", evidence=["SEC-a"], attack_technique=C2
        )
    ]
    rule = draft_rule(an_incident(chain), [an_event("SEC-a", flow)], "T1071.001")
    selection = yaml.safe_load(rule.to_yaml())["detection"]["selection"]
    assert selection["DestinationPort"] == 8443
    assert selection["DestinationIp"] == "198.51.100.74"


def test_a_flow_key_is_parsed_into_its_parts() -> None:
    flow = _ref(EntityKind.NETWORK_FLOW, "ws-0148->198.51.100.74:8443")
    chain = [
        CausalLink(
            entity=flow, transition="beaconing", evidence=["SEC-a"], attack_technique=C2
        )
    ]
    rule = draft_rule(an_incident(chain), [an_event("SEC-a", flow)], "T1071.001")
    fields = {m.sigma_field: m.value for m in rule.mappings}
    assert fields["SourceHostname"] == "ws-0148"
    assert fields["DestinationIp"] == "198.51.100.74"
    for mapping in rule.mappings:
        assert mapping.source_field == "entity_ref.id"


def test_the_emitted_header_is_ascii() -> None:
    """The header travels into detection repositories, CI logs and terminals
    whose encoding we do not choose."""
    host = _ref(EntityKind.HOST, "ws-0148")
    rule = draft_rule(an_incident(), [an_event("SEC-a", host)], "T1021.002")
    header = rule.to_yaml(date="2026/08/25").split("\n\n", 1)[0]
    header.encode("ascii")


# --- the validator itself ------------------------------------------------------


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("title: x\nlogsource: {category: a}\n", "detection is required"),
        ("title: x\ndetection: {selection: {A: 1}, condition: selection}\n", "logsource is required"),
        (
            "title: ''\nlogsource: {category: a}\ndetection: {selection: {A: 1}, condition: selection}\n",
            "title is required",
        ),
        (
            "title: x\nlogsource: {category: a}\ndetection: {selection: {A: 1}, condition: missing}\n",
            "not defined",
        ),
        (
            "title: x\nlogsource: {category: a}\ndetection: {condition: selection}\n",
            "no selection",
        ),
        (
            "title: x\nlogsource: {category: a}\ndetection: {selection: {}, condition: selection}\n",
            "matches everything",
        ),
        (
            (
                "title: x\nlevel: catastrophic\nlogsource: {category: a}\n"
                "detection: {selection: {A: 1}, condition: selection}\n"
            ),
            "level",
        ),
        (
            (
                "title: x\nid: not-a-uuid\nlogsource: {category: a}\n"
                "detection: {selection: {A: 1}, condition: selection}\n"
            ),
            "not a UUID",
        ),
    ],
)
def test_the_validator_catches_a_broken_rule(document: str, expected: str) -> None:
    problems = validate(document)
    assert any(expected in problem for problem in problems), problems


def test_the_validator_rejects_something_that_is_not_a_rule() -> None:
    assert validate("- just\n- a list\n") == ["a Sigma rule is a YAML mapping at the top level"]
    assert "not parseable as YAML" in validate("title: [unclosed\n")[0]


def test_techniques_lists_what_could_be_drafted() -> None:
    host = _ref(EntityKind.HOST, "ws-0148")
    chain = [
        CausalLink(entity=host, transition="a", evidence=["SEC-a"], attack_technique=C2),
        CausalLink(entity=host, transition="b", evidence=["SEC-b"], attack_technique=SMB),
        CausalLink(entity=host, transition="c", evidence=["SEC-c"]),
    ]
    assert [t.id for t in rule_techniques(an_incident(chain))] == ["T1071.001", "T1021.002"]


# --- the reference parser ------------------------------------------------------


def test_the_reference_sigma_parser_accepts_what_we_emit() -> None:
    """R71's first clause, checked by somebody else's parser.

    `validate` above is our own reading of the specification, which makes it the
    same author marking their own work — it would pass a rule that is wrong in
    exactly the way we misread the spec. pySigma is the reference implementation
    the detection ecosystem actually uses, so this is the check that can fail in
    a way our own cannot.

    It also pins the custom keys. `x-provenance` and `x-gaps` carry the whole
    reviewability argument, and a parser rejecting them would mean the rule that
    reaches a detection repository is one with its caveats stripped.
    """
    pysigma = pytest.importorskip("sigma.rule", reason="pysigma is a dev dependency")

    host = _ref(EntityKind.HOST, "ws-0148")
    process = _ref(EntityKind.PROCESS, "app-07/schtasks")
    flow = _ref(EntityKind.NETWORK_FLOW, "ws-0148->198.51.100.74:8443")

    cases = [
        (SMB, host, "T1021.002"),
        (TASK, process, "T1053.005"),
        (C2, flow, "T1071.001"),
    ]
    for technique, entity, technique_id in cases:
        chain = [
            CausalLink(
                entity=entity,
                transition="observed",
                evidence=["SEC-a"],
                attack_technique=technique,
            )
        ]
        rule = draft_rule(an_incident(chain), [an_event("SEC-a", entity)], technique_id)
        text = rule.to_yaml(date="2026/08/25")

        parsed = pysigma.SigmaRule.from_yaml(text)
        assert parsed.errors == [], (technique_id, parsed.errors)
        assert parsed.title == rule.title
        assert yaml.safe_load(text)["x-provenance"], technique_id
