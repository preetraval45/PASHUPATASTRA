"""Buddhi — hypotheses, suppression, change correlation, causal chains.

The centre of gravity here is what the layer *refuses* to surface. A reasoning
module is easy to test on the happy path and the happy path is not where it hurts
anyone: the failure that matters is a fluent, confident, uncited claim reaching an
operator at 3am, so most of these tests are about that.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pashupatastra.events import (
    DeploymentPayload,
    EntityKind,
    EntityRef,
    Event,
    EventClass,
    MetricPayload,
    Provenance,
)
from pashupatastra.gateway import Gateway, ModelRequest, Usage
from pashupatastra.incidents import Hypothesis
from pashupatastra.reasoning import (
    Reasoner,
    Reasoning,
    SuppressionReason,
    correlate_changes,
    score_diagnoses,
)
from pashupatastra.smriti import MemoryKind, MemoryRecord, Outcome, Smriti

T0 = datetime(2026, 8, 17, 14, 0, 0).astimezone()


def an_event(
    event_id: str,
    *,
    at: datetime = T0,
    event_class: EventClass = EventClass.METRIC,
    service: str = "checkout-api",
    payload: Any = None,
) -> Event:
    return Event(
        id=event_id,
        event_class=event_class,
        source="test",
        occurred_at=at,
        observed_at=at,
        entity_ref=EntityRef(kind=EntityKind.SERVICE, id=service, name=service),
        provenance=Provenance(source_system="test"),
        payload=payload
        or MetricPayload(name="connection_pool_saturation", value=0.98),
    )


def a_deploy(event_id: str, *, at: datetime, version: str = "v4.21") -> Event:
    return an_event(
        event_id,
        at=at,
        event_class=EventClass.DEPLOYMENT,
        payload=DeploymentPayload(service="checkout-api", version=version),
    )


class ScriptedProvider:
    """Returns whatever hypotheses the test scripts, so admission can be driven."""

    name = "scripted"
    model = "scripted-0"

    def __init__(self, hypotheses: list[dict[str, Any]]) -> None:
        self.hypotheses = hypotheses
        self.last_request: ModelRequest | None = None

    def complete(self, prompt: str, request: ModelRequest) -> tuple[dict[str, Any], Usage]:
        self.last_request = request
        return {"hypotheses": self.hypotheses}, Usage(input_tokens=10, output_tokens=5)


def reasoner_for(hypotheses: list[dict[str, Any]]) -> tuple[Reasoner, ScriptedProvider]:
    provider = ScriptedProvider(hypotheses)
    return Reasoner(Gateway(provider)), provider


# --- citation verification: the load-bearing check ---------------------------


def test_a_fabricated_citation_suppresses_the_whole_hypothesis() -> None:
    """The dangerous failure: it satisfies every structural check.

    The schema forces a citation to be *present*; only this checks it is *real*.
    A fabricated ref is worse than a missing one — a missing one is visibly
    ungrounded, a fabricated one is indistinguishable from a good one until an
    operator clicks it.
    """
    reasoner, _ = reasoner_for(
        [{"statement": "Pool exhausted", "confidence": 0.9, "evidence_refs": ["evt-99"]}]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])

    assert result.hypotheses == []
    assert result.suppressed[0].reason is SuppressionReason.FABRICATED_CITATION
    assert "evt-99" in result.suppressed[0].detail


def test_a_partly_fabricated_hypothesis_is_dropped_not_trimmed() -> None:
    """Stripping the bad ref would leave the claim standing on evidence the model
    did not actually have — that is the failure, not the citation formatting."""
    reasoner, _ = reasoner_for(
        [
            {
                "statement": "Pool exhausted",
                "confidence": 0.9,
                "evidence_refs": ["evt-1", "evt-99"],
            }
        ]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert result.hypotheses == []


def test_citations_are_checked_against_exactly_what_the_model_was_shown() -> None:
    """If the shown set and the checked set ever diverged, verification would
    silently start passing things it should reject."""
    reasoner, provider = reasoner_for(
        [{"statement": "x", "confidence": 0.5, "evidence_refs": ["evt-1"]}]
    )
    events = [an_event("evt-1"), an_event("evt-2")]
    reasoner.analyse("inc-1", events)

    shown = {item.ref for item in provider.last_request.evidence}
    assert shown == {"evt-1", "evt-2"}


def test_a_verified_hypothesis_survives() -> None:
    reasoner, _ = reasoner_for(
        [{"statement": "Pool exhausted", "confidence": 0.8, "evidence_refs": ["evt-1"]}]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].evidence == ["evt-1"]


# --- suppression, and its visibility -----------------------------------------


def test_an_uncited_hypothesis_is_suppressed_not_surfaced_quietly() -> None:
    """Low confidence is not the answer: a low-confidence hypothesis on screen is
    read as a lead, and someone spends an hour on it."""
    reasoner, _ = reasoner_for(
        [{"statement": "Probably the database", "confidence": 0.2, "evidence_refs": []}]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert result.hypotheses == []
    assert result.suppressed[0].reason is SuppressionReason.NO_EVIDENCE


def test_suppression_is_counted_and_attributable() -> None:
    """Silent suppression is its own failure mode — a layer that discards most of
    what it produces is broken, and nobody finds out unless the discards show."""
    reasoner, _ = reasoner_for(
        [
            {"statement": "good", "confidence": 0.8, "evidence_refs": ["evt-1"]},
            {"statement": "uncited", "confidence": 0.7, "evidence_refs": []},
            {"statement": "invented", "confidence": 0.7, "evidence_refs": ["nope"]},
            {"statement": "", "confidence": 0.7, "evidence_refs": ["evt-1"]},
        ]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])

    summary = result.summary()
    assert summary["proposed"] == 4
    assert summary["surfaced"] == 1
    assert summary["suppressed"] == 3
    assert summary["by_reason"] == {
        "no_evidence": 1,
        "fabricated_citation": 1,
        "empty_statement": 1,
    }
    assert result.suppression_rate == 0.75


def test_a_repeated_claim_is_dropped_because_repetition_reads_as_corroboration() -> None:
    reasoner, _ = reasoner_for(
        [
            {"statement": "Pool exhausted", "confidence": 0.8, "evidence_refs": ["evt-1"]},
            {"statement": "pool exhausted", "confidence": 0.7, "evidence_refs": ["evt-1"]},
        ]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert len(result.hypotheses) == 1
    assert result.suppressed[0].reason is SuppressionReason.DUPLICATE


def test_no_events_means_no_speculation() -> None:
    """Asking a model to explain an incident with no telemetry is asking it to
    invent one, and it would."""
    reasoner, provider = reasoner_for([{"statement": "x", "confidence": 1.0, "evidence_refs": []}])
    result = reasoner.analyse("inc-1", [])
    assert result == Reasoning()
    assert provider.last_request is None, "the model must not be called at all"


# --- contradiction ------------------------------------------------------------


def test_contradicting_evidence_is_preserved_so_the_system_shows_its_doubt() -> None:
    reasoner, _ = reasoner_for(
        [
            {
                "statement": "Pool exhausted",
                "confidence": 0.8,
                "evidence_refs": ["evt-1"],
                "contradicted_by": ["evt-2"],
            }
        ]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1"), an_event("evt-2")])
    assert result.hypotheses[0].contradicted_by == ["evt-2"]


def test_a_fabricated_contradiction_is_dropped_without_killing_the_hypothesis() -> None:
    """A bad counter-ref weakens a claim. Rejecting the whole hypothesis for one
    would let a fabrication suppress a well-supported finding — the opposite of
    the intent."""
    reasoner, _ = reasoner_for(
        [
            {
                "statement": "Pool exhausted",
                "confidence": 0.8,
                "evidence_refs": ["evt-1"],
                "contradicted_by": ["evt-404"],
            }
        ]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].contradicted_by == []


# --- change correlation (deterministic) ---------------------------------------


def test_a_deploy_before_onset_is_offered_as_a_candidate() -> None:
    events = [a_deploy("dep-1", at=T0 - timedelta(minutes=18)), an_event("evt-1", at=T0)]
    changes = correlate_changes(events, onset=T0)
    assert len(changes) == 1
    assert changes[0].version == "v4.21"
    assert round(changes[0].seconds_before_onset) == 1080


def test_a_deploy_after_onset_cannot_be_a_cause() -> None:
    """Offering it invites exactly the post-hoc reasoning this prevents."""
    events = [a_deploy("dep-1", at=T0 + timedelta(minutes=5))]
    assert correlate_changes(events, onset=T0) == []


def test_an_old_deploy_falls_outside_the_lookback() -> None:
    events = [a_deploy("dep-1", at=T0 - timedelta(hours=6))]
    assert correlate_changes(events, onset=T0) == []


def test_candidates_are_nearest_first() -> None:
    events = [
        a_deploy("far", at=T0 - timedelta(minutes=25), version="v4.19"),
        a_deploy("near", at=T0 - timedelta(minutes=2), version="v4.21"),
    ]
    assert [c.version for c in correlate_changes(events, onset=T0)] == ["v4.21", "v4.19"]


def test_a_deploy_is_evidence_and_never_a_conclusion() -> None:
    """The Phase 1 connector rule, held at the layer most tempted to break it:
    'a deploy happened' must not become 'a deploy broke something'."""
    reasoner, provider = reasoner_for([])
    events = [a_deploy("dep-1", at=T0 - timedelta(minutes=5)), an_event("evt-1", at=T0)]
    result = reasoner.analyse("inc-1", events, onset=T0)

    assert len(result.changes) == 1
    assert result.hypotheses == [], "a deploy alone must not produce a hypothesis"
    # It is offered to the model as citable evidence, with its timing spelled out.
    deploy_evidence = next(e for e in provider.last_request.evidence if e.ref == "dep-1")
    assert "before onset" in deploy_evidence.content


# --- causal chain -------------------------------------------------------------


def test_the_chain_is_ordered_by_observation_not_by_the_models_narrative() -> None:
    """A model asked for a sequence produces one whether or not the timestamps
    agree. When they disagree, the timestamps are right."""
    early = an_event("early", at=T0)
    late = an_event("late", at=T0 + timedelta(minutes=3))
    reasoner, _ = reasoner_for(
        [
            {
                "statement": "cascade",
                "confidence": 0.9,
                # Deliberately reversed relative to real time.
                "evidence_refs": ["late", "early"],
            }
        ]
    )
    result = reasoner.analyse("inc-1", [early, late])
    assert [link.evidence[0] for link in result.causal_chain] == ["early", "late"]


def test_every_chain_link_cites_an_event() -> None:
    reasoner, _ = reasoner_for(
        [{"statement": "x", "confidence": 0.9, "evidence_refs": ["evt-1"]}]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert result.causal_chain
    assert all(link.evidence for link in result.causal_chain)


def test_a_suppressed_top_hypothesis_leaves_no_chain_behind() -> None:
    """The chain is built from admitted hypotheses only, so it cannot be the
    place an unverified ref sneaks back in."""
    reasoner, _ = reasoner_for(
        [{"statement": "invented", "confidence": 0.99, "evidence_refs": ["ghost"]}]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert result.causal_chain == []


# --- ranking and bounds -------------------------------------------------------


def test_hypotheses_are_ranked_by_confidence() -> None:
    reasoner, _ = reasoner_for(
        [
            {"statement": "weak", "confidence": 0.2, "evidence_refs": ["evt-1"]},
            {"statement": "strong", "confidence": 0.9, "evidence_refs": ["evt-1"]},
        ]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert [h.statement for h in result.hypotheses] == ["strong", "weak"]
    assert result.top.statement == "strong"


def test_the_list_is_bounded() -> None:
    """More than a handful is a wall of text that pushes the operator back to
    reading raw telemetry — the thing this replaces."""
    reasoner, _ = reasoner_for(
        [
            {"statement": f"h{i}", "confidence": 0.5, "evidence_refs": ["evt-1"]}
            for i in range(12)
        ]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert len(result.hypotheses) == 5


def test_out_of_range_confidence_is_clamped_not_rejected() -> None:
    """A confidence of 1.4 is a formatting error, not grounds to discard a
    well-cited claim — but it must not reach a risk score unclamped."""
    reasoner, _ = reasoner_for(
        [{"statement": "x", "confidence": 1.4, "evidence_refs": ["evt-1"]}]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert result.hypotheses[0].confidence == 1.0


# --- the boundary -------------------------------------------------------------


def test_reasoning_never_learns_which_model_answered() -> None:
    """What lets the same reasoning run against Bedrock, a direct API, or the
    deterministic stub in the benchmark.

    Checked at the import graph rather than by scanning for strings: the module
    is free to *name* a provider in its prose, and a substring check would flag
    the sentence above while missing an aliased import.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "pashupatastra" / "reasoning.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    assert not imported & {"anthropic", "boto3", "botocore", "openai"}


