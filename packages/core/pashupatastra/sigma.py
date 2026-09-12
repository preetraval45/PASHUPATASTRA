"""A detection rule drafted from an incident's own telemetry, and an honest
account of what its telemetry could not supply.

The task is a translation between two vocabularies. Our normalized event model
(`events.py`) and Sigma's field taxonomy describe the same world in different
words, and the interesting engineering is not the half that translates — it is
the half that does not.

**A rule that reads well and matches nothing is the failure mode.** A model asked
for a Sigma rule for SMB lateral movement will produce `EventID: 5145` and
`ShareName: '\\\\*\\ADMIN$'` because that is what such rules look like, and every
line of it will be fabricated: no event in this store carries a Windows event id
or a share name. It would parse, review well, deploy, and never fire. So every
field in the emitted rule is derived from a stored value and cites the event it
was read from, and every field this technique would normally rest on and our
telemetry cannot fill is emitted **into the rule** as a gap.

**Uncertainty travels in the artefact, not beside it.** A YAML file is written to
be copied out of a browser and pasted into a detection repository, and the panel
that carefully explained its limitations does not make that journey. So the gaps,
the provenance table and the experimental status are all inside the document.
This is R70's argument about the word "draft" appearing three times, applied to
the thing R70's argument implies.

**Mapping is typed, because the plausible mistake is a category error.** In this
store `SecurityPayload.principal` is set to the subject of the detection, which
for a host-scoped detection is a hostname. Mapping it to Sigma's `User` would
produce a rule that parses, cites a real stored value, and is wrong in a way no
reviewer would catch — a hostname sitting in a username field. `principal` is
mapped to an identity field only where the entity it describes is an account.

**An indicator match is not a behavioural detection**, and the difference is
recorded per field. A rule keyed on `ws-0148` and `198.51.100.74` would have
caught this incident and will never catch another, because those values are this
incident. Fields carrying an instance value are marked as not generalising, and
a rule with no generalising field says so rather than presenting itself as a
detection for the technique.

No model participates in anything here. What Sati contributes is the decision to
ask and the prose around the answer; the rule, its fields, its citations and its
gaps are computed from stored records — rule 1, the same way `relations.py`
keeps the relation judgement out of the model's hands.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

import yaml

from .events import EntityKind, Event
from .incidents import AttackTechnique, Incident

SIGMA_NAMESPACE = uuid.UUID("6f0b4c5e-7a1d-5f2b-9c3e-8d4a1b6f2c70")
"""Fixed namespace for deterministic rule ids.

