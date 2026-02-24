"""Plain text log format parser (fallback).

Attempts to extract timestamp and level from common patterns.
Supports multiline continuation for stacktraces.
"""

from __future__ import annotations

import re
from datetime import datetime

from . import BaseParser, ParsedRecord, register_parser

# ANSI escape sequence pattern
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Common timestamp patterns at start of line
_TS_PATTERNS: list[tuple[re.Pattern, str | None]] = [
    # ISO-8601: 2025-01-15T10:30:45.123
    (re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)"), "%Y-%m-%dT%H:%M:%S.%f"),
    # ISO-8601 no fractional: 2025-01-15T10:30:45
    (re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"), "%Y-%m-%dT%H:%M:%S"),
    # Space-separated with comma millis: 2025-01-15 10:30:45,123
    (re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)"), "%Y-%m-%d %H:%M:%S,%f"),
    # Space-separated with dot millis: 2025-01-15 10:30:45.123
    (re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)"), "%Y-%m-%d %H:%M:%S.%f"),
    # Space-separated no millis: 2025-01-15 10:30:45
    (re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"), "%Y-%m-%d %H:%M:%S"),
    # Syslog-style: Jan 15 10:30:45
    (re.compile(r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})"), None),
]

# Log level keywords
_LEVEL_RE = re.compile(
    r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\b",
    re.IGNORECASE,
)

# Syslog month names
_SYSLOG_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Multiline continuation patterns
_CONTINUATION_RE = re.compile(
    r"^(\s+"              # Leading whitespace
    r"|Caused by:"        # Java chained exceptions
    r"|Traceback "        # Python traceback header
    r"|\s+at\s+"          # Java stack frame
    r"|\s+File\s+"        # Python stack frame
    r"|\.\.\.\s+\d+\s+more"  # Java truncated frames
    r")",
)


class PlainParser(BaseParser):
    """Fallback parser for plain text logs."""

    def parse_line(self, raw: str) -> ParsedRecord | None:
        cleaned = _ANSI_RE.sub("", raw).strip()
        if not cleaned:
            return None

        timestamp, rest = _extract_timestamp(cleaned)
        level, rest = _extract_level(rest)

        return ParsedRecord(
            timestamp=timestamp,
            level=level,
            message=rest.strip() or cleaned,
            structured=None,
        )

    def is_continuation(self, line: str) -> bool:
        cleaned = _ANSI_RE.sub("", line)
        return bool(_CONTINUATION_RE.match(cleaned))


def _extract_timestamp(text: str) -> tuple[datetime | None, str]:
    """Try to extract a timestamp from the start of text."""
    for pattern, fmt in _TS_PATTERNS:
        m = pattern.match(text)
        if m:
            ts_str = m.group(1)
            rest = text[m.end():].lstrip(" -:")
            if fmt:
                try:
                    return datetime.strptime(ts_str, fmt), rest
                except ValueError:
                    continue
            else:
                # Syslog format
                ts = _parse_syslog_ts(ts_str)
                if ts:
                    return ts, rest
    return None, text


def _parse_syslog_ts(ts_str: str) -> datetime | None:
    """Parse syslog-style timestamp (Jan 15 10:30:45)."""
    parts = ts_str.split()
    if len(parts) < 3:
        return None
    month = _SYSLOG_MONTHS.get(parts[0])
    if not month:
        return None
    try:
        day = int(parts[1])
        time_parts = parts[2].split(":")
        return datetime(
            year=datetime.now().year,
            month=month,
            day=day,
            hour=int(time_parts[0]),
            minute=int(time_parts[1]),
            second=int(time_parts[2]),
        )
    except (ValueError, IndexError):
        return None


def _extract_level(text: str) -> tuple[str | None, str]:
    """Try to extract a log level from text."""
    m = _LEVEL_RE.search(text)
    if m:
        level = m.group(1).upper()
        # Normalize WARNING -> WARN, CRITICAL -> FATAL
        if level == "WARNING":
            level = "WARN"
        elif level == "CRITICAL":
            level = "FATAL"
        # Remove the level token from the remaining text
        rest = text[:m.start()] + text[m.end():]
        return level, rest.strip(" -:")
    return None, text


register_parser("plain", PlainParser)