def test_reasoning_depends_only_on_the_gateway_abstraction() -> None:
    """The Reasoner takes a `Gateway`, not a provider or a client — so swapping
    the model is a wiring change and never a reasoning change."""
    import typing

    # `from __future__ import annotations` makes annotations strings, so they
    # have to be resolved rather than compared as written.
    hints = typing.get_type_hints(Reasoner.__init__)
    assert hints["gateway"] is Gateway


# --- memory in the loop -------------------------------------------------------


def a_memory_store(*, outcome: Outcome | None = None, entities: tuple[str, ...] = ()) -> Smriti:
    store = Smriti()
    store.remember(
        MemoryRecord(
            id="INC-42",
            tenant="acme",
            kind=MemoryKind.INCIDENT,
            text="connection pool exhausted on checkout-api after a deploy",
            source="incident-store",
            at=T0 - timedelta(days=30),
            entities=frozenset(entities or ("service:checkout-api",)),
            signals=frozenset(("connection_pool_saturation",)),
            outcome=outcome,
        )
    )
    return store


def test_a_prior_incident_is_offered_to_the_model_as_citable_evidence() -> None:
    provider = ScriptedProvider([])
    reasoner = Reasoner(Gateway(provider), memory=a_memory_store(), tenant="acme")
    result = reasoner.analyse("INC-NEW", [an_event("evt-1")])

    refs = {item.ref for item in provider.last_request.evidence}
    assert "INC-42" in refs
    assert [r.record.id for r in result.precedents] == ["INC-42"]


