"""R70: a draft cites everything it asserts, and is a draft everywhere.

The strongest test here is the one that tries to build an uncited line and
cannot. Checking afterwards that every line happens to have a ref tests the
builder as it is written today; refusing to construct one tests the builder
anybody writes next.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pashupatastra.drafts import (
    PLAYBOOK,
    POST_INCIDENT,
    Line,
    build_draft,
    playbook,
    post_incident,
)
from pashupatastra.events import EntityKind, EntityRef
from pashupatastra.incidents import (
    CausalLink,
    Execution,
    Hypothesis,
    Incident,
    IncidentSeverity,
    PlanStep,
    Verification,
    VerificationCheck,
)
from pashupatastra.registry import get as get_action

NOW = datetime(2026, 8, 25, 12, 0).astimezone()
HOST = EntityRef(kind=EntityKind.HOST, id="ws-0148", name="ws-0148")


def an_incident(**overrides) -> Incident:
    base = dict(
        id="INC-2026-0903",
        severity=IncidentSeverity.CRITICAL,
        opened_at=NOW,
        affected_entities=[HOST],
        causal_chain=[
            CausalLink(entity=HOST, transition="beaconed outbound", evidence=["evt-a"])
        ],
        hypotheses=[
            Hypothesis(
                statement="Implant beaconing to a C2 host.",
                confidence=0.9,
                evidence=["evt-a"],
            ),
            Hypothesis(
                statement="Backup software on a schedule.",
                confidence=0.05,
                evidence=["evt-a"],
                contradicted_by=["evt-b"],
            ),
        ],
        plan=[
            PlanStep(
                order=1,
                action_id="isolate_host",
                expected_post_state={"host.network": "isolated"},
                rollback_action_id="rejoin_network",
            )
        ],
    )
    base.update(overrides)
    return Incident(**base)


def all_lines(draft):
    return [line for section in draft.sections for line in section.lines]


# --- the rule, enforced where it cannot be forgotten ---------------------------


def test_a_line_that_cites_nothing_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="cites nothing"):
        Line(text="The attacker was probably a nation state.", refs=())


def test_every_line_of_every_draft_carries_a_reference() -> None:
    incident = an_incident()
    for draft in (playbook(incident), post_incident(incident)):
        assert all_lines(draft), f"{draft.kind} produced no lines at all"
        for line in all_lines(draft):
            assert line.refs, line.text


def test_a_draft_cites_records_that_belong_to_its_incident() -> None:
    """A ref pointing at something else is a citation that looks checkable and
    leads somewhere unrelated — the failure R59 is about, one layer up."""
    incident = an_incident()
    draft = post_incident(incident)
    for ref in draft.refs:
        assert ref.startswith(incident.id) or ref.startswith("evt-"), ref


# --- a draft is a draft --------------------------------------------------------


def test_a_draft_says_so_in_its_title_and_its_status() -> None:
    incident = an_incident()
    for draft in (playbook(incident), post_incident(incident)):
        assert draft.status == "draft"
        assert draft.title.lower().startswith("draft")


def test_nothing_can_set_a_draft_to_adopted() -> None:
    """`status` is a property, not a field. A status that can be assigned is a
    status that eventually is, and the approved thing is an audit record naming
    a human — not a flag on the document."""
    draft = playbook(an_incident())
    with pytest.raises(AttributeError):
        draft.status = "adopted"  # type: ignore[misc]


# --- adopting is an action -----------------------------------------------------


def test_adopting_names_a_registered_action_with_a_rollback() -> None:
    """Clause three. Adopting is not a save button: it is scored and routed like
    anything else that changes how the next incident is handled."""
    incident = an_incident()
    for draft in (playbook(incident), post_incident(incident)):
        action = get_action(draft.adopt_action_id)
        assert action.base_risk > 0, "an action with no risk needs no approval, which is the bug"
        assert action.has_tested_rollback
        assert not action.read_only, "adopting must never be reachable from the chat agent"


def test_the_adopt_actions_cannot_be_reached_by_the_analyst() -> None:
    """The agent drafts; a human adopts. `read_only` is what the chat toolbox
    derives its list from, so this is the property that keeps the two apart."""
    for action_id in ("adopt_playbook", "adopt_report", "retract_playbook", "retract_report"):
        assert not get_action(action_id).read_only


# --- what the documents say ----------------------------------------------------


def test_the_report_names_what_was_ruled_out_and_on_what() -> None:
    """The part a report written afterwards always drops: by then the answer
    feels obvious and the alternative that was live at 3am goes unmentioned."""
    draft = post_incident(an_incident())
    ruled = [line for line in all_lines(draft) if line.text.startswith("Ruled out:")]
    assert ruled, "the report does not say what the diagnosis beat"
    assert "evt-b" in ruled[0].refs


def test_nothing_executed_is_stated_rather_than_left_out() -> None:
    """An empty section reads as an author who forgot. A stated absence is a
    claim a reader can check."""
    draft = post_incident(an_incident())
    said = " ".join(line.text for line in all_lines(draft))
    assert "Nothing was executed" in said
    assert "No verification is recorded" in said


def test_a_verified_incident_reports_what_was_observed() -> None:
    incident = an_incident(
        executions=[
            Execution(
                step_order=1,
                action_id="isolate_host",
                started_at=NOW,
                finished_at=NOW,
                succeeded=True,
                verdict_snapshot=_a_verdict(),
            )
        ],
        verification=Verification(
            window_seconds=300,
            checks=[
                VerificationCheck(
                    name="host.network", expected="isolated", observed="isolated", passed=True
                )
            ],
        ),
    )
    said = " ".join(line.text for line in all_lines(post_incident(incident)))
    assert "isolate_host — succeeded" in said
    assert "expected isolated, observed isolated" in said


def test_a_playbook_carries_the_rollback_and_the_tier_of_each_step() -> None:
    """A playbook that lists steps without saying what undoes them or who has to
    approve them is the half of the procedure that is easy to write."""
    said = " ".join(line.text for line in all_lines(playbook(an_incident())))
    assert "isolate_host" in said
    assert "rollback: rejoin_network" in said


def test_an_incident_with_no_plan_still_produces_an_honest_playbook() -> None:
    draft = playbook(an_incident(plan=[]))
    said = " ".join(line.text for line in all_lines(draft))
    assert "No plan is recorded" in said


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(KeyError):
        build_draft("executive_summary", an_incident())


def test_build_resolves_both_kinds() -> None:
    incident = an_incident()
    assert build_draft(PLAYBOOK, incident).kind == PLAYBOOK
    assert build_draft(POST_INCIDENT, incident).kind == POST_INCIDENT


def _a_verdict():
    from pashupatastra.dharma import Tier, Verdict

    return Verdict(
        action_id="isolate_host",
        incident_ref="INC-2026-0903",
        base_risk=55,
        adjustments=[],
        effective_risk=55,
        tier=Tier.APPROVAL,
        required_approvers=["operator"],
        granted_by="operator",
    )
