"""In-memory ring buffer for live event storage."""

from __future__ import annotations

import re
from collections import deque

from .models import FilterSpec, LogEvent


class RingBuffer:
    """Fixed-size in-memory buffer of LogEvents."""

    def __init__(self, capacity: int = 10_000):
        self._capacity = capacity
        self._events: deque[LogEvent] = deque(maxlen=capacity)
        # Incremental source tracking: O(1) amortized instead of O(n)
        self._source_counts: dict[str, int] = {}

    def append(self, event: LogEvent) -> None:
        """Append an event. Silently evicts oldest when full."""
        # Track eviction before deque auto-evicts
        if len(self._events) == self._capacity:
            evicted = self._events[0]
            cnt = self._source_counts[evicted.source] - 1
            if cnt == 0:
                del self._source_counts[evicted.source]
            else:
                self._source_counts[evicted.source] = cnt
        self._events.append(event)
        self._source_counts[event.source] = self._source_counts.get(event.source, 0) + 1

    def get_recent(self, n: int) -> list[LogEvent]:
        """Return the most recent n events (oldest first)."""
        if n <= 0:
            return []
        if n >= len(self._events):
            return list(self._events)
        return list(self._events)[-n:]

    def filter(self, spec: FilterSpec) -> list[LogEvent]:
        """Return events matching the filter spec (oldest first)."""
        return [e for e in self._events if spec.matches(e)]

    def search(self, pattern: str) -> list[LogEvent]:
        """Regex/substring search over message + raw fields."""
        try:
            compiled = re.compile(pattern)
        except re.error:
            # Invalid regex — treat as literal substring
            return [
                e for e in self._events
                if pattern in e.message or pattern in e.raw
            ]
        return [
            e for e in self._events
            if compiled.search(e.message) or compiled.search(e.raw)
        ]

    @property
    def count(self) -> int:
        """Number of events currently in the buffer."""
        return len(self._events)

    @property
    def sources(self) -> set[str]:
        """Set of unique source IDs in the buffer."""
        return set(self._source_counts.keys())


class ObservableBuffer(RingBuffer):
    """RingBuffer with pending-event tracking for live consumers.

    After each append, the event is also placed into a pending list.
    Consumers (TUI timer, plain-mode loop) call ``drain_pending()``
    to collect new events since the last drain.
    """

    def __init__(self, capacity: int = 10_000):
        super().__init__(capacity)
        self._pending: list[LogEvent] = []

    def append(self, event: LogEvent) -> None:
        super().append(event)
        self._pending.append(event)

    def drain_pending(self) -> list[LogEvent]:
        """Return and clear all events appended since the last drain."""
        events = self._pending
        self._pending = []
        return events