def test_a_wrong_prior_diagnosis_travels_with_the_recollection() -> None:
    """A model shown "this resembles INC-42", without being told INC-42 was
    misdiagnosed, will confidently repeat the earlier mistake and cite history
    while doing it."""
    provider = ScriptedProvider([])
    store = a_memory_store(outcome=Outcome(resolved=True, diagnosis_correct=False))
    Reasoner(Gateway(provider), memory=store, tenant="acme").analyse("INC-NEW", [an_event("evt-1")])

    memory_evidence = next(e for e in provider.last_request.evidence if e.ref == "INC-42")
    assert "WARNING" in memory_evidence.content
    assert "wrong" in memory_evidence.content.lower()


def test_a_non_precedent_recollection_is_labelled_as_such_to_the_model() -> None:
    provider = ScriptedProvider([])
    store = a_memory_store(entities=("service:somewhere-else",))
    store._by_tenant["acme"]["INC-42"].signals = frozenset()  # no shared structure

    result = Reasoner(Gateway(provider), memory=store, tenant="acme").analyse(
        "INC-NEW", [an_event("evt-1")]
    )
    if result.recalled:  # only if the text alone cleared the similarity floor
        assert result.precedents == []
        evidence = next(e for e in provider.last_request.evidence if e.ref == "INC-42")
        assert "not a precedent" in evidence.content


