"""Normalizer: converts raw lines via a parser into LogEvent instances.

Handles multiline buffering and deterministic EID generation.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from .models import Level, LogEvent
from .parsers import BaseParser, ParsedRecord


# Level string -> Level enum mapping
_LEVEL_MAP: dict[str, Level] = {
    "DEBUG": Level.DEBUG,
    "INFO": Level.INFO,
    "WARN": Level.WARN,
    "WARNING": Level.WARN,
    "ERROR": Level.ERROR,
    "FATAL": Level.FATAL,
    "CRITICAL": Level.FATAL,
}


def _make_eid(source: str, timestamp: datetime | None, first_raw_line: str) -> str:
    """Generate deterministic EID: first 6 hex chars of sha256(source + ts_iso + raw)."""
    ts_iso = timestamp.isoformat() if timestamp else ""
    payload = source + ts_iso + first_raw_line
    return hashlib.sha256(payload.encode()).hexdigest()[:6]


class Normalizer:
    """Feeds raw lines through a parser and assembles LogEvent instances.

    Buffers continuation lines for multiline records (stacktraces, etc.).
    """

    def __init__(self, parser: BaseParser, source: str, source_path: str = "") -> None:
        self._parser = parser
        self._source = source
        self._source_path = source_path

        # Multiline buffer
        self._buffered_record: ParsedRecord | None = None
        self._buffered_raw: list[str] = []

    def feed_line(self, raw: str) -> LogEvent | None:
        """Feed a raw line. Returns LogEvent when a complete record is ready.

        Buffers continuation lines internally. A new non-continuation line
        flushes the previous buffer as a LogEvent.
        """
        # Check if this line is a continuation of the current buffer
        if self._buffered_record is not None and self._parser.is_continuation(raw):
            self._buffered_raw.append(raw)
            return None

        # Not a continuation — flush previous buffer if any
        flushed = self._flush_buffer()

        # Parse the new line
        record = self._parser.parse_line(raw)
        if record is None:
            # Parser didn't recognize the line — treat as standalone plain event
            if raw.strip():
                self._buffered_record = ParsedRecord(
                    timestamp=None,
                    level=None,
                    message=raw.strip(),
                    structured=None,
                )
                self._buffered_raw = [raw]
            return flushed

        # Start new buffer with this record
        self._buffered_record = record
        self._buffered_raw = [raw]
        return flushed

    def flush(self) -> LogEvent | None:
        """Flush any buffered multiline record."""
        return self._flush_buffer()

    def _flush_buffer(self) -> LogEvent | None:
        """Convert buffered record + raw lines into a LogEvent."""
        if self._buffered_record is None:
            return None

        record = self._buffered_record
        raw_lines = self._buffered_raw

        # Reset buffer
        self._buffered_record = None
        self._buffered_raw = []

        timestamp = record.timestamp or datetime.now()
        level = _LEVEL_MAP.get(record.level or "", Level.INFO)
        multiline = len(raw_lines) > 1
        raw_text = "\n".join(raw_lines)

        eid = _make_eid(self._source, record.timestamp, raw_lines[0])

        return LogEvent(
            eid=eid,
            timestamp=timestamp,
            level=level,
            source=self._source,
            source_path=self._source_path,
            message=record.message,
            structured=record.structured,
            raw=raw_text,
            multiline=multiline,
        )
