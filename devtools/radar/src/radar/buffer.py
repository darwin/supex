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

    def append(self, event: LogEvent) -> None:
        """Append an event. Silently evicts oldest when full."""
        self._events.append(event)

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
        return {e.source for e in self._events}
