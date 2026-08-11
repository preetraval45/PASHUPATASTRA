"""Ingestion buffer.

The drop policy is the part worth pinning down. Everything else is a queue.
"""

from __future__ import annotations

from app.engines.buffer import BufferedIngestion, IngestionBuffer


def test_offer_and_drain_preserve_order() -> None:
    buffer = IngestionBuffer(capacity=10)
    buffer.offer([1, 2, 3])
    assert buffer.drain() == [1, 2, 3]


def test_drain_is_bounded() -> None:
    """A single drain must not become the long-running write the buffer exists
    to prevent."""
    buffer = IngestionBuffer(capacity=100)
    buffer.offer(list(range(50)))
    assert len(buffer.drain(max_items=10)) == 10
    assert len(buffer) == 40


def test_overflow_drops_the_oldest_not_the_newest() -> None:
    """Under sustained overload the newest telemetry is the most useful: an
    operator needs to know what the system is doing now."""
    buffer = IngestionBuffer(capacity=3)
    buffer.offer([1, 2, 3])
    dropped = buffer.offer([4, 5])

    assert dropped == 2
    assert buffer.drain() == [3, 4, 5]


def test_drops_are_counted_not_silent() -> None:
    """'We saw nothing' and 'we could not keep up' must never look the same."""
    buffer = IngestionBuffer(capacity=2)
    buffer.offer([1, 2, 3, 4])

    assert buffer.stats.dropped == 2
    assert not buffer.stats.healthy
    assert buffer.stats.snapshot()["dropped"] == 2


def test_saturation_is_visible_before_loss_begins() -> None:
    buffer = IngestionBuffer(capacity=10)
    buffer.offer(list(range(8)))
    assert buffer.saturation == 0.8
    assert buffer.stats.healthy, "nothing lost yet — this is a warning, not a failure"


def test_high_water_survives_draining() -> None:
    buffer = IngestionBuffer(capacity=100)
    buffer.offer(list(range(60)))
    buffer.drain(60)
    assert buffer.stats.high_water == 60, "peak pressure must remain visible after recovery"


def test_drain_all_yields_batches_until_empty() -> None:
    buffer = IngestionBuffer(capacity=100)
    buffer.offer(list(range(25)))
    batches = list(buffer.drain_all(max_items=10))
    assert [len(b) for b in batches] == [10, 10, 5]
    assert len(buffer) == 0


def test_flush_writes_everything() -> None:
    ingestion = BufferedIngestion(buffer=IngestionBuffer(capacity=100))
    ingestion.submit(list(range(30)))

    seen: list[int] = []

    def write(batch: list[int]) -> int:
        seen.extend(batch)
        return len(batch)

    written, errors = ingestion.flush(write, batch_size=10)
    assert written == 30
    assert errors == []
    assert seen == list(range(30))


def test_one_failing_batch_does_not_strand_the_backlog() -> None:
    ingestion = BufferedIngestion(buffer=IngestionBuffer(capacity=100))
    ingestion.submit(list(range(30)))

    written: list[int] = []
    calls = {"n": 0}

    def flaky(batch: list[int]) -> int:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("transient write failure")
        written.extend(batch)
        return len(batch)

    total, errors = ingestion.flush(flaky, batch_size=10)
    assert total == 20, "the two healthy batches still landed"
    assert len(errors) == 1
    assert len(written) == 20


def test_empty_offer_is_a_no_op() -> None:
    buffer = IngestionBuffer(capacity=10)
    assert buffer.offer([]) == 0
    assert buffer.stats.accepted == 0
