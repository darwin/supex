"""Pipe-separated log format parser.

Format: timestamp|level|source|message|optional_json_payload
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from . import BaseParser, ParsedRecord, register_parser

# ANSI escape sequence pattern
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class PipeParser(BaseParser):
    """Parser for pipe-separated log lines."""

    def parse_line(self, raw: str) -> ParsedRecord | None:
        cleaned = _ANSI_RE.sub("", raw).strip()
        if not cleaned:
            return None

        parts = cleaned.split("|", maxsplit=4)
        if len(parts) < 3:
            return None

        timestamp = _parse_timestamp(parts[0].strip())
        level = parts[1].strip().upper() or None
        # parts[2] is source — consumed by normalizer from config, skip here
        message = parts[3].strip() if len(parts) > 3 else ""

        structured = None
        if len(parts) > 4 and parts[4].strip():
            try:
                structured = json.loads(parts[4].strip())
            except (json.JSONDecodeError, ValueError):
                # Treat extra field as part of message
                message = f"{message} | {parts[4].strip()}" if message else parts[4].strip()

        return ParsedRecord(
            timestamp=timestamp,
            level=level,
            message=message,
            structured=structured,
        )


def _parse_timestamp(s: str) -> datetime | None:
    """Try common timestamp formats."""
    for fmt in (
        "%Y-%m-%d %H:%M:%S,%f",  # 2025-01-15 10:30:45,123
        "%Y-%m-%d %H:%M:%S.%f",  # 2025-01-15 10:30:45.123
        "%Y-%m-%d %H:%M:%S",     # 2025-01-15 10:30:45
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO-8601
        "%Y-%m-%dT%H:%M:%S",     # ISO-8601 no fractional
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


register_parser("pipe", PipeParser)
