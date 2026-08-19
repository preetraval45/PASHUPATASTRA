"""Scripted blue-team incidents for the public demo.

These are **written**, not observed. Nothing here came off a real network, and
the deployment that serves them reports `degraded` and `dry run` for exactly
that reason. The agent that watches a real machine is a separate deployment
(docs/REBUILD.md, Phase A) and shares none of this data.

Each scenario declares its telemetry *and* its incident, in that order, so that
every evidence id an incident cites is an event that exists. The alternative is
a plausible-looking string in a citation that resolves to nothing, which is the
defect R6 exists to remove — a reference that looks checkable and is not is
worse than no reference, because a reader stops looking.

Three scenarios, chosen because each is a case this system could plausibly get
wrong:

* **Credential stuffing** — the alternative reading ("the user is travelling")
  is genuinely reasonable until impossible travel rules it out.
* **Phishing to token theft** — the tempting response is a password reset, and a
  password reset does not revoke a stolen token. Getting the *right* action here
  matters more than detecting it at all.
* **Beaconing and lateral movement** — regular outbound connections to one
  destination are what backup software looks like, and the difference is the
  destination, not the pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pashupatastra import (
    AttackTechnique,
    CausalLink,
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    Hypothesis,
    Impact,
    Incident,
    IncidentSeverity,
    IncidentState,
    PlanStep,
    Provenance,
    Severity,
)
from pashupatastra.events import SecurityPayload
from pashupatastra.registry import get as get_action


def _ref(kind: EntityKind, name: str) -> EntityRef:
    return EntityRef(kind=kind, id=name, name=name)


@dataclass
class Signal:
    """One observation the incident will cite, and the entity it happened to."""

    id: str
    entity: EntityRef
    at_offset_seconds: float
    detection: str
    message: str
    severity: Severity = Severity.WARNING
    confidence: float = 0.9


@dataclass
class Scenario:
    """A written incident and the telemetry it cites."""

    incident: Incident
    signals: list[Signal] = field(default_factory=list)

    def events(self, now: datetime) -> list[Event]:
        """Materialise the telemetry, anchored so it reads as recent.

        Offsets are relative and negative — the newest signal sits closest to
        `now`. A fixture stamped at a fixed date would show a dashboard of
        month-old events and read as a system that had stopped.
        """
        return [
            Event(
                id=signal.id,
                event_class=EventClass.SECURITY,
                source="demo",
                occurred_at=now + timedelta(seconds=signal.at_offset_seconds),
                observed_at=now + timedelta(seconds=signal.at_offset_seconds),
                entity_ref=signal.entity,
                severity=signal.severity,
                payload=SecurityPayload(
                    detection_type=signal.detection,
                    principal=signal.entity.id,
                    confidence=signal.confidence,
                ),
                # Says what it is. No view can present a written scenario as
                # something observed from a live system.
                provenance=Provenance(
                    source_system="demo-scenario",
                    query=self.incident.id,
                ),
                labels={"summary": signal.message},
            )
            for signal in self.signals
        ]


def _plan(*action_ids: str) -> list[PlanStep]:
    """Plan steps carry the registry's post-state and rollback, never a copy.

    A plan that restated them would be a second answer to "what does this action
    do", and the one the operator reads would be the one that drifted.
    """
    return [
        PlanStep(
            order=order,
            action_id=action_id,
            expected_post_state=get_action(action_id).expected_post_state,
            rollback_action_id=get_action(action_id).rollback_action_id,
        )
        for order, action_id in enumerate(action_ids, start=1)
    ]


# --- 1. credential stuffing ---------------------------------------------------


def credential_stuffing(now: datetime) -> Scenario:
    account = _ref(EntityKind.ACCOUNT, "j.rivera")
    asset = _ref(EntityKind.ASSET, "sso-portal")
    flow = _ref(EntityKind.NETWORK_FLOW, "45.61.184.22->sso-portal:443")

    signals = [
        Signal("SEC-0001-a", flow, -2100, "auth_failure_burst",
               "412 failed sign-ins from AS204428, an ASN never seen before"),
        Signal("SEC-0001-b", account, -1740, "auth_success_after_failures",
               "successful sign-in for j.rivera from the same address",
               severity=Severity.CRITICAL),
        Signal("SEC-0001-c", account, -1500, "impossible_travel",
               "sign-in from Lagos 4 minutes after a sign-in from Charlotte",
               severity=Severity.CRITICAL, confidence=0.97),
        Signal("SEC-0001-d", asset, -1440, "session_issued",
               "new session issued to j.rivera from an unrecognised device"),
    ]

    incident = Incident(
        id="INC-2026-0901",
        severity=IncidentSeverity.CRITICAL,
        opened_at=now - timedelta(seconds=1700),
        affected_entities=[account, asset],
        impact=Impact(
            estimated_users_affected=1,
            affected_services=["sso-portal"],
            blast_radius_entities=2,
        ),
        hypotheses=[
            Hypothesis(
                statement=(
                    "Credential stuffing against the SSO portal succeeded on one "
                    "account: 412 failures from a single new ASN, then one success."
                ),
                confidence=0.94,
                evidence=["SEC-0001-a", "SEC-0001-b", "SEC-0001-c"],
                contradicted_by=[],
                mechanism=[
                    "credential list replayed against sso-portal",
                    "412 failures across many accounts",
                    "one valid pair accepted",
                    "session issued to an unrecognised device",
                ],
            ),
            Hypothesis(
                statement="The user is travelling and signed in from a new location.",
                confidence=0.03,
                evidence=["SEC-0001-b"],
                # The reason this scenario is worth having: travelling is a
                # perfectly ordinary explanation for one sign-in from a new
                # place, and only the interval kills it.
                contradicted_by=["SEC-0001-c", "SEC-0001-a"],
            ),
        ],
        causal_chain=[
            CausalLink(
                entity=flow,
                transition="412 sign-in failures from one new ASN in 6 minutes",
                evidence=["SEC-0001-a"],
                attack_technique=AttackTechnique(
                    id="T1110.004", name="Credential Stuffing", tactic="Credential Access"
                ),
            ),
            CausalLink(
                entity=account,
                transition="failures → one success on the same account",
                evidence=["SEC-0001-b", "SEC-0001-c"],
                attack_technique=AttackTechnique(
                    id="T1078.004", name="Cloud Accounts", tactic="Defense Evasion"
                ),
            ),
            CausalLink(
                entity=asset,
                transition="session issued to an unrecognised device",
                evidence=["SEC-0001-d"],
                attack_technique=AttackTechnique(
                    id="T1078", name="Valid Accounts", tactic="Persistence"
                ),
            ),
        ],
        plan=_plan("revoke_session", "require_mfa_reauth"),
    )
    incident.transition_to(
        IncidentState.CORRELATED, "agent:sentinel",
        "412 failures and one success on one account within 11 minutes",
    )
    incident.transition_to(
        IncidentState.DIAGNOSED, "agent:analyst",
        "impossible travel rules out the travelling-user reading",
    )
    incident.transition_to(
        IncidentState.AWAITING_APPROVAL, "dharma",
        "revoke_session scores 25 → approval tier",
    )
    return Scenario(incident=incident, signals=signals)


# --- 2. phishing to token theft -----------------------------------------------


def token_theft(now: datetime) -> Scenario:
    account = _ref(EntityKind.ACCOUNT, "m.okafor")
    mailbox = _ref(EntityKind.ASSET, "m.okafor-mailbox")
    app = _ref(EntityKind.ASSET, "oauth-app-Rep0rt-Sync")

    signals = [
        Signal("SEC-0002-a", mailbox, -5400, "lookalike_domain_delivered",
               "message from rn1crosoft-billing.com delivered to m.okafor"),
        Signal("SEC-0002-b", account, -4980, "phishing_link_followed",
               "proxy log records the link being followed"),
        Signal("SEC-0002-c", app, -4800, "oauth_consent_granted",
               "token issued to 'Rep0rt Sync', an application never consented to before",
               severity=Severity.CRITICAL),
        Signal("SEC-0002-d", mailbox, -3600, "mailbox_read_by_token",
               "mailbox read in bulk using the new token",
               severity=Severity.CRITICAL),
        Signal("SEC-0002-e", account, -3540, "no_password_authentication",
               "no password authentication event for m.okafor in the window",
               severity=Severity.INFO, confidence=0.99),
    ]

    incident = Incident(
        id="INC-2026-0902",
        severity=IncidentSeverity.HIGH,
        opened_at=now - timedelta(seconds=4700),
        affected_entities=[account, mailbox, app],
        impact=Impact(
            estimated_users_affected=1,
            affected_services=["mail"],
            blast_radius_entities=3,
        ),
        hypotheses=[
            Hypothesis(
                statement=(
                    "A phishing link led to an OAuth consent, and the resulting "
                    "token — not a password — is what read the mailbox."
                ),
                confidence=0.91,
                evidence=["SEC-0002-b", "SEC-0002-c", "SEC-0002-d", "SEC-0002-e"],
                contradicted_by=[],
                mechanism=[
                    "lookalike domain delivered",
                    "link followed",
                    "OAuth consent granted to an unfamiliar application",
                    "token used to read the mailbox",
                ],
            ),
            Hypothesis(
                statement="The account's password was compromised and used to sign in.",
                confidence=0.04,
                evidence=["SEC-0002-d"],
                # The distinction the whole scenario exists for. If this were
                # the diagnosis the response would be a password reset, and a
                # password reset does not revoke an already-issued token: the
                # attacker keeps reading the mailbox and the alert closes.
                contradicted_by=["SEC-0002-e", "SEC-0002-c"],
            ),
        ],
        causal_chain=[
            CausalLink(
                entity=mailbox,
                transition="message from a lookalike domain delivered",
                evidence=["SEC-0002-a"],
                attack_technique=AttackTechnique(
                    id="T1566.002", name="Spearphishing Link", tactic="Initial Access"
                ),
            ),
            CausalLink(
                entity=app,
                transition="OAuth consent granted to an unfamiliar application",
                evidence=["SEC-0002-b", "SEC-0002-c"],
                attack_technique=AttackTechnique(
                    id="T1528", name="Steal Application Access Token",
                    tactic="Credential Access",
                ),
            ),
            CausalLink(
                entity=mailbox,
                transition="mailbox read in bulk by the issued token",
                evidence=["SEC-0002-d"],
                attack_technique=AttackTechnique(
                    id="T1114.002", name="Remote Email Collection", tactic="Collection"
                ),
            ),
        ],
        # Revoke the token and pull the message. Notably *not*
        # force_password_reset: the password was never used, so resetting it
        # would inconvenience the user and leave the token working.
        plan=_plan("revoke_session", "quarantine_email"),
    )
    incident.transition_to(
        IncidentState.CORRELATED, "agent:sentinel",
        "delivery, click, consent and bulk read on one account within 31 minutes",
    )
    incident.transition_to(
        IncidentState.DIAGNOSED, "agent:analyst",
        "no password authentication in the window — this is a token, not a credential",
    )
    incident.transition_to(
        IncidentState.AWAITING_APPROVAL, "dharma",
        "revoke_session scores 25 → approval tier",
    )
    return Scenario(incident=incident, signals=signals)


# --- 3. beaconing and lateral movement ----------------------------------------


def beaconing(now: datetime) -> Scenario:
    host = _ref(EntityKind.HOST, "ws-0148")
    peer_a = _ref(EntityKind.HOST, "fs-02")
    peer_b = _ref(EntityKind.HOST, "app-07")
    beacon = _ref(EntityKind.NETWORK_FLOW, "ws-0148->198.51.100.74:8443")
    task = _ref(EntityKind.PROCESS, "app-07/schtasks")

    signals = [
        Signal("SEC-0003-a", beacon, -7200, "rare_destination",
               "outbound to 198.51.100.74:8443, a destination no host has used before"),
        Signal("SEC-0003-b", beacon, -6600, "regular_interval",
               "connections every 60s ± 2s for 96 minutes — machine-timed, not human",
               severity=Severity.CRITICAL, confidence=0.88),
        Signal("SEC-0003-c", host, -2400, "new_smb_peer",
               "ws-0148 opened SMB to fs-02 and app-07, neither contacted before"),
        Signal("SEC-0003-d", task, -1800, "scheduled_task_created",
               "scheduled task created on app-07 by a remote session",
               severity=Severity.CRITICAL),
        Signal("SEC-0003-e", beacon, -7100, "not_backup_infrastructure",
               "198.51.100.74 is not in the backup infrastructure inventory",
               severity=Severity.INFO, confidence=0.99),
    ]

    incident = Incident(
        id="INC-2026-0903",
        severity=IncidentSeverity.CRITICAL,
        opened_at=now - timedelta(seconds=6500),
        affected_entities=[host, peer_a, peer_b],
        impact=Impact(
            estimated_users_affected=0,
            affected_services=["file-share", "app-07"],
            blast_radius_entities=4,
        ),
        hypotheses=[
            Hypothesis(
                statement=(
                    "ws-0148 is beaconing to a command-and-control host and has "
                    "begun moving laterally: new SMB peers, then a scheduled task."
                ),
                confidence=0.86,
                evidence=["SEC-0003-a", "SEC-0003-b", "SEC-0003-c", "SEC-0003-d"],
                contradicted_by=[],
                mechanism=[
                    "regular outbound connection to a rare destination",
                    "SMB to hosts never previously contacted",
                    "scheduled task created remotely",
                ],
            ),
            Hypothesis(
                statement="A backup agent is running on its schedule.",
                confidence=0.09,
                evidence=["SEC-0003-b"],
                # Regular outbound connections are exactly what backup software
                # looks like. The pattern does not separate them; the
                # destination does.
                contradicted_by=["SEC-0003-e", "SEC-0003-c", "SEC-0003-d"],
            ),
        ],
        causal_chain=[
            CausalLink(
                entity=beacon,
                transition="outbound every 60s ± 2s to a destination never seen before",
                evidence=["SEC-0003-a", "SEC-0003-b"],
                attack_technique=AttackTechnique(
                    id="T1071.001", name="Web Protocols", tactic="Command and Control"
                ),
            ),
            CausalLink(
                entity=host,
                transition="SMB opened to two hosts never previously contacted",
                evidence=["SEC-0003-c"],
                attack_technique=AttackTechnique(
                    id="T1021.002", name="SMB/Windows Admin Shares",
                    tactic="Lateral Movement",
                ),
            ),
            CausalLink(
                entity=task,
                transition="scheduled task created on app-07 from a remote session",
                evidence=["SEC-0003-d"],
                attack_technique=AttackTechnique(
                    id="T1053.005", name="Scheduled Task", tactic="Persistence"
                ),
            ),
        ],
        plan=_plan("isolate_host", "block_ip"),
    )
    incident.transition_to(
        IncidentState.CORRELATED, "agent:sentinel",
        "beacon, new SMB peers and remote task creation on one host within 90 minutes",
    )
    incident.transition_to(
        IncidentState.DIAGNOSED, "agent:analyst",
        "destination absent from backup inventory — the backup reading does not hold",
    )
    incident.transition_to(
        IncidentState.ESCALATED, "dharma",
        "isolate_host scores 55 → senior approval",
    )
    return Scenario(incident=incident, signals=signals)


BUILDERS = (credential_stuffing, token_theft, beaconing)


def scenarios(now: datetime | None = None) -> list[Scenario]:
    now = now or datetime.now().astimezone()
    return [build(now) for build in BUILDERS]