def test_a_prior_incident_is_trusted_but_an_unpromoted_runbook_is_not() -> None:
    """Past incidents are platform-authored; a runbook is a document, and a
    document is untrusted input until someone vouches for it."""
    provider = ScriptedProvider([])
    store = a_memory_store()
    store.ingest_document(
        "acme",
        "RB-1",
        "connection pool exhausted on checkout-api: restart the service",
        MemoryKind.RUNBOOK,
        "git://runbooks",
        T0,
        entities=["service:checkout-api"],
    )
    Reasoner(Gateway(provider), memory=store, tenant="acme").analyse("INC-NEW", [an_event("evt-1")])

    by_ref = {e.ref: e for e in provider.last_request.evidence}
    assert by_ref["INC-42"].trusted is True
    assert by_ref["RB-1"].trusted is False


def test_an_incident_cannot_recall_itself_as_its_own_precedent() -> None:
    """Otherwise an incident already written to memory cites its own guess."""
    provider = ScriptedProvider([])
    result = Reasoner(Gateway(provider), memory=a_memory_store(), tenant="acme").analyse(
        "INC-42", [an_event("evt-1")]
    )
    assert result.recalled == []


def test_memory_is_optional() -> None:
    """The reasoner works without it — memory improves diagnosis, it is not a
    precondition for having one."""
    reasoner, _ = reasoner_for(
        [{"statement": "x", "confidence": 0.5, "evidence_refs": ["evt-1"]}]
    )
    result = reasoner.analyse("inc-1", [an_event("evt-1")])
    assert result.recalled == []
    assert len(result.hypotheses) == 1


