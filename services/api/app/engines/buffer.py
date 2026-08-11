"""Ingestion buffer.

A telemetry spike must not stall reasoning. Without a buffer, a connector that
suddenly returns 50,000 events blocks the poll loop on database writes while the
incident it is reporting goes undiagnosed — the failure mode where the system is
busiest exactly when it most needs to think.

On AWS this becomes SQS (docs/DEPLOYMENT.md). The in-process implementation
exists so the semantics are defined and tested somewhere the benchmark can run
without a cloud, and so the SQS version has something to reproduce.

**Drops are counted and surfaced, never silent.** A buffer that quietly discards
under load turns "we saw nothing" and "we couldn't keep up" into the same
observation, and those demand opposite responses.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass
class BufferStats:
    accepted: int = 0
    dropped: int = 0
    high_water: int = 0
    batches: int = 0

    @property
    def healthy(self) -> bool:
        return self.dropped == 0

    def snapshot(self) -> dict[str, int | bool]:
        return {
            "accepted": self.accepted,
            "dropped": self.dropped,
            "high_water": self.high_water,
            "batches": self.batches,
            "healthy": self.healthy,
        }


class IngestionBuffer:
    """Bounded FIFO queue with an explicit drop policy.

    Drops the **oldest** item when full, not the newest. Under sustained
    overload the most recent telemetry is the most diagnostically useful: an
    operator needs to know what the system is doing now, not what it was doing
    when the backlog began.
    """

    def __init__(self, capacity: int = 50_000) -> None:
        self.capacity = capacity
        self._items: deque = deque()
        self._lock = threading.Lock()
        self.stats = BufferStats()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    @property
    def saturation(self) -> float:
        """0.0–1.0. Worth surfacing before it reaches 1.0: a buffer at 80% is a
        warning that perception is about to start losing data."""
        return len(self) / self.capacity if self.capacity else 0.0

    def offer(self, items: list) -> int:
        """Enqueue, dropping the oldest to make room. Returns the number dropped."""
        if not items:
            return 0

        dropped = 0
        with self._lock:
            for item in items:
                if len(self._items) >= self.capacity:
                    self._items.popleft()
                    dropped += 1
                self._items.append(item)

            self.stats.accepted += len(items)
            self.stats.dropped += dropped
            self.stats.high_water = max(self.stats.high_water, len(self._items))

        return dropped

    def drain(self, max_items: int = 1_000) -> list:
        """Take up to `max_items` oldest items.

        Bounded so a single drain cannot itself become the long-running write
        that the buffer exists to prevent.
        """
        with self._lock:
            if not self._items:
                return []
            take = min(max_items, len(self._items))
            batch = [self._items.popleft() for _ in range(take)]
            self.stats.batches += 1
            return batch

    def drain_all(self, max_items: int = 1_000):
        """Yield batches until empty. Each batch is a separate transaction, so a
        failure loses one batch rather than the whole backlog."""
        while True:
            batch = self.drain(max_items)
            if not batch:
                return
            yield batch


@dataclass
class BufferedIngestion:
    """Pairs a buffer with the sink that empties it."""

    buffer: IngestionBuffer = field(default_factory=IngestionBuffer)

    def submit(self, events: list) -> int:
        return self.buffer.offer(events)

    def flush(self, write: "callable", batch_size: int = 1_000) -> tuple[int, list[str]]:
        """Drain into `write`, batch by batch.

        A failing batch is reported and the drain continues: one bad batch must
        not strand the rest of the backlog behind it.
        """
        written, errors = 0, []
        for batch in self.buffer.drain_all(batch_size):
            try:
                written += write(batch)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        return written, errors
