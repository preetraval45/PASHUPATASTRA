"""The Blue Team debrief: every point traced to a named thing.

Built on a hand-made incident and a stub graph rather than on the seeded demo
scenarios, because `testgame.py` skips its whole file when those are absent —
*"demo scenarios are not seeded in this configuration"* — and R64's rule would
then be checked only in configurations nobody runs locally. That is the third
suite in this repository gated behind something that is usually missing, and the
pattern is worth naming: a test that silently does not run reports green.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.game import score
from pashupatastra.incidents import (
    CausalLink,
    Hypothesis,
    Incident,
    IncidentSeverity,
    PlanStep,
)
from pashupatastra.events import EntityKind, EntityRef

NOW = datetime(2026, 8, 24, 12, 0, 0).astimezone()

HOST = EntityRef(kind=EntityKind.HOST, id="ws-1", name="ws-1")
PEER = EntityRef(kind=EntityKind.HOST, id="fs-9", name="fs-9")

# `fs-9` holds the observation that rules out the decoy. A player who never
# opens it can still guess correctly, which is the distinction the exercise is
# built to measure.
DECISIVE = "EV-decisive"


def an_incident() -> Incident:
    return Incident(
        id="INC-2026-9001",
        severity=IncidentSeverity.HIGH,
        opened_at=NOW - timedelta(minutes=30),
        affected_entities=[HOST, PEER],
        hypotheses=[
            Hypothesis(
                statement="A workstation is beaconing to a command-and-control host.",
                confidence=0.9,
                evidence=["EV-beacon-1", "EV-beacon-2"],
            ),
            Hypothesis(
                statement="A backup job is running on an unusual schedule.",
                confidence=0.3,
                evidence=["EV-sched"],
                contradicted_by=[DECISIVE],
            ),
        ],
        causal_chain=[
            CausalLink(entity=HOST, transition="outbound every 60s", evidence=["EV-beacon-1"]),
        ],
        plan=[
            PlanStep(order=1, action_id="isolate_host", expected_post_state={"isolated": "true"}),
        ],
    )


class _Graph:
    """Two entities, each with its own evidence. `fs-9` holds the decisive one."""

    EVENTS = {
        "host:ws-1": [{"id": "EV-beacon-1"}, {"id": "EV-beacon-2"}],
        "host:fs-9": [{"id": DECISIVE}, {"id": "EV-quiet"}],
    }

    def entity_events(self, key: str, limit: int = 8):
        return self.EVENTS.get(key, [])[:limit]

    def event(self, ref: str):
        for key, rows in self.EVENTS.items():
            if any(row["id"] == ref for row in rows):
                return {"id": ref, "entity_key": key}
        return None

    def entity(self, key: str):
        return {"key": key}


def marked(*, diagnosis: str, action: str, investigated: list[str]) -> dict:
    incident = an_incident()
    from app.game import _choice_id

    chosen = next(
        _choice_id(h.statement) for h in incident.hypotheses if h.statement.startswith(diagnosis)
    )
    return score(
        incident,
        _Graph(),
        diagnosis_id=chosen,
        action_id=action,
        investigated=investigated,
    )


# --- the done-when ----------------------------------------------------------


def test_the_board_is_complete_not_a_highlight_reel() -> None:
    """Every entity appears in exactly one of opened/missed.

    A debrief showing only the decisive miss would let a player conclude they
    had covered everything else, which is the opposite of what it is for.
    """
    result = marked(diagnosis="A workstation", action="isolate_host", investigated=["host:ws-1"])
    debrief = result["debrief"]
    opened = {row["entity_key"] for row in debrief["opened"]}
    missed = {row["entity_key"] for row in debrief["missed"]}
    assert opened == {"host:ws-1"}
    assert missed == {"host:fs-9"}
    assert not (opened & missed)
    assert opened | missed == {"host:ws-1", "host:fs-9"}


def test_unopened_evidence_is_listed_by_name() -> None:
    """R64 is explicit about this. "You missed something" teaches nothing;
    naming `host:fs-9` and `EV-decisive` teaches the lesson."""
    result = marked(diagnosis="A workstation", action="isolate_host", investigated=["host:ws-1"])
    missed = {row["entity_key"]: row for row in result["debrief"]["missed"]}
    assert DECISIVE in missed["host:fs-9"]["evidence"]
    assert missed["host:fs-9"]["decisive"] is True
    assert missed["host:fs-9"]["decisive_evidence"] == [DECISIVE]


def test_being_right_by_luck_is_distinguishable_from_being_right() -> None:
    """The same correct diagnosis, scored differently depending on whether the
    player opened the thing that rules out the alternative. This is the entire
    reason the investigation category exists."""
    lucky = marked(diagnosis="A workstation", action="isolate_host", investigated=["host:ws-1"])
    thorough = marked(
        diagnosis="A workstation", action="isolate_host", investigated=["host:ws-1", "host:fs-9"]
    )
    assert thorough["total"] > lucky["total"]

    by_name = {row["name"]: row for row in lucky["breakdown"]}
    assert by_name["Diagnosis"]["points"] == by_name["Diagnosis"]["of"]
    assert by_name["Investigation"]["points"] == 0


def test_every_line_of_the_breakdown_names_what_it_judged() -> None:
    """A point gained or lost traces to named evidence or a named decision. A
    number with a sentence beside it is still a number."""
    result = marked(diagnosis="A backup job", action="read_logs", investigated=[])
    lines = {row["name"]: row for row in result["breakdown"]}

    # Evidence-based lines cite refs.
    assert lines["Diagnosis"]["evidence"] == ["EV-beacon-1", "EV-beacon-2"]
    assert lines["Investigation"]["evidence"] == [DECISIVE]
    assert lines["Investigation"]["on_entities"] == ["host:fs-9"]

    # The decision-based line names the decision.
    assert lines["Response"]["chose_action"] == "read_logs"
    assert lines["Response"]["plan_actions"] == ["isolate_host"]


def test_a_wrong_diagnosis_names_what_rules_it_out() -> None:
    """Being told the right answer teaches less than being shown the specific
    observation that killed the answer you were drawn to."""
    result = marked(diagnosis="A backup job", action="isolate_host", investigated=[])
    diagnosis = next(row for row in result["breakdown"] if row["name"] == "Diagnosis")
    assert diagnosis["points"] == 0
    assert diagnosis["contradicted_by"] == [DECISIVE]


def test_a_correct_diagnosis_has_nothing_to_contradict() -> None:
    result = marked(diagnosis="A workstation", action="isolate_host", investigated=["host:fs-9"])
    diagnosis = next(row for row in result["breakdown"] if row["name"] == "Diagnosis")
    assert diagnosis["contradicted_by"] == []


def test_opening_everything_leaves_the_missed_list_empty() -> None:
    result = marked(
        diagnosis="A workstation",
        action="isolate_host",
        investigated=["host:ws-1", "host:fs-9"],
    )
    assert result["debrief"]["missed"] == []
    assert len(result["debrief"]["opened"]) == 2


# --- R102: the board and the sentence cannot disagree -------------------------

SECOND = "EV-decisive-2"


def a_two_proof_incident() -> Incident:
    """The decoy is ruled out by two records on two different entities."""
    incident = an_incident()
    incident.hypotheses[1].contradicted_by = [DECISIVE, SECOND]
    return incident


class _TwoProofGraph(_Graph):
    EVENTS = {
        "host:ws-1": [{"id": "EV-beacon-1"}, {"id": "EV-beacon-2"}, {"id": SECOND}],
        "host:fs-9": [{"id": DECISIVE}, {"id": "EV-quiet"}],
    }


def _marked_two_proof(graph, investigated: list[str]) -> dict:
    incident = a_two_proof_incident()
    from app.game import _choice_id

    chosen = _choice_id(incident.hypotheses[0].statement)
    return score(
        incident, graph, diagnosis_id=chosen, action_id="isolate_host", investigated=investigated
    )


def test_opening_one_of_two_decisive_entities_earns_the_marks_and_says_so() -> None:
    """The reviewer scored 100, read "you opened the evidence that rules out
    the plausible alternative", and beside it a board marking a different
    decisive entity as never opened. Both true, read as a contradiction. The
    marks stand — any one decisive record rules the decoy out — and the
    sentence now names the other entity as *also* holding it."""
    verdict = _marked_two_proof(_TwoProofGraph(), investigated=["host:fs-9"])
    line = next(row for row in verdict["breakdown"] if row["name"] == "Investigation")
    assert line["points"] == line["of"]
    assert "on host:fs-9" in line["note"]
    assert "also on host:ws-1, which you did not open" in line["note"]

    board = verdict["debrief"]
    opened = {row["entity_key"]: row for row in board["opened"]}
    missed = {row["entity_key"]: row for row in board["missed"]}
    assert opened["host:fs-9"]["decisive"] is True
    assert missed["host:ws-1"]["decisive"] is True
    assert missed["host:ws-1"]["decisive_evidence"] == [SECOND]


def test_the_board_uses_the_same_resolver_as_the_score() -> None:
    """The old board intersected each entity's eight most recent events with
    the decisive set; the score read the record's own entity. A decisive record
    older than eight events was credited by one and denied by the other."""

    class _DeepGraph(_Graph):
        EVENTS = {
            "host:ws-1": [{"id": "EV-beacon-1"}, {"id": "EV-beacon-2"}],
            # The decisive record is the ninth event — outside the window.
            "host:fs-9": [{"id": f"EV-noise-{i}"} for i in range(8)] + [{"id": DECISIVE}],
        }

    incident = an_incident()
    from app.game import _choice_id

    chosen = _choice_id(incident.hypotheses[0].statement)
    verdict = score(
        incident, _DeepGraph(), diagnosis_id=chosen, action_id="isolate_host",
        investigated=["host:fs-9"],
    )
    line = next(row for row in verdict["breakdown"] if row["name"] == "Investigation")
    assert line["points"] == line["of"], "the score credits the opened record"
    opened = {row["entity_key"]: row for row in verdict["debrief"]["opened"]}
    assert opened["host:fs-9"]["decisive"] is True, "and so must the board"
    assert opened["host:fs-9"]["decisive_evidence"] == [DECISIVE]
