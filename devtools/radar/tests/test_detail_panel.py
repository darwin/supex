"""Tests for DetailPanel view_mode toggle and raw rendering."""

from __future__ import annotations

from datetime import datetime

from radar.models import Level, LogEvent
from radar.tui.views import DetailPanel


def _make_event(
    *,
    raw: str = "line one\nline two\nline three",
    message: str = "test message",
) -> LogEvent:
    return LogEvent(
        eid="abc123",
        timestamp=datetime(2025, 1, 15, 10, 30, 45),
        level=Level.INFO,
        source="test-source",
        source_path="/tmp/test.log",
        message=message,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# DetailPanel.toggle_raw
# ---------------------------------------------------------------------------


class TestDetailPanelToggleRaw:
    def test_initial_mode_is_detail(self):
        panel = DetailPanel()
        assert panel.view_mode == "detail"

    def test_toggle_raw_switches_to_raw(self):
        panel = DetailPanel()
        panel.toggle_raw()
        assert panel.view_mode == "raw"

    def test_toggle_raw_twice_returns_to_detail(self):
        panel = DetailPanel()
        panel.toggle_raw()
        panel.toggle_raw()
        assert panel.view_mode == "detail"

    def test_toggle_raw_cycles_raw_detail(self):
        """Repeated toggles alternate between raw and detail."""
        panel = DetailPanel()
        modes = []
        for _ in range(4):
            panel.toggle_raw()
            modes.append(panel.view_mode)
        assert modes == ["raw", "detail", "raw", "detail"]


# ---------------------------------------------------------------------------
# DetailPanel._render_raw_text
# ---------------------------------------------------------------------------


class TestRenderRawText:
    def test_includes_eid(self):
        event = _make_event()
        text = DetailPanel._render_raw_text(event)
        assert "EID: abc123" in text.plain

    def test_includes_raw_label(self):
        event = _make_event()
        text = DetailPanel._render_raw_text(event)
        assert "[raw]" in text.plain

    def test_line_numbers_start_at_one(self):
        event = _make_event(raw="alpha\nbeta\ngamma")
        text = DetailPanel._render_raw_text(event)
        lines = text.plain.split("\n")
        # Find numbered lines (skip header and separator)
        numbered = [line for line in lines if "\u2502" in line]
        assert len(numbered) == 3
        assert numbered[0].strip().startswith("1\u2502")
        assert numbered[1].strip().startswith("2\u2502")
        assert numbered[2].strip().startswith("3\u2502")

    def test_single_line_raw(self):
        event = _make_event(raw="single line")
        text = DetailPanel._render_raw_text(event)
        numbered = [line for line in text.plain.split("\n") if "\u2502" in line]
        assert len(numbered) == 1
        assert "single line" in numbered[0]

    def test_separator_present(self):
        event = _make_event()
        text = DetailPanel._render_raw_text(event)
        assert "\u2500" * 60 in text.plain
