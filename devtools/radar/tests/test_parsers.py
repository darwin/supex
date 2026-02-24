"""Tests for parsers, auto-detection, and normalizer."""

from __future__ import annotations

import json
from datetime import datetime

from radar.models import Level
from radar.normalizer import Normalizer, _make_eid
from radar.parsers import BaseParser, detect_format, get_parser
from radar.parsers.jsonl import JsonlParser
from radar.parsers.pipe import PipeParser
from radar.parsers.plain import PlainParser


# ---------------------------------------------------------------------------
# Pipe parser
# ---------------------------------------------------------------------------


class TestPipeParser:
    def setup_method(self):
        self.parser = PipeParser()

    def test_standard_line(self):
        raw = "2025-01-15 10:30:45,123|INFO|supex_runtime|Module loaded successfully"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp == datetime(2025, 1, 15, 10, 30, 45, 123000)
        assert rec.level == "INFO"
        assert rec.message == "Module loaded successfully"
        assert rec.structured is None

    def test_missing_fields(self):
        raw = "2025-01-15 10:30:45|WARN|short"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp == datetime(2025, 1, 15, 10, 30, 45)
        assert rec.level == "WARN"
        assert rec.message == ""

    def test_extra_json_payload(self):
        payload = {"request_id": "abc123", "duration_ms": 42}
        raw = f'2025-01-15 10:30:45|DEBUG|driver|Request completed|{json.dumps(payload)}'
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.level == "DEBUG"
        assert rec.message == "Request completed"
        assert rec.structured == payload

    def test_extra_non_json_payload(self):
        raw = "2025-01-15 10:30:45|ERROR|driver|Crash detected|not valid json"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.message == "Crash detected | not valid json"

    def test_empty_line(self):
        assert self.parser.parse_line("") is None
        assert self.parser.parse_line("   ") is None

    def test_too_few_pipes(self):
        assert self.parser.parse_line("just some text") is None
        assert self.parser.parse_line("one|two") is None

    def test_iso_timestamp(self):
        raw = "2025-01-15T10:30:45.123000|INFO|src|Hello"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp == datetime(2025, 1, 15, 10, 30, 45, 123000)

    def test_no_continuation(self):
        assert self.parser.is_continuation("anything") is False


# ---------------------------------------------------------------------------
# JSONL parser
# ---------------------------------------------------------------------------


class TestJsonlParser:
    def setup_method(self):
        self.parser = JsonlParser()

    def test_valid_json_with_message(self):
        data = {
            "timestamp": "2025-01-15 10:30:45,123",
            "level": "ERROR",
            "message": "Connection failed",
        }
        rec = self.parser.parse_line(json.dumps(data))
        assert rec is not None
        assert rec.timestamp == datetime(2025, 1, 15, 10, 30, 45, 123000)
        assert rec.level == "ERROR"
        assert rec.message == "Connection failed"
        assert rec.structured == data

    def test_valid_json_without_message(self):
        data = {"method": "tools/list", "result": {"tools": []}}
        rec = self.parser.parse_line(json.dumps(data))
        assert rec is not None
        assert "method=tools/list" in rec.message
        assert "result=<object>" in rec.message

    def test_json_with_event_key(self):
        data = {"event": "vcad_place", "timestamp": "2025-01-15T10:30:45"}
        rec = self.parser.parse_line(json.dumps(data))
        assert rec is not None
        assert "event=vcad_place" in rec.message

    def test_json_with_error_dict(self):
        data = {"error": {"message": "timeout", "code": 504}}
        rec = self.parser.parse_line(json.dumps(data))
        assert rec is not None
        assert "error=timeout" in rec.message

    def test_malformed_json_returns_none(self):
        assert self.parser.parse_line("{not valid json}") is None
        assert self.parser.parse_line("plain text line") is None

    def test_json_array_returns_none(self):
        assert self.parser.parse_line("[1, 2, 3]") is None

    def test_empty_line(self):
        assert self.parser.parse_line("") is None

    def test_msg_field_alias(self):
        data = {"msg": "Short message", "level": "info"}
        rec = self.parser.parse_line(json.dumps(data))
        assert rec is not None
        assert rec.message == "Short message"
        assert rec.level == "INFO"

    def test_no_continuation(self):
        assert self.parser.is_continuation("anything") is False


