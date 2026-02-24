"""JSON lines log format parser."""

from __future__ import annotations

import json
import re
from datetime import datetime

from . import BaseParser, ParsedRecord, register_parser

# ANSI escape sequence pattern
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class JsonlParser(BaseParser):
    """Parser for JSON-lines log files."""

    def parse_line(self, raw: str) -> ParsedRecord | None:
        cleaned = _ANSI_RE.sub("", raw).strip()
        if not cleaned:
            return None

        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None

        timestamp = _extract_timestamp(data)
        level = _extract_level(data)
        message = _extract_message(data)
        structured = data  # Preserve full payload

        return ParsedRecord(
            timestamp=timestamp,
            level=level,
            message=message,
            structured=structured,
        )


def _extract_timestamp(data: dict) -> datetime | None:
    """Extract and parse timestamp from known field names."""
    for key in ("timestamp", "ts", "time", "@timestamp"):
        val = data.get(key)
        if val is None:
            continue
        if isinstance(val, str):
            for fmt in (
                "%Y-%m-%d %H:%M:%S,%f",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
            ):
                try:
                    return datetime.strptime(val, fmt)
                except ValueError:
                    continue
    return None


def _extract_level(data: dict) -> str | None:
    """Extract log level from known field names."""
    for key in ("level", "severity", "loglevel"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().upper()
    return None


def _extract_message(data: dict) -> str:
    """Extract or derive a message from JSON payload.

    For protocol/event payloads without 'message', derives a summary
    from known keys (method, event, error, result).
    """
    # Direct message field
    for key in ("message", "msg"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # Derive summary from known keys
    parts = []
    if "method" in data:
        parts.append(f"method={data['method']}")
    if "event" in data:
        parts.append(f"event={data['event']}")
    if "error" in data:
        err = data["error"]
        if isinstance(err, dict):
            parts.append(f"error={err.get('message', err)}")
        else:
            parts.append(f"error={err}")
    if "result" in data:
        result = data["result"]
        if isinstance(result, str):
            parts.append(f"result={result}")
        else:
            parts.append("result=<object>")

    if parts:
        return " ".join(parts)

    # Last resort: stringify top-level keys
    return " ".join(f"{k}={v}" for k, v in list(data.items())[:4])


register_parser("jsonl", JsonlParser)
