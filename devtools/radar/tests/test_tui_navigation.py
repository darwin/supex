"""Tests for TUI navigation: page up/down, browse mode entry, double Ctrl+C, detail toggle."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from radar.buffer import ObservableBuffer
from radar.models import Level, LogEvent
from radar.tui.app import RadarApp
from radar.tui.views import DetailPanel, LogListView


class _DummyPipeline:
    async def run(self) -> None:
        await asyncio.Event().wait()


class _StaticRadarApp(RadarApp):
    """Radar app variant for tests — skips background workers and timers."""

    def on_mount(self) -> None:
        self.query_one("#log-list", LogListView).focus()


def _make_event(i: int) -> LogEvent:
    return LogEvent(
        eid=f"e{i:06d}",
        timestamp=datetime(2026, 2, 24, 12, 0, i % 60),
        level=Level.INFO,
        source="test-source",
        source_path="/tmp/test.log",
        message=f"message {i}",
        raw=f"raw {i}",
    )


def _seed_events(app: RadarApp, count: int = 40) -> LogListView:
    log_list = app.query_one("#log-list", LogListView)
    events = [_make_event(i) for i in range(count)]
    log_list.add_events_batch(events)
    app._visible_events.extend(events)
    return log_list


# ---------------------------------------------------------------------------
# Browse mode entry: first cursor_down does not move cursor
# ---------------------------------------------------------------------------


class TestBrowseModeEntry:
    @pytest.mark.asyncio
    async def test_first_cursor_down_enters_browse_at_last_row(self):
        """First cursor_down enters browse mode with cursor on the last row."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=20)
            await pilot.pause()

            assert app._mode == "streaming"
            app.action_cursor_down()
            await pilot.pause()

            assert app._mode == "browsing"
            assert log_list.cursor_row == 19  # last row (0-indexed)

    @pytest.mark.asyncio
    async def test_second_cursor_down_moves_cursor(self):
        """Second cursor_down after browse entry moves cursor down."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=20)
            await pilot.pause()

            # Enter browse mode — lands on last row
            app.action_cursor_down()
            await pilot.pause()
            # Already at last row, so cursor stays at 19
            # Move up first, then down to verify movement
            app.action_cursor_up()
            await pilot.pause()
            assert log_list.cursor_row == 18

            app.action_cursor_down()
            await pilot.pause()
            assert log_list.cursor_row == 19

    @pytest.mark.asyncio
    async def test_first_cursor_up_enters_browse_at_last_row(self):
        """First cursor_up also enters browse at last row without moving."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=20)
            await pilot.pause()

            app.action_cursor_up()
            await pilot.pause()

            assert app._mode == "browsing"
            assert log_list.cursor_row == 19  # last row, no movement


# ---------------------------------------------------------------------------
# Page up / page down
# ---------------------------------------------------------------------------


class TestPageNavigation:
    @pytest.mark.asyncio
    async def test_page_down_moves_by_page_size(self):
        """page_down moves cursor by (height - 1) rows."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=50)
            await pilot.pause()

            # Enter browse mode and go to top
            app.action_scroll_top()
            await pilot.pause()
            assert log_list.cursor_row == 0

            app.action_page_down()
            await pilot.pause()
            page = max(1, log_list.size.height - 1)
            assert log_list.cursor_row == page

    @pytest.mark.asyncio
    async def test_page_up_moves_by_page_size(self):
        """page_up moves cursor backwards by (height - 1) rows."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=50)
            await pilot.pause()

            # Enter browse mode (at last row), then page up
            app.action_cursor_down()
            await pilot.pause()
            last_row = log_list.cursor_row
            assert last_row == 49

            app.action_page_up()
            await pilot.pause()
            page = max(1, log_list.size.height - 1)
            assert log_list.cursor_row == last_row - page

    @pytest.mark.asyncio
    async def test_page_up_clamps_at_zero(self):
        """page_up does not go below row 0."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=50)
            await pilot.pause()

            app.action_scroll_top()
            await pilot.pause()
            assert log_list.cursor_row == 0

            app.action_page_up()
            await pilot.pause()
            assert log_list.cursor_row == 0

    @pytest.mark.asyncio
    async def test_page_down_clamps_at_last(self):
        """page_down does not exceed the last row."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=50)
            await pilot.pause()

            app.action_scroll_bottom()
            await pilot.pause()
            assert log_list.cursor_row == 49

            app.action_page_down()
            await pilot.pause()
            assert log_list.cursor_row == 49


# ---------------------------------------------------------------------------
# Show / hide detail
# ---------------------------------------------------------------------------


class TestDetailToggle:
    @pytest.mark.asyncio
    async def test_select_row_opens_detail(self):
        """action_select_row opens detail panel and adds CSS classes."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=10)
            await pilot.pause()

            app.action_cursor_down()
            await pilot.pause()
            app.action_select_row()
            await pilot.pause()

            detail = app.query_one("#detail-panel", DetailPanel)
            assert detail.has_class("visible")
            assert log_list.has_class("detail-open")

    @pytest.mark.asyncio
    async def test_select_row_twice_hides_detail(self):
        """Second action_select_row hides the detail panel."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            log_list = _seed_events(app, count=10)
            await pilot.pause()

            app.action_cursor_down()
            await pilot.pause()
            app.action_select_row()
            await pilot.pause()
            app.action_select_row()
            await pilot.pause()

            detail = app.query_one("#detail-panel", DetailPanel)
            assert not detail.has_class("visible")
            assert not log_list.has_class("detail-open")

    @pytest.mark.asyncio
    async def test_exit_browse_hides_detail(self):
        """action_exit_browse hides detail and returns to streaming."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            _seed_events(app, count=10)
            await pilot.pause()

            app.action_cursor_down()
            await pilot.pause()
            app.action_select_row()
            await pilot.pause()

            app.action_exit_browse()
            await pilot.pause()

            detail = app.query_one("#detail-panel", DetailPanel)
            assert not detail.has_class("visible")
            assert app._mode == "streaming"


# ---------------------------------------------------------------------------
# Double Ctrl+C to quit
# ---------------------------------------------------------------------------


class TestDoubleCtrlC:
    @pytest.mark.asyncio
    async def test_single_ctrl_c_does_not_quit(self):
        """Single Ctrl+C does not exit the app."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            _seed_events(app, count=5)
            await pilot.pause()

            app.action_interrupt()
            await pilot.pause()

            # App should still be running — _last_ctrl_c is set
            assert app._last_ctrl_c > 0
            assert app.is_running

    @pytest.mark.asyncio
    async def test_double_ctrl_c_exits(self):
        """Two rapid Ctrl+C presses exit the app."""
        app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)
        async with app.run_test(size=(100, 24)) as pilot:
            _seed_events(app, count=5)
            await pilot.pause()

            app.action_interrupt()
            app.action_interrupt()
            await pilot.pause()

            # App should have exited
            assert not app.is_running
