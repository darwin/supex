"""Tests for ring buffer and ingest pipeline."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path

import pytest

from radar.buffer import RingBuffer
from radar.ingest import IngestPipeline
from radar.models import FilterSpec, Level, LogEvent
from radar.tailer import MultiTailer, TailSource


def _make_event(
    *,
    source: str = "test",
    source_path: str = "/tmp/test.log",
    message: str = "test message",
    level: Level = Level.INFO,
    timestamp: datetime | None = None,
    raw: str = "",
) -> LogEvent:
    """Helper to create a LogEvent with sensible defaults."""
    return LogEvent(
        eid=LogEvent.make_eid(),
        timestamp=timestamp or datetime(2025, 1, 15, 10, 30, 45),
        level=level,
        source=source,
        source_path=source_path,
        message=message,
        raw=raw or message,
    )


# ---------------------------------------------------------------------------
# RingBuffer: basic operations
# ---------------------------------------------------------------------------


class TestRingBufferBasic:
    def test_empty_buffer(self):
        buf = RingBuffer(capacity=100)
        assert buf.count == 0
        assert buf.sources == set()
        assert buf.get_recent(10) == []

    def test_append_and_count(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(message="first"))
        buf.append(_make_event(message="second"))
        assert buf.count == 2

    def test_get_recent_all(self):
        buf = RingBuffer(capacity=100)
        for i in range(5):
            buf.append(_make_event(message=f"msg-{i}"))
        recent = buf.get_recent(10)
        assert len(recent) == 5
        assert recent[0].message == "msg-0"
        assert recent[4].message == "msg-4"

    def test_get_recent_partial(self):
        buf = RingBuffer(capacity=100)
        for i in range(10):
            buf.append(_make_event(message=f"msg-{i}"))
        recent = buf.get_recent(3)
        assert len(recent) == 3
        assert recent[0].message == "msg-7"
        assert recent[2].message == "msg-9"

    def test_get_recent_zero(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event())
        assert buf.get_recent(0) == []

    def test_get_recent_negative(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event())
        assert buf.get_recent(-1) == []

    def test_sources(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(source="mcp-protocol"))
        buf.append(_make_event(source="cli-driver"))
        buf.append(_make_event(source="mcp-protocol"))
        assert buf.sources == {"mcp-protocol", "cli-driver"}


# ---------------------------------------------------------------------------
# RingBuffer: overflow / eviction
# ---------------------------------------------------------------------------


class TestRingBufferOverflow:
    def test_evicts_oldest_when_full(self):
        buf = RingBuffer(capacity=3)
        buf.append(_make_event(message="a"))
        buf.append(_make_event(message="b"))
        buf.append(_make_event(message="c"))
        buf.append(_make_event(message="d"))
        assert buf.count == 3
        recent = buf.get_recent(10)
        assert [e.message for e in recent] == ["b", "c", "d"]

    def test_eviction_preserves_order(self):
        buf = RingBuffer(capacity=5)
        for i in range(20):
            buf.append(_make_event(message=f"msg-{i}"))
        assert buf.count == 5
        recent = buf.get_recent(5)
        assert [e.message for e in recent] == [
            "msg-15", "msg-16", "msg-17", "msg-18", "msg-19"
        ]

    def test_capacity_one(self):
        buf = RingBuffer(capacity=1)
        buf.append(_make_event(message="first"))
        buf.append(_make_event(message="second"))
        assert buf.count == 1
        assert buf.get_recent(1)[0].message == "second"


# ---------------------------------------------------------------------------
# RingBuffer: filter
# ---------------------------------------------------------------------------


class TestRingBufferFilter:
    def test_filter_by_source(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(source="mcp-protocol", message="mcp msg"))
        buf.append(_make_event(source="cli-driver", message="cli msg"))
        buf.append(_make_event(source="mcp-protocol", message="mcp msg 2"))

        spec = FilterSpec(sources=["mcp-protocol"])
        result = buf.filter(spec)
        assert len(result) == 2
        assert all(e.source == "mcp-protocol" for e in result)

    def test_filter_by_level(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(level=Level.DEBUG, message="debug"))
        buf.append(_make_event(level=Level.ERROR, message="error"))
        buf.append(_make_event(level=Level.WARN, message="warn"))

        spec = FilterSpec(min_level=Level.WARN)
        result = buf.filter(spec)
        assert len(result) == 2
        messages = {e.message for e in result}
        assert messages == {"error", "warn"}

    def test_filter_by_pattern(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(message="connection timeout"))
        buf.append(_make_event(message="all good"))
        buf.append(_make_event(message="connection refused"))

        spec = FilterSpec(pattern=re.compile(r"connection"))
        result = buf.filter(spec)
        assert len(result) == 2

    def test_filter_combined(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(source="mcp", level=Level.ERROR, message="mcp error"))
        buf.append(_make_event(source="mcp", level=Level.DEBUG, message="mcp debug"))
        buf.append(_make_event(source="cli", level=Level.ERROR, message="cli error"))

        spec = FilterSpec(sources=["mcp"], min_level=Level.ERROR)
        result = buf.filter(spec)
        assert len(result) == 1
        assert result[0].message == "mcp error"

    def test_filter_empty_result(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(source="test"))
        spec = FilterSpec(sources=["nonexistent"])
        assert buf.filter(spec) == []

    def test_source_filter_uses_logical_name(self):
        """Source filtering uses logical source ID, independent of file basename."""
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(
            source="my-custom-source",
            source_path="/var/log/totally-different-name.log",
            message="from custom",
        ))
        buf.append(_make_event(
            source="other-source",
            source_path="/var/log/my-custom-source.log",
            message="from other",
        ))

        spec = FilterSpec(sources=["my-custom-source"])
        result = buf.filter(spec)
        assert len(result) == 1
        assert result[0].message == "from custom"
        assert result[0].source_path == "/var/log/totally-different-name.log"


# ---------------------------------------------------------------------------
# RingBuffer: search
# ---------------------------------------------------------------------------


class TestRingBufferSearch:
    def test_search_in_message(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(message="connection timeout error"))
        buf.append(_make_event(message="all good"))
        buf.append(_make_event(message="timeout on request"))

        result = buf.search("timeout")
        assert len(result) == 2

    def test_search_in_raw(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(message="summary", raw="full raw line with secret_key"))
        buf.append(_make_event(message="other", raw="nothing here"))

        result = buf.search("secret_key")
        assert len(result) == 1
        assert result[0].message == "summary"

    def test_search_regex(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(message="error code 404"))
        buf.append(_make_event(message="error code 500"))
        buf.append(_make_event(message="success code 200"))

        result = buf.search(r"error code \d{3}")
        assert len(result) == 2

    def test_search_invalid_regex_fallback_to_literal(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(message="test[1]"))
        buf.append(_make_event(message="test2"))

        # "[1" is invalid regex — should fall back to literal substring
        result = buf.search("[1")
        assert len(result) == 1

    def test_search_no_results(self):
        buf = RingBuffer(capacity=100)
        buf.append(_make_event(message="hello"))
        assert buf.search("nonexistent") == []


# ---------------------------------------------------------------------------
# IngestPipeline: end-to-end
# ---------------------------------------------------------------------------


class TestIngestPipelineEndToEnd:
    @pytest.mark.asyncio
    async def test_ingest_pipe_format(self, tmp_path: Path):
        """End-to-end: pipe-formatted file -> tailer -> normalizer -> buffer."""
        log_file = tmp_path / "driver.log"
        log_file.write_text(
            "2025-01-15 10:30:45|INFO|driver|First message\n"
            "2025-01-15 10:30:46|ERROR|driver|Second message\n"
        )

        sources = [TailSource(source="cli-driver", source_path=log_file)]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf, parser_overrides={"cli-driver": "pipe"})

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 2
        events = buf.get_recent(10)
        assert events[0].source == "cli-driver"
        assert events[0].message == "First message"
        assert events[0].level == Level.INFO
        assert events[1].message == "Second message"
        assert events[1].level == Level.ERROR

    @pytest.mark.asyncio
    async def test_ingest_jsonl_format(self, tmp_path: Path):
        """End-to-end: JSONL file -> buffer."""
        log_file = tmp_path / "protocol.jsonl"
        log_file.write_text(
            '{"timestamp": "2025-01-15T10:30:45", "level": "INFO", "message": "Request received"}\n'
            '{"timestamp": "2025-01-15T10:30:46", "level": "DEBUG", "message": "Processing"}\n'
        )

        sources = [TailSource(source="mcp-protocol", source_path=log_file)]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf, parser_overrides={"mcp-protocol": "jsonl"})

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 2
        events = buf.get_recent(10)
        assert events[0].message == "Request received"
        assert events[0].structured is not None

    @pytest.mark.asyncio
    async def test_ingest_multiple_sources(self, tmp_path: Path):
        """Multiple log files ingested simultaneously."""
        file_a = tmp_path / "driver.log"
        file_b = tmp_path / "console.log"
        file_a.write_text("2025-01-15 10:30:45|INFO|drv|From driver\n")
        file_b.write_text("2025-01-15 10:30:45|WARN|con|From console\n")

        sources = [
            TailSource(source="cli-driver", source_path=file_a),
            TailSource(source="runtime-console", source_path=file_b),
        ]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(
            tailer, buf,
            parser_overrides={"cli-driver": "pipe", "runtime-console": "pipe"},
        )

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 2
        assert buf.sources == {"cli-driver", "runtime-console"}

    @pytest.mark.asyncio
    async def test_ingest_live_append(self, tmp_path: Path):
        """Lines appended after start are picked up."""
        log_file = tmp_path / "live.log"
        log_file.write_text("")

        sources = [TailSource(source="live", source_path=log_file)]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf, parser_overrides={"live": "pipe"})

        task = asyncio.create_task(pipeline.run())

        # Wait then append
        await asyncio.sleep(0.1)
        with open(log_file, "a") as f:
            f.write("2025-01-15 10:30:45|INFO|src|Live line\n")

        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 1
        assert buf.get_recent(1)[0].message == "Live line"


# ---------------------------------------------------------------------------
# IngestPipeline: parser selection precedence
# ---------------------------------------------------------------------------


class TestIngestParserSelection:
    @pytest.mark.asyncio
    async def test_explicit_parser_override(self, tmp_path: Path):
        """Explicit parser override in config takes precedence."""
        log_file = tmp_path / "test.log"
        # Write pipe-formatted content but override parser to plain
        log_file.write_text("2025-01-15 10:30:45|INFO|src|Message\n")

        sources = [TailSource(source="test-src", source_path=log_file)]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf, parser_overrides={"test-src": "plain"})

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 1
        ev = buf.get_recent(1)[0]
        # Plain parser would treat the whole line as the message (not split on pipes)
        assert ev.source == "test-src"
        assert ev.structured is None

    @pytest.mark.asyncio
    async def test_auto_detect_pipe(self, tmp_path: Path):
        """Without explicit override, auto-detect selects pipe parser."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            "2025-01-15 10:30:45|INFO|src|Msg one\n"
            "2025-01-15 10:30:46|DEBUG|src|Msg two\n"
        )

        sources = [TailSource(source="auto-src", source_path=log_file)]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        # No parser_overrides — auto-detect
        pipeline = IngestPipeline(tailer, buf)

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count >= 1
        # Auto-detect should have parsed at least the second line as pipe
        events = buf.get_recent(10)
        assert any(e.source == "auto-src" for e in events)

    @pytest.mark.asyncio
    async def test_plain_fallback_for_unrecognized(self, tmp_path: Path):
        """Plain text content uses plain parser (auto-detect fallback)."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Just some unstructured text\nAnother line\n")

        sources = [TailSource(source="plain-src", source_path=log_file)]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf)

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count >= 1
        events = buf.get_recent(10)
        assert any("unstructured" in e.message for e in events)


# ---------------------------------------------------------------------------
# IngestPipeline: glob expansion
# ---------------------------------------------------------------------------


class TestIngestGlobExpansion:
    @pytest.mark.asyncio
    async def test_glob_expands_and_ingests(self, tmp_path: Path):
        """Glob path expands deterministically and ingests all matched files."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        (logs_dir / "alpha.log").write_text("2025-01-15 10:30:45|INFO|a|From alpha\n")
        (logs_dir / "beta.log").write_text("2025-01-15 10:30:46|WARN|b|From beta\n")
        (logs_dir / "gamma.txt").write_text("ignored file\n")

        # Expand glob manually (as config loading would do)
        import glob
        matched = sorted(glob.glob(str(logs_dir / "*.log")))
        assert len(matched) == 2

        sources = [
            TailSource(source="glob-test", source_path=Path(p))
            for p in matched
        ]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf, parser_overrides={"glob-test": "pipe"})

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 2
        messages = {e.message for e in buf.get_recent(10)}
        assert "From alpha" in messages
        assert "From beta" in messages

    @pytest.mark.asyncio
    async def test_glob_deterministic_order(self, tmp_path: Path):
        """Glob-expanded paths are sorted lexicographically."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        (logs_dir / "c.log").write_text("2025-01-15 10:30:47|INFO|x|Third\n")
        (logs_dir / "a.log").write_text("2025-01-15 10:30:45|INFO|x|First\n")
        (logs_dir / "b.log").write_text("2025-01-15 10:30:46|INFO|x|Second\n")

        import glob
        matched = sorted(glob.glob(str(logs_dir / "*.log")))
        assert [Path(p).name for p in matched] == ["a.log", "b.log", "c.log"]

        sources = [
            TailSource(source="ordered", source_path=Path(p))
            for p in matched
        ]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf, parser_overrides={"ordered": "pipe"})

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 3

    @pytest.mark.asyncio
    async def test_glob_deduplication(self, tmp_path: Path):
        """Duplicate paths from overlapping globs are deduplicated."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        (logs_dir / "test.log").write_text("2025-01-15 10:30:45|INFO|x|Msg\n")

        import glob
        matched1 = glob.glob(str(logs_dir / "*.log"))
        matched2 = glob.glob(str(logs_dir / "test*"))
        # Deduplicate
        all_paths = sorted(set(matched1 + matched2))
        assert len(all_paths) == 1

        sources = [
            TailSource(source="dedup", source_path=Path(p))
            for p in all_paths
        ]
        tailer = MultiTailer(sources, poll_interval=0.05)
        buf = RingBuffer(capacity=100)
        pipeline = IngestPipeline(tailer, buf, parser_overrides={"dedup": "pipe"})

        task = asyncio.create_task(pipeline.run())
        await asyncio.sleep(0.3)
        pipeline.flush_all()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert buf.count == 1
