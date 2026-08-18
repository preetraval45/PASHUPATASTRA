"""Smriti — memory, retrieval, and the ways recollection misleads.

The happy path (store a thing, find it again) is the easy half. These tests
concentrate on the three ways a memory layer does damage: leaking across tenants,
surfacing a precedent that isn't one, and recalling a past incident without
saying that its diagnosis was wrong.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pashupatastra.smriti import (
    HashingEmbedder,
    MatchBasis,
    MemoryKind,
    MemoryRecord,
    Outcome,
    Smriti,
    Trust,
    cosine,
    score_retrieval,
)

NOW = datetime(2026, 8, 17, 12, 0, 0).astimezone()


def a_memory(
    memory_id: str,
    *,
    tenant: str = "acme",
    text: str = "connection pool exhausted on checkout-api after deploy",
    entities: tuple[str, ...] = ("service:checkout-api",),
    signals: tuple[str, ...] = ("connection_pool_saturation",),
    at: datetime = NOW,
    outcome: Outcome | None = None,
    trust: Trust = Trust.UNTRUSTED,
) -> MemoryRecord:
    return MemoryRecord(
        id=memory_id,
        tenant=tenant,
        kind=MemoryKind.INCIDENT,
        text=text,
        source="incident-store",
        at=at,
        entities=frozenset(entities),
        signals=frozenset(signals),
        outcome=outcome,
        trust=trust,
    )


def a_store(*records: MemoryRecord) -> Smriti:
    store = Smriti()
    for record in records:
        store.remember(record)
    return store


# --- tenant isolation ---------------------------------------------------------


def test_recall_never_crosses_tenants() -> None:
    """Structural, from the first commit. Retrofitting it is how leaks happen."""
    store = a_store(a_memory("INC-1", tenant="acme"), a_memory("INC-2", tenant="globex"))

    acme = store.recall("acme", "connection pool exhausted", entities=["service:checkout-api"])
    assert [r.record.id for r in acme] == ["INC-1"]

    globex = store.recall("globex", "connection pool exhausted", entities=["service:checkout-api"])
    assert [r.record.id for r in globex] == ["INC-2"]


def test_a_memory_without_a_tenant_cannot_be_stored() -> None:
    with pytest.raises(ValueError, match="tenant"):
        a_store(a_memory("INC-1", tenant=""))


def test_an_unknown_tenant_recalls_nothing_rather_than_erroring() -> None:
    """An empty result is the correct answer for a tenant with no history — and
    it must not be distinguishable from a tenant that does not exist, or the
    error message becomes an enumeration oracle."""
    store = a_store(a_memory("INC-1", tenant="acme"))
    assert store.recall("nobody", "anything") == []


# --- the outcome is the valuable half ----------------------------------------


def test_a_wrong_prior_diagnosis_is_surfaced_as_a_warning() -> None:
    """Recalling a misdiagnosed incident without saying so lends the authority of
    history to a mistake, and the operator inherits it with more confidence than
    the person who originally made it."""
    store = a_store(
        a_memory(
            "INC-42",
            outcome=Outcome(resolved=True, diagnosis_correct=False, action_taken="restarted pods"),
        )
    )
    result = store.recall("acme", "pool exhausted", entities=["service:checkout-api"])[0]

    assert result.record.outcome.warning is not None
    assert "wrong" in result.describe().lower()
    assert "CAUTION" in result.describe()


def test_a_failed_remediation_is_a_warning_too() -> None:
    outcome = Outcome(resolved=True, verification_passed=False)
    assert outcome.warning is not None
    assert "verification" in outcome.warning


def test_an_unresolved_prior_incident_is_a_warning() -> None:
    assert Outcome(resolved=False).warning is not None


def test_a_clean_outcome_surfaces_what_fixed_it() -> None:
    store = a_store(
        a_memory(
            "INC-7",
            outcome=Outcome(
                resolved=True, diagnosis_correct=True, action_taken="rolled back v4.21"
            ),
        )
    )
    described = store.recall("acme", "pool exhausted", entities=["service:checkout-api"])[
        0
    ].describe()
    assert "rolled back v4.21" in described
    assert "CAUTION" not in described


def test_outcomes_are_attached_later_not_defaulted_to_resolved() -> None:
    """A memory stored without an outcome must be visibly incomplete — the
    outcome is usually known much later than the incident."""
    store = a_store(a_memory("INC-1"))
    assert store.recall("acme", "pool", entities=["service:checkout-api"])[0].record.outcome is None

    store.record_outcome("acme", "INC-1", Outcome(resolved=True, diagnosis_correct=True))
    assert store.recall("acme", "pool", entities=["service:checkout-api"])[0].record.outcome


# --- hybrid retrieval: why it matched matters --------------------------------


def test_the_same_entity_is_the_strongest_precedent() -> None:
    store = a_store(a_memory("INC-1"))
    result = store.recall("acme", "pool exhausted", entities=["service:checkout-api"])[0]
    assert result.basis is MatchBasis.SAME_ENTITY
    assert result.is_precedent


def test_the_same_failure_mode_elsewhere_is_a_different_claim() -> None:
    store = a_store(a_memory("INC-1", entities=("service:payments-api",)))
    result = store.recall(
        "acme",
        "pool exhausted",
        entities=["service:checkout-api"],
        signals=["connection_pool_saturation"],
    )[0]
    assert result.basis is MatchBasis.SAME_SIGNAL
    assert result.is_precedent
    assert "elsewhere" in result.describe()


def test_a_text_only_resemblance_is_not_a_precedent() -> None:
    """Pure vector search cannot tell these apart, because what distinguishes
    them is not in the prose. Saying "we have seen this before" on a coincidence
    of vocabulary is how a phrase becomes a claim about history."""
    store = a_store(a_memory("INC-1", entities=("service:unrelated",), signals=("disk_full",)))
    results = store.recall(
        "acme",
        "connection pool exhausted on checkout-api after deploy",
        entities=["service:checkout-api"],
        signals=["connection_pool_saturation"],
    )
    assert results[0].basis is MatchBasis.TEXT_ONLY
    assert not results[0].is_precedent
    assert store.precedents("acme", "connection pool exhausted on checkout-api after deploy") == []


def test_structure_outranks_vocabulary() -> None:
    """A strong text match must not outrank a weak structural one — the whole
    point of hybrid retrieval, and what a single blended score would lose."""
    store = a_store(
        # Near-identical wording, unrelated entity and signal.
        a_memory(
            "TEXT-TWIN",
            text="connection pool exhausted on checkout-api after deploy",
            entities=("service:somewhere-else",),
            signals=("unrelated_signal",),
        ),
        # Different wording, same entity.
        a_memory(
            "SAME-ENTITY",
            text="latency regression traced to a saturated worker queue",
            entities=("service:checkout-api",),
            signals=("queue_depth",),
        ),
    )
    results = store.recall(
        "acme",
        "connection pool exhausted on checkout-api after deploy",
        entities=["service:checkout-api"],
    )
    assert results[0].record.id == "SAME-ENTITY"
    assert results[0].similarity < results[1].similarity, "and it won despite worse text overlap"


def test_a_structural_match_survives_weak_text_similarity() -> None:
    """The asymmetry that makes this hybrid rather than filtered: shared
    structure is itself evidence, so it does not have to clear the text floor."""
    store = a_store(a_memory("INC-1", text="entirely unrelated wording about storage"))
    results = store.recall(
        "acme", "connection pool exhausted", entities=["service:checkout-api"]
    )
    assert len(results) == 1
    assert results[0].similarity < 0.35


# --- not inventing recollections ---------------------------------------------


def test_nothing_similar_returns_nothing() -> None:
    """A memory layer that produces a plausible precedent when it has none is an
    uncited hypothesis one layer down — and harder to catch, because "we have
    seen this before" is exactly what people stop questioning."""
    store = a_store(a_memory("INC-1", text="kubernetes node pressure eviction"))
    assert store.recall("acme", "certificate expiry on the load balancer") == []


