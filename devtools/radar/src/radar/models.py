"""Core data models for Radar log aggregator."""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime


class Level(enum.IntEnum):
    """Log severity level with comparison ordering."""

    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    FATAL = 4


@dataclass
class LogEvent:
    """Single normalized log event from any source."""

    eid: str
    timestamp: datetime
    level: Level
    source: str
    source_path: str
    message: str
    structured: dict | None = None
    raw: str = ""
    multiline: bool = False

    @staticmethod
    def make_eid() -> str:
        """Generate a short event ID."""
        return uuid.uuid4().hex[:6]


@dataclass
class FilterSpec:
    """Active filter state for log views."""

    sources: list[str] = field(default_factory=list)
    min_level: Level = Level.DEBUG
    pattern: re.Pattern | None = None
    since: datetime | None = None
    until: datetime | None = None

    def matches(self, event: LogEvent) -> bool:
        """Check if an event passes all active filters."""
        if self.sources and event.source not in self.sources:
            return False
        if event.level < self.min_level:
            return False
        if self.pattern and not self.pattern.search(event.message):
            return False
        if self.since and event.timestamp < self.since:
            return False
        if self.until and event.timestamp > self.until:
            return False
        return True
