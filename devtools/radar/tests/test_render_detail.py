"""Tests for renderer detail delegation and render_raw formatting."""

from __future__ import annotations

import json
from datetime import datetime

from rich.text import Text

from radar.models import Level, LogEvent
from radar.tui.renderers import (
    DefaultSummaryRenderer,
    MCPProtocolRenderer,
    SummaryRenderer,
    get_renderer,
    render_raw,
)


def _make_event(
    *,
    source: str = "test",
    message: str = "test message",
    raw: str = "",
    level: Level = Level.INFO,
    structured: dict | None = None,
) -> LogEvent:
    return LogEvent(
        eid="abc123",
        timestamp=datetime(2025, 1, 15, 10, 30, 45),
        level=level,
        source=source,
        source_path="/tmp/test.log",
        message=message,
        raw=raw or message,
        structured=structured,
    )


# ---------------------------------------------------------------------------
# SummaryRenderer.render_detail — base class default
# ---------------------------------------------------------------------------


class TestSummaryRendererDetailDefault:
    def test_base_class_returns_raw(self):
        """Default render_detail returns event.raw as plain Text."""

        class MinimalRenderer(SummaryRenderer):
            def render(self, event: LogEvent) -> Text:
                return Text("summary")

        r = MinimalRenderer()
        event = _make_event(raw="raw content here")
        detail = r.render_detail(event)
        assert isinstance(detail, Text)
        assert detail.plain == "raw content here"

    def test_default_renderer_detail(self):
        """DefaultSummaryRenderer inherits the base render_detail."""
        r = DefaultSummaryRenderer()
        event = _make_event(raw="default raw")
        detail = r.render_detail(event)
        assert detail.plain == "default raw"


# ---------------------------------------------------------------------------
# MCPProtocolRenderer.render_detail
# ---------------------------------------------------------------------------


class TestMCPProtocolRendererDetail:
    def test_structured_event_produces_indented_json(self):
        """Structured events render as pretty-printed JSON."""
        r = MCPProtocolRenderer()
        data = {"method": "tools/call", "params": {"name": "eval_ruby"}}
        event = _make_event(
            source="mcp-protocol",
            structured=data,
            raw='{"method":"tools/call"}',
        )
        detail = r.render_detail(event)
        parsed = json.loads(detail.plain)
        assert parsed == data

    def test_no_structured_falls_back_to_raw(self):
        """Events without structured data return raw text."""
        r = MCPProtocolRenderer()
        event = _make_event(
            source="mcp-protocol",
            raw="plain log line",
            structured=None,
        )
        detail = r.render_detail(event)
        assert detail.plain == "plain log line"


# ---------------------------------------------------------------------------
# render_raw — compact header + delegated detail
# ---------------------------------------------------------------------------


class TestRenderRaw:
    def test_header_contains_eid_source_timestamp_level(self):
        """render_raw header line includes EID, source, ISO timestamp, level."""
        event = _make_event(source="cli-driver", level=Level.WARN)
        result = render_raw(event)
        plain = result.plain
        assert "EID: abc123" in plain
        assert "Source: cli-driver" in plain
        assert "2025-01-15" in plain
        assert "WARN" in plain

    def test_header_is_single_line(self):
        """Header metadata is on one line (compact format)."""
        event = _make_event(source="test-src")
        lines = render_raw(event).plain.split("\n")
        # First line has all metadata, second is separator
        assert "EID:" in lines[0]
        assert "Source:" in lines[0]
        assert "\u2500" in lines[1]

    def test_delegates_to_source_renderer(self):
        """render_raw uses the source renderer's render_detail."""
        # mcp-protocol has a custom renderer — structured data produces JSON
        data = {"method": "test/method", "id": 1}
        event = _make_event(
            source="mcp-protocol",
            structured=data,
            raw="raw fallback",
        )
        result = render_raw(event)
        # Should contain pretty-printed JSON, not the raw fallback
        assert '"method": "test/method"' in result.plain

    def test_unknown_source_uses_default_detail(self):
        """Unknown source falls back to DefaultSummaryRenderer.render_detail (raw text)."""
        event = _make_event(source="unknown-source-xyz", raw="my raw text")
        result = render_raw(event)
        assert "my raw text" in result.plain

    def test_separator_is_60_chars(self):
        """Separator line is 60 box-drawing characters."""
        event = _make_event()
        lines = render_raw(event).plain.split("\n")
        sep_line = lines[1]
        assert len(sep_line) == 60
        assert all(c == "\u2500" for c in sep_line)


# ---------------------------------------------------------------------------
# get_renderer — module-level convenience
# ---------------------------------------------------------------------------


class TestGetRenderer:
    def test_known_source_returns_specific(self):
        """mcp-protocol returns MCPProtocolRenderer."""
        r = get_renderer("mcp-protocol")
        assert isinstance(r, MCPProtocolRenderer)

    def test_unknown_source_returns_default(self):
        """Unknown source returns DefaultSummaryRenderer."""
        r = get_renderer("nonexistent-source")
        assert isinstance(r, DefaultSummaryRenderer)