def test_a_hypothesis_may_cite_a_recalled_incident() -> None:
    """The point of putting memory in the evidence set: a precedent becomes a
    verifiable citation rather than a hint the model half-remembers."""
    provider = ScriptedProvider(
        [
            {
                "statement": "Same pool exhaustion as INC-42",
                "confidence": 0.8,
                "evidence_refs": ["evt-1", "INC-42"],
            }
        ]
    )
    reasoner = Reasoner(Gateway(provider), memory=a_memory_store(), tenant="acme")
    result = reasoner.analyse("INC-NEW", [an_event("evt-1")])
    assert result.hypotheses[0].evidence == ["evt-1", "INC-42"]


def test_memory_recall_respects_tenant() -> None:
    provider = ScriptedProvider([])
    reasoner = Reasoner(Gateway(provider), memory=a_memory_store(), tenant="globex")
    result = reasoner.analyse("INC-NEW", [an_event("evt-1")])
    assert result.recalled == []


# --- measuring the Phase 2 exit criterion ------------------------------------


def a_reasoning(statement: str | None, refs: list[str] | None = None) -> Reasoning:
    result = Reasoning(proposed=1 if statement else 0)
    if statement:
        result.hypotheses = [
            Hypothesis(statement=statement, confidence=0.8, evidence=refs or ["evt-1"])
        ]
    return result


def test_top1_accuracy_counts_abstentions_against_it() -> None:
    """A system that declines everything is not 100% accurate, it is unused."""
    quality = score_diagnoses(
        [
            (a_reasoning("connection pool exhausted"), "connection pool"),
            (a_reasoning("disk full"), "connection pool"),
            (a_reasoning(None), "connection pool"),
        ]
    )
    assert quality.correct == 1
    assert quality.incorrect == 1
    assert quality.abstained == 1
    assert quality.top1_accuracy == round(1 / 3, 4)


def test_precision_when_answering_is_reported_separately() -> None:
    """The gap between the two numbers is the cost of caution — the figure to
    read when deciding whether abstention is tuned sensibly."""
    quality = score_diagnoses(
        [
            (a_reasoning("connection pool exhausted"), "connection pool"),
            (a_reasoning(None), "connection pool"),
        ]
    )
    assert quality.top1_accuracy == 0.5
    assert quality.precision_when_answering == 1.0


def test_grounding_is_reported_beside_accuracy_not_folded_into_it() -> None:
    """The exit criterion is two claims. An accurate diagnosis that cannot be
    traced to its telemetry fails the second regardless of the first, and one
    combined score would hide exactly that case."""
    quality = score_diagnoses([(a_reasoning("connection pool"), "connection pool")])
    assert quality.fully_grounded
    assert "top1_accuracy" in quality.summary()
    assert "fully_grounded" in quality.summary()


def test_the_match_rule_is_a_parameter_not_a_hard_coded_answer() -> None:
    """Judging semantic equivalence is its own research problem; baking in a weak
    answer would quietly cap the measured accuracy of every later improvement."""
    quality = score_diagnoses(
        [(a_reasoning("the pool ran dry"), "connection pool exhausted")],
        matches=lambda h, cause: "pool" in h.statement,
    )
    assert quality.correct == 1


def test_usage_is_attributed_to_the_incident() -> None:
    reasoner, _ = reasoner_for(
        [{"statement": "x", "confidence": 0.5, "evidence_refs": ["evt-1"]}]
    )
    reasoner.analyse("inc-42", [an_event("evt-1")], agent="sati.analyst")
    assert reasoner.gateway.accountant.for_incident("inc-42").total_tokens == 15