A random uuid4 would give the same incident a different rule id on every
request, so two reviewers comparing drafts could not tell a re-issue from a new
rule. uuid5 over the incident and technique is stable and carries no clock.
"""

STATUS = "experimental"
"""Never `stable`, never `test`. Sigma's `status` is how a detection repository
decides what to deploy, and a rule assembled from one incident's telemetry by a
console that has never seen this customer's log pipeline has not earned either.
"""

LEVELS = ("informational", "low", "medium", "high", "critical")
STATUSES = ("stable", "test", "experimental", "deprecated", "unsupported")

_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_FLOW = re.compile(r"^(?P<source>[^>]+)->(?P<destination>[^:]+):(?P<port>\d+)$")


class SigmaError(ValueError):
    """A rule that would misrepresent what the telemetry supports."""


# --- what a technique's detection normally rests on ---------------------------
#
# A static table, written by hand, and deliberately small. It is the one place
# here that makes a claim about the world rather than about our store, so it is
# stated as "fields a published rule for this technique commonly keys on" and
# nothing stronger. Its only job is to make the gap list specific: "we cannot
# fill ShareName" is useful, "our telemetry is incomplete" is not.
#
# A technique absent from this table gets no invented expectations. The rule is
# still emitted and the gap list is simply shorter, which is the honest outcome
# — a missing table entry is our ignorance, and dressing it up as the technique
# having no requirements would be the fabrication this module exists to avoid.

TECHNIQUE_FIELDS: dict[str, tuple[str, ...]] = {
    # T1021.002 — SMB/Windows Admin Shares. Windows Security 5140/5145.
    "T1021.002": ("EventID", "ShareName", "RelativeTargetName", "SubjectUserName", "IpAddress"),
    # T1071.001 — Web Protocols (C2 over HTTP/S).
    "T1071.001": ("DestinationIp", "DestinationPort", "Image", "User"),
    # T1053.005 — Scheduled Task.
    "T1053.005": ("EventID", "TaskName", "SubjectUserName", "Image", "CommandLine"),
    # T1110.004 — Credential Stuffing.
    "T1110.004": ("EventID", "TargetUserName", "IpAddress", "LogonType"),
}


@dataclass(frozen=True)
class Mapping:
    """One Sigma field, the telemetry field it was read from, and the records
    that carried it.

    `refs` is required and non-empty, for the reason `drafts.Line` requires it:
    a field whose origin nobody can trace is the thing this module exists not to
    emit, and enforcing it at construction binds the next author too.
    """

    sigma_field: str
    source_field: str
    """Dotted path into our own event model — `entity_ref.id`,
    `payload.source_address`. Not a description: a reader checking this rule
    needs the field, so they can go and look at whether it carries what we say."""

    value: str
    refs: tuple[str, ...]

    generalises: bool = False
    """Whether this field would match a future occurrence of the technique.

    A hostname and a destination address are this incident, not the behaviour,
    and a rule made only of them is an indicator list wearing a rule's shape.
    """

    def __post_init__(self) -> None:
        if not self.sigma_field.strip():
            raise SigmaError("a mapping with no Sigma field is not a mapping")
        if not self.source_field.strip():
            raise SigmaError(
                f"{self.sigma_field} names no source field; a Sigma field whose "
                "origin is not stated is indistinguishable from an invented one"
            )
        if not str(self.value).strip():
            raise SigmaError(f"{self.sigma_field} has no value to match on")
        if not self.refs:
            raise SigmaError(
                f"{self.sigma_field} cites nothing; every field in a drafted rule "
                "names the event it was read from"
            )

    def describe(self) -> str:
        # ASCII deliberately. This line is emitted into the rule's comment
        # header, and the header travels into detection repositories, CI logs
        # and terminals whose encoding we do not choose. An arrow that renders
        # as a mojibake question mark in half of them is not worth the typography.
        scope = "matches this incident only" if not self.generalises else "generalises"
        return f"{self.sigma_field} <- {self.source_field} ({scope}); {', '.join(self.refs)}"


@dataclass(frozen=True)
class Gap:
    """A field this rule would be stronger for and the telemetry cannot fill.

    The reason is a statement about our store — what is and is not recorded —
    rather than about Sigma. "No stored event records which share was opened" is
    checkable by reading the events; "the telemetry is incomplete" is not.
    """

    sigma_field: str
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise SigmaError(
                f"gap {self.sigma_field!r} states no reason; a gap without one is "
                "a shrug, and a reader cannot tell it from an oversight"
            )


@dataclass(frozen=True)
class DetectionRule:
    """A drafted Sigma rule, everything it rests on, and everything it lacks."""

    incident_ref: str
    title: str
    description: str
    logsource: dict[str, str]
    mappings: tuple[Mapping, ...]
    gaps: tuple[Gap, ...] = ()
    technique: AttackTechnique | None = None
    level: str = "medium"
    evidence_refs: tuple[str, ...] = ()
    unmapped: tuple[Gap, ...] = field(default_factory=tuple)
    """Telemetry we hold and deliberately did not map, with the reason.

    Separate from `gaps`, which is what we do not hold. The distinction matters
    to a reader deciding whether to improve the pipeline or the rule: one is a
    collection problem, the other is a translation we refused to make.
    """

    def __post_init__(self) -> None:
        if not self.mappings:
            raise SigmaError(
                f"{self.incident_ref}: no telemetry field could be mapped to a Sigma "
                "field, so there is no rule to draft. An empty detection matches "
                "everything or nothing and both are worse than saying so."
            )
        if self.level not in LEVELS:
            raise SigmaError(f"level {self.level!r} is not one of {LEVELS}")

    @property
    def status(self) -> str:
        """A property, not a field — R70's argument. A status that can be
        assigned is one that eventually is, and nothing drafted here has earned
        anything above experimental."""
        return STATUS

    @property
    def rule_id(self) -> str:
        seed = f"{self.incident_ref}:{self.technique.id if self.technique else 'none'}"
        return str(uuid.uuid5(SIGMA_NAMESPACE, seed))

    @property
    def behavioural(self) -> bool:
        """Whether anything here would match a future occurrence.

        False means every field is an instance value, which makes this an
        indicator match. Reported rather than hidden: it is the difference
        between a rule and a list of things that already happened.
        """
        return any(mapping.generalises for mapping in self.mappings)

    @property
    def refs(self) -> list[str]:
        seen: list[str] = []
        for mapping in self.mappings:
            for ref in mapping.refs:
                if ref not in seen:
                    seen.append(ref)
        return seen

    @property
    def false_positives(self) -> list[str]:
        """What would trip this rule that is not the technique.

        Derived from the rule's own shape rather than left as "Unknown". A rule
        pinned to one hostname fires on everything that host does, and that is
        not a caveat to discover in production — it is the most likely outcome
        of deploying this draft, so it is the first line a reviewer reads.
        """
        causes: list[str] = []
        if not self.behavioural:
            pinned = ", ".join(
                f"{m.sigma_field}={m.value}" for m in self.mappings if not m.generalises
            )
            causes.append(
                f"Every field is specific to {self.incident_ref} ({pinned}). This will "
                "match unrelated activity on the same entities and nothing elsewhere."
            )
        if len(self.mappings) == 1:
            causes.append(
                f"The selection tests a single field ({self.mappings[0].sigma_field}), "
                "so anything carrying that value matches regardless of behaviour."
            )
        return causes or ["Unknown"]

    @property
    def tags(self) -> list[str]:
        if self.technique is None:
            return []
        tactic = self.technique.tactic.lower().replace(" ", "_")
        return [f"attack.{tactic}", f"attack.{self.technique.id.lower()}"]

    # --- emission -----------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """The rule as Sigma's document shape.

        `x-provenance` and `x-gaps` are custom keys, prefixed as the
        specification asks. They are what makes this rule reviewable — the
        mapping table and the honest limitations — and they are in the document
        rather than in the API response because the document is what gets
        copied into a detection repository.
        """
        selection = {mapping.sigma_field: _typed(mapping.value) for mapping in self.mappings}
        document: dict[str, object] = {
            "title": self.title,
            "id": self.rule_id,
            "status": self.status,
            "description": self.description,
            "references": [self.incident_ref, *self.evidence_refs],
            "author": "Sati (drafted from one incident; not validated against live telemetry)",
            "date": "",
            "tags": self.tags,
            "logsource": dict(self.logsource),
            "detection": {"selection": selection, "condition": "selection"},
            # Not the gap list. A missing field is not a false positive, and
            # putting one in the other's key would misreport both to every tool
            # that reads this document — `falsepositives` is what a reviewer
            # triages against, and filling it with "we could not map ShareName"
            # buys a rule the appearance of having been thought about.
            "falsepositives": self.false_positives,
            "level": self.level,
            "x-provenance": {
                mapping.sigma_field: {
                    "source_field": mapping.source_field,
                    "observed_in": list(mapping.refs),
                    "generalises": mapping.generalises,
                }
                for mapping in self.mappings
            },
        }
        if self.gaps:
            document["x-gaps"] = {gap.sigma_field: gap.reason for gap in self.gaps}
        if self.unmapped:
            document["x-not-mapped"] = {gap.sigma_field: gap.reason for gap in self.unmapped}
        if not self.behavioural:
            document["x-warning"] = (
                "Every field in this rule is an instance value from this incident. "
                "It would have matched this occurrence and will not match another; "
                "it is an indicator match, not a behavioural detection."
            )
        return document

    def to_yaml(self, date: str = "") -> str:
        """The document, with the caveats also in a comment header.

        Both, deliberately. The header is what a human sees first in a pull
        request; the custom keys are what a tool can read. Dropping either
        leaves one of the two audiences with a rule that looks finished.

        `date` is passed in rather than read from a clock — this module holds no
        clock, so the same incident yields the same bytes and a diff between two
        drafts shows what changed rather than when it was run.
        """
        document = self.to_dict()
        document["date"] = date or "unset"
        body = yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100)

        header = [
            "# DRAFT - assembled from one incident's stored telemetry. Not deployed,",
            "# not validated against a live log pipeline, and not adopted.",
            f"# Incident: {self.incident_ref}",
        ]
        if self.technique is not None:
            header.append(
                f"# Technique: {self.technique.id} {self.technique.name} "
                f"({self.technique.tactic})"
            )
        header.append("#")
        header.append("# Every field below was read from a stored event:")
        header += [f"#   {mapping.describe()}" for mapping in self.mappings]
        if self.gaps:
            header.append("#")
            header.append("# This telemetry could not supply, and a reviewer should add:")
            header += [f"#   {gap.sigma_field} - {gap.reason}" for gap in self.gaps]
        if not self.behavioural:
            header.append("#")
            header.append(
                "# WARNING: every field is an instance value. This matches this "
                "incident and not the technique."
            )
        return "\n".join(header) + "\n\n" + body


def _typed(value: str) -> object:
    """Ports and the like belong in the rule as numbers.

    A port quoted as a string is a rule that silently fails to match an integer
    field in half the backends Sigma compiles to — the sort of defect that looks
    like the detection simply never firing.
    """
    text = str(value)
    if text.isdigit() and not text.startswith("0"):
        return int(text)
    return text


# --- mapping ------------------------------------------------------------------


def _flow_mappings(event: Event) -> list[Mapping]:
    """A network-flow key parsed into the fields it actually contains.

    The key is `<source>-><destination>:<port>` by construction (`EntityKind
    .NETWORK_FLOW`), so this reads structure that is guaranteed rather than
    guessing at a string.
    """
    match = _FLOW.match(event.entity_ref.id)
    if match is None:
        return []
    destination = match.group("destination")
    port = match.group("port")
    mappings = [
        Mapping(
            sigma_field="DestinationPort",
            source_field="entity_ref.id",
            value=port,
            refs=(event.id,),
        ),
        Mapping(
            sigma_field="DestinationIp" if _IPV4.match(destination) else "DestinationHostname",
            source_field="entity_ref.id",
            value=destination,
            refs=(event.id,),
        ),
    ]
    source = match.group("source")
    if source:
        mappings.append(
            Mapping(
                sigma_field="SourceIp" if _IPV4.match(source) else "SourceHostname",
                source_field="entity_ref.id",
                value=source,
                refs=(event.id,),
            )
        )
    return mappings


def _event_mappings(event: Event) -> tuple[list[Mapping], list[Gap]]:
    """What one event can honestly contribute, and what it was refused for."""
    mappings: list[Mapping] = []
    refused: list[Gap] = []
    kind = event.entity_ref.kind

    if kind is EntityKind.NETWORK_FLOW:
        mappings += _flow_mappings(event)
    elif kind is EntityKind.HOST:
        mappings.append(
            Mapping(
                sigma_field="Computer",
                source_field="entity_ref.id",
                value=event.entity_ref.id,
                refs=(event.id,),
            )
        )
    elif kind is EntityKind.ACCOUNT:
        mappings.append(
            Mapping(
                sigma_field="TargetUserName",
                source_field="entity_ref.id",
                value=event.entity_ref.id,
                refs=(event.id,),
            )
        )
    elif kind is EntityKind.PROCESS:
        # `process:<host>/<name>` — the name half is the image, the host half is
        # already carried by Computer if a host event supplied it.
        name = event.entity_ref.id.split("/", 1)[-1]
        if name:
            mappings.append(
                Mapping(
                    sigma_field="Image",
                    source_field="entity_ref.id",
                    value=name,
                    refs=(event.id,),
                    # A process name is the behaviour. `schtasks.exe` on a host
                    # that has never run it is a finding wherever it happens,
                    # which is what distinguishes it from a hostname.
                    generalises=True,
                )
            )

    payload = event.payload
    address = getattr(payload, "source_address", None)
    if address:
        mappings.append(
            Mapping(
                sigma_field="SourceIp" if _IPV4.match(str(address)) else "SourceHostname",
                source_field="payload.source_address",
                value=str(address),
                refs=(event.id,),
            )
        )

    principal = getattr(payload, "principal", None)
    if principal:
        if kind is EntityKind.ACCOUNT:
            mappings.append(
                Mapping(
                    sigma_field="SubjectUserName",
                    source_field="payload.principal",
                    value=str(principal),
                    refs=(event.id,),
                )
            )
        else:
            # The category error this module is most likely to make, refused in
            # the one place it would be made. On a host-scoped detection
            # `principal` holds a hostname, and a hostname in SubjectUserName is
            # a rule that parses, cites a real value and is wrong.
            refused.append(
                Gap(
                    sigma_field="SubjectUserName",
                    reason=(
                        f"payload.principal on {event.id} is {principal!r}, which is a "
                        f"{kind.value} and not an account. Mapping it to a user field "
                        "would put a hostname in a username: the rule would parse, cite "
                        "a real stored value, and match nothing"
                    ),
                )
            )

    # Two fields we hold, understand, and still will not map. Reported rather
    # than dropped, because a reader comparing the rule against the evidence
    # will see them in the event and otherwise has no way to tell a considered
    # refusal from an oversight in the mapper.
    detection_type = getattr(payload, "detection_type", None)
    if detection_type:
        refused.append(
            Gap(
                sigma_field="(none)",
                reason=(
                    f"payload.detection_type on {event.id} is {detection_type!r}, which is "
                    "this platform's own detector label rather than a field of the source "
                    "log. Sigma matches what the log recorded, not what we concluded from "
                    "it, so there is no field for this and inventing one would encode our "
                    "verdict as somebody else's observation"
                ),
            )
        )
    if event.labels.get("summary"):
        refused.append(
            Gap(
                sigma_field="(prose)",
                reason=(
                    f"labels.summary on {event.id} names the detail a stronger rule would "
                    "key on, in prose written for a human. Parsing hostnames out of it "
                    "would make the rule depend on sentence structure, which is the "
                    "guessing this module refuses everywhere else"
                ),
            )
        )

    return mappings, refused


def _dedupe(mappings: list[Mapping]) -> tuple[Mapping, ...]:
    """One Sigma field, one value, all the records that carried it.

    Two events observing the same destination should strengthen the citation,
    not produce two selections. Where two events disagree on a value the first
    is kept and the second dropped, because a selection cannot hold both and
    silently picking the later one would make the rule depend on ingest order.
    """
    merged: dict[str, Mapping] = {}
    for mapping in mappings:
        existing = merged.get(mapping.sigma_field)
        if existing is None:
            merged[mapping.sigma_field] = mapping
            continue
        if existing.value != mapping.value:
            continue
        refs = tuple(dict.fromkeys((*existing.refs, *mapping.refs)))
        merged[mapping.sigma_field] = Mapping(
            sigma_field=existing.sigma_field,
            source_field=existing.source_field,
            value=existing.value,
            refs=refs,
            generalises=existing.generalises or mapping.generalises,
        )
    return tuple(merged.values())


def _technique_gaps(technique: AttackTechnique | None, filled: set[str]) -> list[Gap]:
    """Fields a published rule for this technique commonly keys on and we did
    not fill, each stated as what our store does not carry."""
    if technique is None:
        return []
    wanted = TECHNIQUE_FIELDS.get(technique.id, ())
    return [
        Gap(
            sigma_field=name,
            reason=(
                f"no stored event for this step carries {name}; the normalized event "
                f"model (events.py) has no field it maps from, so a rule for "
                f"{technique.id} keying on it would be inventing the value"
            ),
        )
        for name in wanted
        if name not in filled
    ]


def _logsource(events: list[Event]) -> dict[str, str]:
    """Deliberately coarse.

    Our events carry `source` ("demo", a connector name) and `event_class`, and
    neither is a Sigma product. Claiming `product: windows` because the detection
    concerns SMB would be asserting where these logs came from, which is exactly
    the sort of confident-and-unfounded line this module refuses elsewhere.
    """
    classes = sorted({event.event_class.value for event in events})
    sources = sorted({event.source for event in events})
    return {
        "category": classes[0] if len(classes) == 1 else "multiple",
        "product": "pashupatastra",
        "service": sources[0] if len(sources) == 1 else "multiple",
    }


def draft_rule(
    incident: Incident,
    events: list[Event],
    technique_id: str | None = None,
) -> DetectionRule:
    """Draft a rule for one step of one incident.

    Scoped to a step rather than the whole incident on purpose. An incident is a
    sequence of techniques and a Sigma rule detects one thing; a rule fusing a
    C2 beacon with a scheduled task into one selection would fire only where all
    of it appears at once, which is after the intrusion has finished.

    The step's own `evidence` decides which events are read, so the rule rests
    on exactly the records the causal chain says established that step — not on
    everything that happened to be stored near it.
    """
    links = [link for link in incident.causal_chain if link.attack_technique is not None]
    if not links:
        raise SigmaError(
            f"{incident.id} has no causal step carrying an attack technique, so there "
            "is no adversary behaviour here to write a rule for. The infrastructure "
            "domain has no ATT&CK mapping and inventing one would be worse than none."
        )

    if technique_id:
        chosen = [link for link in links if link.attack_technique.id == technique_id]
        if not chosen:
            available = ", ".join(sorted({link.attack_technique.id for link in links}))
            raise SigmaError(
                f"{incident.id} has no step for {technique_id}. It carries: {available}"
            )
        link = chosen[0]
    else:
        link = links[0]

    technique = link.attack_technique
    cited = set(link.evidence)
    relevant = [event for event in events if event.id in cited]
    if not relevant:
        raise SigmaError(
            f"{incident.id}/{technique.id} cites {sorted(cited)}, none of which is "
            "among the events supplied. A rule drafted from records that were not "
            "read would cite ids it never saw."
        )

    collected: list[Mapping] = []
    refused: list[Gap] = []
    for event in sorted(relevant, key=lambda e: e.id):
        mappings, refusals = _event_mappings(event)
        collected += mappings
        refused += refusals

    mappings = _dedupe(collected)
    if not mappings:
        raise SigmaError(
            f"{incident.id}/{technique.id}: none of {sorted(cited)} carries a field "
            "that maps to Sigma. Emitting a rule anyway would mean inventing one."
        )

    filled = {mapping.sigma_field for mapping in mappings}
    gaps = _technique_gaps(technique, filled)
    # Keyed on the reason as well as the field: several events can each refuse
    # the same Sigma field for different reasons, and collapsing those on the
    # field alone would report one event's refusal as though it were the only one.
    unmapped = tuple({(g.sigma_field, g.reason): g for g in refused}.values())

    return DetectionRule(
        incident_ref=incident.id,
        title=f"Draft: {technique.name} observed in {incident.id}",
        description=(
            f"Drafted from {incident.id}, which recorded: {link.transition}. "
            f"Fields below were read from {', '.join(sorted(cited))}. "
            f"{'Some fields this technique usually keys on are absent - see x-gaps.' if gaps else ''}"
        ).strip(),
        logsource=_logsource(relevant),
        mappings=mappings,
        gaps=tuple(gaps),
        technique=technique,
        level="high" if incident.severity.value == "critical" else "medium",
        evidence_refs=tuple(sorted(cited)),
        unmapped=unmapped,
    )


def rule_techniques(incident: Incident) -> list[AttackTechnique]:
    """Which rules could be drafted from this incident, in chain order."""
    seen: dict[str, AttackTechnique] = {}
    for link in incident.causal_chain:
        if link.attack_technique is not None:
            seen.setdefault(link.attack_technique.id, link.attack_technique)
    return list(seen.values())


# --- validation ---------------------------------------------------------------


def validate(text: str) -> list[str]:
    """Structural validation against the Sigma specification.

    Returns the problems rather than raising, because a caller checking output
    wants all of them at once. This is a real parse of the emitted document —
    the clause R71 is measured on is that the thing we hand a reviewer would be
    accepted by the repository they paste it into, and the only way to know that
    is to read it back as a document rather than to trust the writer.
    """
    problems: list[str] = []
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"not parseable as YAML: {exc}"]

    if not isinstance(document, dict):
        return ["a Sigma rule is a YAML mapping at the top level"]

    title = document.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("title is required and must be a non-empty string")
    elif len(title) > 256:
        problems.append(f"title is {len(title)} characters; the specification caps it at 256")

    if "id" in document:
        try:
            uuid.UUID(str(document["id"]))
        except ValueError:
            problems.append(f"id {document['id']!r} is not a UUID")

    status = document.get("status")
    if status is not None and status not in STATUSES:
        problems.append(f"status {status!r} is not one of {STATUSES}")

    level = document.get("level")
    if level is not None and level not in LEVELS:
        problems.append(f"level {level!r} is not one of {LEVELS}")

    logsource = document.get("logsource")
    if not isinstance(logsource, dict):
        problems.append("logsource is required and must be a mapping")
    elif not any(key in logsource for key in ("category", "product", "service")):
        problems.append("logsource names none of category, product or service")

    detection = document.get("detection")
    if not isinstance(detection, dict):
        problems.append("detection is required and must be a mapping")
        return problems

    condition = detection.get("condition")
    if not isinstance(condition, str) or not condition.strip():
        problems.append("detection.condition is required")

    selections = {key: value for key, value in detection.items() if key != "condition"}
    if not selections:
        problems.append("detection defines no selection, so the condition refers to nothing")
    for name, body in selections.items():
        if isinstance(body, dict) and not body:
            problems.append(f"selection {name!r} is empty, which matches everything")

    if isinstance(condition, str):
        # Bare identifiers in the condition must be defined above. Sigma's
        # condition grammar is larger than this, but an undefined selection name
        # is the error that actually happens and it is silent at deploy time.
        keywords = {"and", "or", "not", "of", "them", "all", "1", "any"}
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", condition):
            if token in keywords or token.endswith("*"):
                continue
            if token not in selections and not any(
                name.startswith(token.rstrip("*")) for name in selections
            ):
                problems.append(f"condition refers to {token!r}, which is not defined")

    return problems


__all__ = [
    "TECHNIQUE_FIELDS",
    "DetectionRule",
    "Gap",
    "Mapping",
    "SigmaError",
    "draft_rule",
    "rule_techniques",
    "validate",
]