# ---------------------------------------------------------------------------
# Plain parser
# ---------------------------------------------------------------------------


class TestPlainParser:
    def setup_method(self):
        self.parser = PlainParser()

    def test_iso_timestamp(self):
        raw = "2025-01-15T10:30:45.123000 INFO Starting server"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp == datetime(2025, 1, 15, 10, 30, 45, 123000)
        assert rec.level == "INFO"
        assert "Starting server" in rec.message

    def test_space_separated_timestamp(self):
        raw = "2025-01-15 10:30:45,123 - mylogger - DEBUG - Some debug message"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp == datetime(2025, 1, 15, 10, 30, 45, 123000)
        assert rec.level == "DEBUG"
        assert "Some debug message" in rec.message

    def test_syslog_format(self):
        raw = "Jan 15 10:30:45 myhost myprogram: Starting up"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp is not None
        assert rec.timestamp.month == 1
        assert rec.timestamp.day == 15
        assert rec.timestamp.hour == 10

    def test_no_timestamp(self):
        raw = "ERROR Something went wrong here"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp is None
        assert rec.level == "ERROR"
        assert "Something went wrong" in rec.message

    def test_no_level_no_timestamp(self):
        raw = "Just some plain text"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.timestamp is None
        assert rec.level is None
        assert rec.message == "Just some plain text"

    def test_empty_line(self):
        assert self.parser.parse_line("") is None
        assert self.parser.parse_line("   ") is None

    def test_warning_normalized_to_warn(self):
        raw = "2025-01-15 10:30:45 WARNING Disk almost full"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.level == "WARN"

    def test_critical_normalized_to_fatal(self):
        raw = "CRITICAL System shutdown"
        rec = self.parser.parse_line(raw)
        assert rec is not None
        assert rec.level == "FATAL"

    def test_continuation_whitespace(self):
        assert self.parser.is_continuation("    at com.example.Main.run(Main.java:42)") is True
        assert self.parser.is_continuation("  continued line") is True

    def test_continuation_caused_by(self):
        assert self.parser.is_continuation("Caused by: java.io.IOException") is True

    def test_continuation_traceback(self):
        assert self.parser.is_continuation("Traceback (most recent call last):") is True

    def test_continuation_python_frame(self):
        assert self.parser.is_continuation('  File "/app/main.py", line 42, in run') is True

    def test_not_continuation(self):
        assert self.parser.is_continuation("2025-01-15 10:30:45 INFO Normal line") is False
        assert self.parser.is_continuation("ERROR Something broke") is False


# ---------------------------------------------------------------------------
# ANSI handling
# ---------------------------------------------------------------------------


class TestAnsiHandling:
    def test_pipe_with_ansi(self):
        raw = "\x1b[32m2025-01-15 10:30:45\x1b[0m|\x1b[34mINFO\x1b[0m|src|Message"
        rec = PipeParser().parse_line(raw)
        assert rec is not None
        assert rec.level == "INFO"
        assert rec.message == "Message"

    def test_jsonl_with_ansi(self):
        data = {"level": "ERROR", "message": "fail"}
        raw = f"\x1b[31m{json.dumps(data)}\x1b[0m"
        rec = JsonlParser().parse_line(raw)
        assert rec is not None
        assert rec.level == "ERROR"

    def test_plain_with_ansi(self):
        raw = "\x1b[33m2025-01-15 10:30:45 WARN Low memory\x1b[0m"
        rec = PlainParser().parse_line(raw)
        assert rec is not None
        assert rec.level == "WARN"
        assert "Low memory" in rec.message


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


