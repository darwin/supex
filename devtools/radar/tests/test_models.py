"""Tests for Radar data models."""

import re
from datetime import datetime

from radar.models import FilterSpec, Level, LogEvent


def _make_event(**overrides) -> LogEvent:
    defaults = {
        "eid": "abc123",
        "timestamp": datetime(2025, 6, 15, 12, 0, 0),
        "level": Level.INFO,
        "source": "test-source",
        "source_path": "/tmp/logs/test.log",
        "message": "test message",
    }
    defaults.update(overrides)
    return LogEvent(**defaults)


class TestLevel:
    def test_ordering(self):
        assert Level.DEBUG < Level.INFO < Level.WARN < Level.ERROR < Level.FATAL

    def test_equality(self):
        assert Level.INFO == Level.INFO
        assert Level.DEBUG != Level.ERROR

    def test_comparison_with_int(self):
        assert Level.DEBUG < Level.FATAL
        assert Level.FATAL > Level.DEBUG


class TestLogEvent:
    def test_creation_minimal(self):
        event = _make_event()
        assert event.eid == "abc123"
        assert event.level == Level.INFO
        assert event.source == "test-source"
        assert event.source_path == "/tmp/logs/test.log"
        assert event.message == "test message"

    def test_source_is_logical_id(self):
        event = _make_event(source="mcp-protocol", source_path="/workspace/.tmp/logs/mcp-protocol.jsonl")
        assert event.source == "mcp-protocol"
        assert event.source_path == "/workspace/.tmp/logs/mcp-protocol.jsonl"

    def test_defaults(self):
        event = _make_event()
        assert event.structured is None
        assert event.raw == ""
        assert event.multiline is False

    def test_structured_data(self):
        event = _make_event(structured={"request_id": "r-42", "node_id": "n-7"})
        assert event.structured["request_id"] == "r-42"

    def test_make_eid_uniqueness(self):
        ids = {LogEvent.make_eid() for _ in range(100)}
        assert len(ids) == 100

    def test_make_eid_length(self):
        eid = LogEvent.make_eid()
        assert len(eid) == 6


class TestFilterSpec:
    def test_defaults(self):
        f = FilterSpec()
        assert f.sources == []
        assert f.min_level == Level.DEBUG
        assert f.pattern is None
        assert f.since is None
        assert f.until is None

    def test_matches_all_by_default(self):
        f = FilterSpec()
        event = _make_event()
        assert f.matches(event)

    def test_filter_by_source(self):
        f = FilterSpec(sources=["mcp-protocol"])
        assert f.matches(_make_event(source="mcp-protocol"))
        assert not f.matches(_make_event(source="cli-driver"))

    def test_filter_by_level(self):
        f = FilterSpec(min_level=Level.WARN)
        assert not f.matches(_make_event(level=Level.DEBUG))
        assert not f.matches(_make_event(level=Level.INFO))
        assert f.matches(_make_event(level=Level.WARN))
        assert f.matches(_make_event(level=Level.ERROR))

    def test_filter_by_pattern(self):
        f = FilterSpec(pattern=re.compile(r"error.*timeout"))
        assert f.matches(_make_event(message="error: connection timeout"))
        assert not f.matches(_make_event(message="all good"))

    def test_filter_by_time_range(self):
        f = FilterSpec(
            since=datetime(2025, 6, 15, 11, 0, 0),
            until=datetime(2025, 6, 15, 13, 0, 0),
        )
        assert f.matches(_make_event(timestamp=datetime(2025, 6, 15, 12, 0, 0)))
        assert not f.matches(_make_event(timestamp=datetime(2025, 6, 15, 10, 0, 0)))
        assert not f.matches(_make_event(timestamp=datetime(2025, 6, 15, 14, 0, 0)))

    def test_combined_filters(self):
        f = FilterSpec(
            sources=["mcp-protocol"],
            min_level=Level.WARN,
            pattern=re.compile(r"timeout"),
        )
        # Passes all filters
        assert f.matches(_make_event(source="mcp-protocol", level=Level.ERROR, message="timeout"))
        # Fails source
        assert not f.matches(_make_event(source="cli-driver", level=Level.ERROR, message="timeout"))
        # Fails level
        assert not f.matches(_make_event(source="mcp-protocol", level=Level.DEBUG, message="timeout"))
        # Fails pattern
        assert not f.matches(_make_event(source="mcp-protocol", level=Level.ERROR, message="success"))
