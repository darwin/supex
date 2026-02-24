"""Main Textual application for Radar TUI."""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding
from textual.widgets import Input

from radar.buffer import ObservableBuffer
from radar.models import FilterSpec, LogEvent
from radar.tui.views import DetailPanel, FilterBar, LogListView, RadarStatusBar

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from radar.ingest import IngestPipeline


class RadarApp(App):
    """Supex Radar TUI — live log aggregator."""

    TITLE = "radar"

    CSS = """
    #filter-bar {
        height: auto;
        max-height: 5;
        display: none;
        padding: 0 1;
        background: $surface;
    }
    #filter-bar.visible {
        display: block;
    }
    #filter-inputs {
        height: 3;
    }
    #filter-inputs Input {
        width: 1fr;
        margin: 0 1 0 0;
    }
    LogListView {
        height: 1fr;
    }
    #detail-panel {
        height: auto;
        max-height: 40%;
        display: none;
        padding: 0 1;
        border-top: solid $primary;
        overflow-y: auto;
    }
    #detail-panel.visible {
        display: block;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        background: $accent;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("tab", "toggle_view", "Summary/Raw", show=False),
        Binding("slash", "search", "Search"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("enter", "select_row", "Detail", show=False),
        Binding("escape", "exit_browse", "Resume", show=False),
    ]

    def __init__(
        self,
        *,
        pipeline: IngestPipeline,
        buffer: ObservableBuffer,
        pane_name: str = "radar",
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._buffer = buffer
        self._pane_name = pane_name

        # Mode: "streaming" (auto-scroll, no cursor) or "browsing" (cursor, no auto-scroll)
        self._mode = "streaming"

        # Active filter
        self._filter = FilterSpec()

        # All events that passed the filter (mirrors what the DataTable shows)
        self._visible_events: list[LogEvent] = []

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield FilterBar(id="filter-bar")
        yield LogListView(id="log-list")
        yield DetailPanel(id="detail-panel")
        yield RadarStatusBar(id="status-bar")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._set_tmux_pane_title()
        self.run_worker(self._run_pipeline(), exclusive=True, name="ingest")
        self.set_interval(0.1, self._poll_events)

    def _set_tmux_pane_title(self) -> None:
        if os.environ.get("TMUX") and self._pane_name:
            try:
                subprocess.run(
                    ["tmux", "select-pane", "-T", self._pane_name],
                    check=False,
                    capture_output=True,
                )
            except FileNotFoundError:
                pass

    # ------------------------------------------------------------------
    # Background ingest
    # ------------------------------------------------------------------

    async def _run_pipeline(self) -> None:
        try:
            await self._pipeline.run()
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # Periodic poll for new events
    # ------------------------------------------------------------------

    def _poll_events(self) -> None:
        pending = self._buffer.drain_pending()
        if not pending:
            self._update_status_bar(new_count=0)
            return

        log_list = self.query_one("#log-list", LogListView)
        added = 0
        for event in pending:
            if self._filter.matches(event):
                log_list.add_event(event)
                self._visible_events.append(event)
                added += 1

        if added and self._mode == "streaming":
            log_list.scroll_end(animate=False)

        self._update_status_bar(new_count=len(pending))

        # Update detail panel if in browsing mode (cursor might point to newly visible row)
        if self._mode == "browsing":
            self._update_detail_for_cursor()

    def _update_status_bar(self, *, new_count: int) -> None:
        status = self.query_one("#status-bar", RadarStatusBar)
        status.update_stats(
            total=self._buffer.count,
            filtered=len(self._visible_events),
            sources=self._buffer.sources,
            mode=self._mode,
            new_count=new_count,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_toggle_filter(self) -> None:
        fb = self.query_one("#filter-bar")
        fb.toggle_class("visible")
        if fb.has_class("visible"):
            try:
                self.query_one("#filter-source", Input).focus()
            except Exception:
                pass

    def action_toggle_view(self) -> None:
        detail = self.query_one("#detail-panel", DetailPanel)
        if detail.has_class("visible"):
            detail.toggle_view()

    def action_search(self) -> None:
        fb = self.query_one("#filter-bar")
        if not fb.has_class("visible"):
            fb.add_class("visible")
        try:
            self.query_one("#filter-pattern", Input).focus()
        except Exception:
            pass

    def action_cursor_down(self) -> None:
        self._enter_browse_mode()
        log_list = self.query_one("#log-list", LogListView)
        log_list.action_cursor_down()
        self._update_detail_for_cursor()

    def action_cursor_up(self) -> None:
        self._enter_browse_mode()
        log_list = self.query_one("#log-list", LogListView)
        log_list.action_cursor_up()
        self._update_detail_for_cursor()

    def action_scroll_top(self) -> None:
        self._enter_browse_mode()
        log_list = self.query_one("#log-list", LogListView)
        log_list.move_cursor(row=0)
        self._update_detail_for_cursor()

    def action_scroll_bottom(self) -> None:
        log_list = self.query_one("#log-list", LogListView)
        if self._visible_events:
            log_list.move_cursor(row=len(self._visible_events) - 1)
        self._update_detail_for_cursor()

    def action_select_row(self) -> None:
        """Enter/toggle detail panel for the selected row."""
        detail = self.query_one("#detail-panel", DetailPanel)
        if self._mode == "streaming":
            self._enter_browse_mode()

        event = self.query_one("#log-list", LogListView).get_event_at_cursor()
        if event is None:
            return

        if detail.has_class("visible"):
            # Already showing — hide it
            detail.remove_class("visible")
            detail.set_event(None)
        else:
            detail.add_class("visible")
            detail.set_event(event)

    def action_exit_browse(self) -> None:
        """Return to streaming mode: hide detail, scroll to end."""
        detail = self.query_one("#detail-panel", DetailPanel)
        detail.remove_class("visible")
        detail.set_event(None)
        self._exit_browse_mode()

    # ------------------------------------------------------------------
    # Browse / stream mode
    # ------------------------------------------------------------------

    def _enter_browse_mode(self) -> None:
        if self._mode == "browsing":
            return
        self._mode = "browsing"
        log_list = self.query_one("#log-list", LogListView)
        log_list.cursor_type = "row"
        # Place cursor at the last row
        if self._visible_events:
            log_list.move_cursor(row=len(self._visible_events) - 1)

    def _exit_browse_mode(self) -> None:
        self._mode = "streaming"
        log_list = self.query_one("#log-list", LogListView)
        log_list.cursor_type = "none"
        log_list.scroll_end(animate=False)

    def _update_detail_for_cursor(self) -> None:
        detail = self.query_one("#detail-panel", DetailPanel)
        if not detail.has_class("visible"):
            return
        event = self.query_one("#log-list", LogListView).get_event_at_cursor()
        detail.set_event(event)

    # ------------------------------------------------------------------
    # Filter changes
    # ------------------------------------------------------------------

    def on_filter_bar_changed(self, message: FilterBar.Changed) -> None:
        self._filter = message.spec
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Rebuild the DataTable from the full ring buffer with active filter."""
        log_list = self.query_one("#log-list", LogListView)
        log_list.clear_events()
        self._visible_events.clear()

        for event in self._buffer.filter(self._filter):
            log_list.add_event(event)
            self._visible_events.append(event)

        if self._mode == "streaming":
            log_list.scroll_end(animate=False)

        self._update_status_bar(new_count=0)