def test_an_empty_store_recalls_nothing() -> None:
    assert Smriti().recall("acme", "anything") == []


def test_expired_memories_are_not_recalled() -> None:
    """Retention is enforced on read, so an expired memory cannot resurface
    because a pruning job did not run."""
    old = a_memory("INC-OLD", at=NOW - timedelta(days=200))
    store = a_store(old)
    assert store.recall("acme", "pool", entities=["service:checkout-api"], now=NOW) == []


def test_an_incident_does_not_recall_itself() -> None:
    store = a_store(a_memory("INC-1"))
    assert store.recall("acme", "pool", entities=["service:checkout-api"], exclude="INC-1") == []


# --- untrusted ingestion ------------------------------------------------------


def test_ingested_documents_arrive_untrusted() -> None:
    """A runbook is a document, and documents can be edited by anyone with
    repository access."""
    store = Smriti()
    record = store.ingest_document(
        tenant="acme",
        doc_id="RB-1",
        text="To resolve pool exhaustion, restart the service.",
        kind=MemoryKind.RUNBOOK,
        source="git://runbooks",
        at=NOW,
    )
    assert record.trust is Trust.UNTRUSTED


def test_there_is_no_way_to_ingest_straight_to_trusted() -> None:
    """A `trust=` parameter is a parameter someone passes VERIFIED to while
    wiring up an importer."""
    import inspect

    assert "trust" not in inspect.signature(Smriti.ingest_document).parameters