class TestDetectFormat:
    def test_detect_jsonl(self):
        lines = [
            '{"timestamp": "2025-01-15T10:30:45", "level": "INFO", "message": "hello"}',
            '{"timestamp": "2025-01-15T10:30:46", "level": "DEBUG", "message": "world"}',
        ]
        parser = detect_format(lines)
        assert isinstance(parser, JsonlParser)

    def test_detect_pipe(self):
        lines = [
            "2025-01-15 10:30:45|INFO|module|Hello",
            "2025-01-15 10:30:46|DEBUG|module|World",
        ]
        parser = detect_format(lines)
        assert isinstance(parser, PipeParser)

    def test_detect_plain(self):
        lines = [
            "Just some plain text",
            "Another plain line",
        ]
        parser = detect_format(lines)
        assert isinstance(parser, PlainParser)

    def test_empty_lines(self):
        parser = detect_format([])
        assert isinstance(parser, PlainParser)

    def test_mixed_favors_majority(self):
        lines = [
            '{"message": "json1"}',
            '{"message": "json2"}',
            "plain text line",
        ]
        parser = detect_format(lines)
        assert isinstance(parser, JsonlParser)


# ---------------------------------------------------------------------------
# Parser registry
# ---------------------------------------------------------------------------


class TestParserRegistry:
    def test_get_pipe(self):
        assert isinstance(get_parser("pipe"), PipeParser)

    def test_get_jsonl(self):
        assert isinstance(get_parser("jsonl"), JsonlParser)

    def test_get_plain(self):
        assert isinstance(get_parser("plain"), PlainParser)

    def test_unknown_raises(self):
        import pytest

        with pytest.raises(KeyError, match="Unknown parser"):
            get_parser("nonexistent")


# ---------------------------------------------------------------------------
# Multiline
# ---------------------------------------------------------------------------


class TestMultiline:
    def test_java_stacktrace(self):
        parser = PlainParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.log")

        lines = [
            "2025-01-15 10:30:45 ERROR NullPointerException",
            "    at com.example.Main.run(Main.java:42)",
            "    at com.example.Main.main(Main.java:10)",
            "2025-01-15 10:30:46 INFO Recovery complete",
        ]

        events = []
        for line in lines:
            ev = norm.feed_line(line)
            if ev:
                events.append(ev)
        final = norm.flush()
        if final:
            events.append(final)

        assert len(events) == 2

        # First event: multiline stacktrace
        assert events[0].multiline is True
        assert "NullPointerException" in events[0].message
        assert events[0].level == Level.ERROR
        assert "Main.java:42" in events[0].raw
        assert events[0].raw.count("\n") == 2  # 3 lines, 2 newlines

        # Second event: normal line
        assert events[1].multiline is False
        assert "Recovery complete" in events[1].message

    def test_python_traceback(self):
        parser = PlainParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.log")

        lines = [
            "2025-01-15 10:30:45 ERROR Unhandled exception",
            "Traceback (most recent call last):",
            '  File "/app/main.py", line 42, in run',
            "    result = process(data)",
            "2025-01-15 10:30:46 INFO Server restarted",
        ]

        events = []
        for line in lines:
            ev = norm.feed_line(line)
            if ev:
                events.append(ev)
        final = norm.flush()
        if final:
            events.append(final)

        assert len(events) == 2
        assert events[0].multiline is True
        assert "Unhandled exception" in events[0].message
        assert events[0].raw.count("\n") == 3  # 4 lines


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------


