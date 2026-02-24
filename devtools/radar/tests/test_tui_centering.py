"""Tests for deterministic cursor centering in Radar TUI detail mode."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from radar.buffer import ObservableBuffer
from radar.models import Level, LogEvent
from radar.tui.app import RadarApp
from radar.tui.views import LogListView


class _DummyPipeline:
    async def run(self) -> None:
        await asyncio.Event().wait()


class _StaticRadarApp(RadarApp):
    """Radar app variant for tests without periodic workers/timers."""

    def on_mount(self) -> None:
        self.query_one("#log-list", LogListView).focus()


def _make_event(i: int) -> LogEvent:
    return LogEvent(
        eid=f"e{i:06d}",
        timestamp=datetime(2026, 2, 24, 12, 0, 0),
        level=Level.INFO,
        source="test-source",
        source_path="/tmp/test.log",
        message=f"message {i}",
        raw=f"raw {i}",
    )


def _seed_events(app: RadarApp, count: int = 30) -> LogListView:
    log_list = app.query_one("#log-list", LogListView)
    events = [_make_event(i) for i in range(count)]
    log_list.add_events_batch(events)
    app._visible_events.extend(events)
    return log_list


@pytest.mark.parametrize(
    ("cursor_row", "row_count", "visible_rows", "expected_top"),
    [
        (10, 30, 3, 9),
        (0, 30, 3, 0),
        (29, 30, 3, 27),
        (2, 3, 3, 0),
    ],
)
def test_centered_scroll_top(cursor_row: int, row_count: int, visible_rows: int, expected_top: int) -> None:
    assert RadarApp._centered_scroll_top(cursor_row, row_count, visible_rows) == expected_top


@pytest.mark.asyncio
async def test_enter_opens_detail_and_centers_cursor() -> None:
    app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)

    async with app.run_test(size=(100, 24)) as pilot:
        log_list = _seed_events(app, count=40)

        # Enter browsing mode, then pick a middle row.
        app.action_cursor_down()
        log_list.move_cursor(row=10)
        await pilot.pause()

        app.action_select_row()
        await pilot.pause()
        await pilot.pause()

        header_rows = log_list.header_height if log_list.show_header else 0
        visible_rows = log_list.size.height - header_rows
        expected_top = RadarApp._centered_scroll_top(10, log_list.row_count, visible_rows)

        assert log_list.has_class("detail-open")
        assert log_list.cursor_row == 10
        assert int(log_list.scroll_y) == expected_top


@pytest.mark.asyncio
async def test_cursor_move_recenters_when_detail_visible() -> None:
    app = _StaticRadarApp(pipeline=_DummyPipeline(), buffer=ObservableBuffer(), mouse=False)

    async with app.run_test(size=(100, 24)) as pilot:
        log_list = _seed_events(app, count=40)

        app.action_cursor_down()
        log_list.move_cursor(row=10)
        await pilot.pause()

        app.action_select_row()
        await pilot.pause()
        await pilot.pause()

        app.action_cursor_up()
        await pilot.pause()

        header_rows = log_list.header_height if log_list.show_header else 0
        visible_rows = log_list.size.height - header_rows
        expected_top = RadarApp._centered_scroll_top(9, log_list.row_count, visible_rows)

        assert log_list.cursor_row == 9
        assert int(log_list.scroll_y) == expected_top