def test_promotion_requires_a_named_actor() -> None:
    store = Smriti()
    store.ingest_document("acme", "RB-1", "text", MemoryKind.RUNBOOK, "git", NOW)
    with pytest.raises(ValueError, match="named actor"):
        store.promote("acme", "RB-1", by="")


def test_promotion_records_who_vouched() -> None:
    store = Smriti()
    store.ingest_document("acme", "RB-1", "text", MemoryKind.RUNBOOK, "git", NOW)
    record = store.promote("acme", "RB-1", by="alice", note="checked against prod")
    assert record.trust is Trust.VERIFIED
    assert record.owner == "alice"
    assert "alice" in record.text


def test_promotion_across_tenants_is_impossible() -> None:
    store = Smriti()
    store.ingest_document("acme", "RB-1", "text", MemoryKind.RUNBOOK, "git", NOW)
    with pytest.raises(KeyError):
        store.promote("globex", "RB-1", by="mallory")


def test_trust_is_a_tiebreaker_not_a_relevance_signal() -> None:
    """A verified runbook about something else is still about something else."""
    store = a_store(
        a_memory("UNVERIFIED", trust=Trust.UNTRUSTED),
        a_memory("VERIFIED", trust=Trust.VERIFIED, entities=("service:elsewhere",),
                 signals=("other_signal",)),
    )
    results = store.recall("acme", "pool exhausted", entities=["service:checkout-api"])
    assert results[0].record.id == "UNVERIFIED", "structure beats trust"


# --- the embedder -------------------------------------------------------------


def test_the_local_embedder_is_deterministic() -> None:
    embedder = HashingEmbedder()
    assert embedder.embed(["pool exhausted"]) == embedder.embed(["pool exhausted"])


def test_similar_text_scores_higher_than_unrelated_text() -> None:
    embedder = HashingEmbedder()
    a, b, c = embedder.embed(
        [
            "connection pool exhausted on checkout-api",
            "connection pool exhaustion on checkout-api",
            "certificate expired on the load balancer",
        ]
    )
    assert cosine(a, b) > cosine(a, c)


def test_word_order_carries_some_weight() -> None:
    embedder = HashingEmbedder()
    a, b = embedder.embed(["pool exhausted", "exhausted pool"])
    assert cosine(a, b) < 1.0


def test_cosine_is_defensive_about_shape() -> None:
    assert cosine([], [1.0]) == 0.0
    assert cosine([1.0, 0.0], [1.0]) == 0.0


# --- measurement --------------------------------------------------------------


def test_retrieval_quality_reports_false_precedents_separately() -> None:
    """A missed precedent costs the operator time they would have spent anyway;
    a false one sends them confidently down a path that does not exist."""
    store = a_store(a_memory("INC-1"))
    found = store.recall("acme", "pool exhausted", entities=["service:checkout-api"])

    quality = score_retrieval([(found, "INC-1"), (found, "INC-OTHER")])
    assert quality.hits == 1
    assert quality.misses == 1
    assert quality.false_precedents == 1
    assert quality.recall_at_k == 0.5


def test_the_negative_case_is_scored() -> None:
    """Without it, a retriever that returns everything scores perfectly."""
    store = a_store(a_memory("INC-1", entities=("service:elsewhere",), signals=("other",)))
    found = store.recall("acme", "totally unrelated query about certificates")
    quality = score_retrieval([(found, None)])
    assert quality.hits == 1
    assert quality.false_precedents == 0


# --- the boundary -------------------------------------------------------------


def test_memory_imports_no_vendor_sdk() -> None:
    """Core runs on a laptop: the default embedder is local and dependency-free,
    and a hosted one plugs in behind the protocol."""
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "pashupatastra" / "smriti.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not imported & {"anthropic", "boto3", "botocore", "openai", "numpy"}