class TestNormalizer:
    def test_single_line_event(self):
        parser = PipeParser()
        norm = Normalizer(parser, source="mcp-stderr", source_path="/tmp/mcp.log")

        ev = norm.feed_line("2025-01-15 10:30:45|INFO|driver|Hello world")
        # First line buffered, no event yet
        assert ev is None

        # Flush to get the event
        ev = norm.flush()
        assert ev is not None
        assert ev.source == "mcp-stderr"
        assert ev.source_path == "/tmp/mcp.log"
        assert ev.level == Level.INFO
        assert ev.message == "Hello world"
        assert ev.multiline is False

    def test_sequence_of_lines(self):
        parser = PipeParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.log")

        events = []
        lines = [
            "2025-01-15 10:30:45|INFO|src|First message",
            "2025-01-15 10:30:46|ERROR|src|Second message",
            "2025-01-15 10:30:47|DEBUG|src|Third message",
        ]

        for line in lines:
            ev = norm.feed_line(line)
            if ev:
                events.append(ev)
        final = norm.flush()
        if final:
            events.append(final)

        assert len(events) == 3
        assert events[0].message == "First message"
        assert events[1].message == "Second message"
        assert events[2].message == "Third message"

    def test_jsonl_normalizer(self):
        parser = JsonlParser()
        norm = Normalizer(parser, source="mcp-protocol", source_path="/tmp/mcp.jsonl")

        data = {"timestamp": "2025-01-15T10:30:45", "level": "INFO", "message": "Request received"}
        ev = norm.feed_line(json.dumps(data))
        assert ev is None

        ev = norm.flush()
        assert ev is not None
        assert ev.message == "Request received"
        assert ev.structured is not None
        assert ev.structured["message"] == "Request received"

    def test_malformed_jsonl_fallback(self):
        """Malformed JSON should still produce an event via normalizer fallback."""
        parser = JsonlParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.jsonl")

        ev = norm.feed_line("{bad json line")
        assert ev is None

        ev = norm.flush()
        assert ev is not None
        assert "{bad json line" in ev.message

    def test_timestamp_fallback_to_now(self):
        parser = PlainParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.log")

        norm.feed_line("No timestamp here just text")
        ev = norm.flush()
        assert ev is not None
        # Should get a timestamp (fallback to now)
        assert ev.timestamp is not None

    def test_level_defaults_to_info(self):
        parser = PlainParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.log")

        norm.feed_line("No level marker in this line")
        ev = norm.flush()
        assert ev is not None
        assert ev.level == Level.INFO

    def test_raw_preserved(self):
        parser = PipeParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.log")

        raw = "2025-01-15 10:30:45|INFO|src|Hello"
        norm.feed_line(raw)
        ev = norm.flush()
        assert ev is not None
        assert ev.raw == raw


# ---------------------------------------------------------------------------
# EID
# ---------------------------------------------------------------------------


class TestEid:
    def test_eid_present(self):
        parser = PipeParser()
        norm = Normalizer(parser, source="test", source_path="/tmp/test.log")

        norm.feed_line("2025-01-15 10:30:45|INFO|src|Hello")
        ev = norm.flush()
        assert ev is not None
        assert len(ev.eid) == 6
        assert all(c in "0123456789abcdef" for c in ev.eid)

    def test_eid_stable_for_same_input(self):
        ts = datetime(2025, 1, 15, 10, 30, 45)
        eid1 = _make_eid("test", ts, "raw line content")
        eid2 = _make_eid("test", ts, "raw line content")
        assert eid1 == eid2

    def test_eid_changes_with_source(self):
        ts = datetime(2025, 1, 15, 10, 30, 45)
        eid1 = _make_eid("source-a", ts, "same line")
        eid2 = _make_eid("source-b", ts, "same line")
        assert eid1 != eid2

    def test_eid_changes_with_timestamp(self):
        raw = "same raw line"
        eid1 = _make_eid("test", datetime(2025, 1, 15, 10, 30, 45), raw)
        eid2 = _make_eid("test", datetime(2025, 1, 15, 10, 30, 46), raw)
        assert eid1 != eid2

    def test_eid_changes_with_raw_line(self):
        ts = datetime(2025, 1, 15, 10, 30, 45)
        eid1 = _make_eid("test", ts, "line alpha")
        eid2 = _make_eid("test", ts, "line beta")
        assert eid1 != eid2

    def test_eid_with_none_timestamp(self):
        eid = _make_eid("test", None, "some line")
        assert len(eid) == 6
        assert all(c in "0123456789abcdef" for c in eid)
