"""Performance regression tests for large buffer operations."""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import pytest

from radar.buffer import ObservableBuffer, RingBuffer
from radar.models import FilterSpec, Level, LogEvent


def _make_events(n: int, sources: int = 5) -> list[LogEvent]:
    """Generate n synthetic events across multiple sources."""
    source_names = [f"src-{i}" for i in range(sources)]
    levels = list(Level)
    base_ts = datetime(2025, 6, 1, 12, 0, 0)
    events = []
    for i in range(n):
        src = source_names[i % sources]
        lvl = levels[i % len(levels)]
        ts = base_ts + timedelta(milliseconds=i * 10)
        events.append(LogEvent(
            eid=f"{i:06x}"[-6:],
            timestamp=ts,
            level=lvl,
            source=src,
            source_path=f"/tmp/perf/{src}.log",
            message=f"perf event {i} src={src}",
            raw=f"perf event {i} src={src}",
        ))
    return events


class TestBufferIngestPerformance:
    """Verify buffer ingest stays fast at 100k+ scale."""

    def test_ingest_100k_under_2s(self):
        events = _make_events(100_000)
        buf = RingBuffer(capacity=100_000)

        t0 = time.perf_counter()
        for event in events:
            buf.append(event)
        elapsed = time.perf_counter() - t0

        assert buf.count == 100_000
        assert elapsed < 2.0, f"Ingest took {elapsed:.3f}s (expected < 2s)"

    def test_ingest_100k_with_eviction_under_2s(self):
        """Ingest 100k into a 10k buffer (90k evictions)."""
        events = _make_events(100_000)
        buf = RingBuffer(capacity=10_000)

        t0 = time.perf_counter()
        for event in events:
            buf.append(event)
        elapsed = time.perf_counter() - t0

        assert buf.count == 10_000
        assert elapsed < 2.0, f"Ingest with eviction took {elapsed:.3f}s (expected < 2s)"


class TestSourcesPropertyPerformance:
    """Verify cached sources is O(1) not O(n)."""

    def test_sources_cached_fast(self):
        events = _make_events(100_000, sources=10)
        buf = RingBuffer(capacity=100_000)
        for event in events:
            buf.append(event)

        t0 = time.perf_counter()
        for _ in range(10_000):
            _ = buf.sources
        elapsed = time.perf_counter() - t0

        assert len(buf.sources) == 10
        # 10k calls should complete well under 1s (cached = dict.keys copy)
        assert elapsed < 1.0, f"sources x10k took {elapsed:.3f}s (expected < 1s)"

    def test_sources_tracks_eviction(self):
        """After eviction removes all events of a source, sources reflects it."""
        buf = RingBuffer(capacity=3)
        buf.append(LogEvent(
            eid="a", timestamp=datetime.now(), level=Level.INFO,
            source="alpha", source_path="/tmp/a", message="a", raw="a",
        ))
        buf.append(LogEvent(
            eid="b", timestamp=datetime.now(), level=Level.INFO,
            source="beta", source_path="/tmp/b", message="b", raw="b",
        ))
        assert buf.sources == {"alpha", "beta"}

        # Fill with beta only — alpha gets evicted
        buf.append(LogEvent(
            eid="c", timestamp=datetime.now(), level=Level.INFO,
            source="beta", source_path="/tmp/b", message="c", raw="c",
        ))
        buf.append(LogEvent(
            eid="d", timestamp=datetime.now(), level=Level.INFO,
            source="beta", source_path="/tmp/b", message="d", raw="d",
        ))
        assert buf.sources == {"beta"}


class TestFilterPerformance:
    """Verify filter operations stay responsive at 100k scale."""

    def test_filter_pass_all_under_500ms(self):
        events = _make_events(100_000)
        buf = RingBuffer(capacity=100_000)
        for event in events:
            buf.append(event)

        spec = FilterSpec()
        t0 = time.perf_counter()
        result = buf.filter(spec)
        elapsed = time.perf_counter() - t0

        assert len(result) == 100_000
        assert elapsed < 0.5, f"Filter pass-all took {elapsed:.3f}s (expected < 500ms)"

    def test_filter_by_source_under_500ms(self):
        events = _make_events(100_000, sources=5)
        buf = RingBuffer(capacity=100_000)
        for event in events:
            buf.append(event)

        spec = FilterSpec(sources=["src-0"])
        t0 = time.perf_counter()
        result = buf.filter(spec)
        elapsed = time.perf_counter() - t0

        assert len(result) == 20_000
        assert elapsed < 0.5, f"Filter by source took {elapsed:.3f}s (expected < 500ms)"

    def test_filter_by_pattern_under_1s(self):
        events = _make_events(100_000)
        buf = RingBuffer(capacity=100_000)
        for event in events:
            buf.append(event)

        spec = FilterSpec(pattern=re.compile(r"event [0-9]*00 "))
        t0 = time.perf_counter()
        result = buf.filter(spec)
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, f"Filter by pattern took {elapsed:.3f}s (expected < 1s)"


class TestObservableBufferPerformance:
    """Verify drain_pending is efficient."""

    def test_drain_100k_under_100ms(self):
        events = _make_events(100_000)
        buf = ObservableBuffer(capacity=100_000)
        for event in events:
            buf.append(event)

        t0 = time.perf_counter()
        pending = buf.drain_pending()
        elapsed = time.perf_counter() - t0

        assert len(pending) == 100_000
        assert elapsed < 0.1, f"drain_pending took {elapsed:.3f}s (expected < 100ms)"
