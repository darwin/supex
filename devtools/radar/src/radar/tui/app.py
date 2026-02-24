"""Main Textual application for Radar TUI."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding
from textual.widgets import Input

from radar.buffer import ObservableBuffer
from radar.models import FilterSpec, Level, LogEvent
from radar.tui.renderers import RendererReloader, RENDERERS
from radar.tui.views import DetailPanel, FilterBar, LogListView, RadarStatusBar

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from radar.ingest import IngestPipeline


def detect_color_system() -> str:
    """Detect terminal color capability.

    Returns one of: "truecolor", "256", "standard", "none".
    Textual/Rich handle the actual rendering; this is for logging
    and informing the user what mode is active.
    """
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return "truecolor"
    term = os.environ.get("TERM", "")
    if "256color" in term:
        return "256"
    if term:
        return "standard"
    return "none"


def detect_terminal_info() -> dict[str, str]:
    """Gather terminal environment info for diagnostics."""
    return {
        "TERM": os.environ.get("TERM", ""),
        "COLORTERM": os.environ.get("COLORTERM", ""),
        "tmux": "yes" if os.environ.get("TMUX") else "no",
        "ssh": "yes" if os.environ.get("SSH_CONNECTION") else "no",
        "colors": detect_color_system(),
    }


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
    LogListView.detail-open {
        height: 4;
    }
    #detail-panel {
        height: 1fr;
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

    # Keybindings chosen to avoid conflict with default tmux prefix (Ctrl+b).
    # All bindings are single printable keys or standard terminal keys
    # (tab, enter, escape) — no Ctrl combinations that could clash.
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "interrupt", "Ctrl+C x2 to quit", show=False, priority=True),
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

    _CTRL_C_WINDOW = 1.0  # seconds between Ctrl+C presses

    def __init__(
        self,
        *,
        pipeline: IngestPipeline,
        buffer: ObservableBuffer,
        pane_name: str = "radar",
        mouse: bool = True,
        initial_filter: FilterSpec | None = None,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._buffer = buffer
        self._pane_name = pane_name
        self._mouse = mouse

        # Mode: "streaming" (auto-scroll, no cursor) or "browsing" (cursor, no auto-scroll)
        self._mode = "streaming"
        self._last_ctrl_c: float = 0.0

        # Active filter (may be pre-set from CLI)
        self._filter = initial_filter or FilterSpec()
        self._initial_filter = initial_filter

        # All events that passed the filter (mirrors what the DataTable shows)
        self._visible_events: list[LogEvent] = []

        # Hot-reload for renderer modules
        self._renderer_reloader = RendererReloader(registry=RENDERERS)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield FilterBar(id="filter-bar")
        yield LogListView(id="log-list")
        yield DetailPanel(id="detail-panel")
        yield RadarStatusBar(id="status-bar")

    def run(self, **kwargs) -> None:
        """Launch the app, forwarding the mouse setting."""
        kwargs.setdefault("mouse", self._mouse)
        return super().run(**kwargs)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self._set_tmux_pane_title()
        self._log_terminal_info()
        self._renderer_reloader.snapshot_mtimes()
        self._apply_initial_filter()
        self.query_one("#log-list", LogListView).focus()
        self.run_worker(self._run_pipeline(), exclusive=True, name="ingest")
        self.set_interval(0.1, self._poll_events)
        self.set_interval(1.0, self._poll_renderer_reload)

    def _apply_initial_filter(self) -> None:
        """Pre-populate FilterBar inputs from CLI-provided filter."""
        if self._initial_filter is None:
            return
        f = self._initial_filter
        has_filter = f.sources or f.min_level > Level.DEBUG or f.pattern
        if not has_filter:
            return

        fb = self.query_one("#filter-bar", FilterBar)
        fb.set_initial_values(
            sources=",".join(f.sources) if f.sources else "",
            level=f.min_level.name if f.min_level > Level.DEBUG else "",
            pattern=f.pattern.pattern if f.pattern else "",
        )
        # Show filter bar when pre-set filters are active
        fb.add_class("visible")

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

    def _log_terminal_info(self) -> None:
        """Show terminal capabilities in subtitle for diagnostics."""
        info = detect_terminal_info()
        parts = []
        if info["tmux"] == "yes":
            parts.append("tmux")
        if info["ssh"] == "yes":
            parts.append("ssh")
        parts.append(f"colors={info['colors']}")
        if not self._mouse:
            parts.append("mouse=off")
        self.sub_title = " | ".join(parts)

        # Warn about tmux escape-time if it's set high (causes Escape key delay)
        if info["tmux"] == "yes":
            self._check_tmux_escape_time()

    def _check_tmux_escape_time(self) -> None:
        """Warn if tmux escape-time is high (causes sluggish Escape key)."""
        try:
            result = subprocess.run(
                ["tmux", "show-option", "-gv", "escape-time"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                escape_time = int(result.stdout.strip())
                if escape_time > 100:
                    self.notify(
                        f"tmux escape-time is {escape_time}ms (>100ms). "
                        "Consider: tmux set -g escape-time 10",
                        title="tmux",
                        severity="warning",
                        timeout=8,
                    )
        except (FileNotFoundError, ValueError):
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
        matched = [e for e in pending if self._filter.matches(e)]

        if matched:
            log_list.add_events_batch(matched)
            self._visible_events.extend(matched)

        if matched and self._mode == "streaming":
            log_list.scroll_end(animate=False)

        self._update_status_bar(new_count=len(pending))

        # Update detail panel if in browsing mode (cursor might point to newly visible row)
        if self._mode == "browsing":
            self._update_detail_for_cursor()

    def _poll_renderer_reload(self) -> None:
        results = self._renderer_reloader.check()
        if not results:
            return
        # Log warnings for any failures
        for r in results:
            if not r.success:
                self.notify(
                    f"Renderer reload failed: {r.error}",
                    title="renderer",
                    severity="warning",
                    timeout=5,
                )

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

    def _show_detail(self, event: LogEvent) -> None:
        """Show detail panel for the given event, shrink log list."""
        detail = self.query_one("#detail-panel", DetailPanel)
        log_list = self.query_one("#log-list", LogListView)
        detail.add_class("visible")
        log_list.add_class("detail-open")
        detail.set_event(event)
        # Defer centering until after layout reflow (height change needs a render pass)
        self.call_after_refresh(self._center_cursor, log_list)

    def _hide_detail(self) -> None:
        """Hide detail panel, restore log list height."""
        detail = self.query_one("#detail-panel", DetailPanel)
        log_list = self.query_one("#log-list", LogListView)
        detail.remove_class("visible")
        log_list.remove_class("detail-open")
        detail.set_event(None)

    def action_select_row(self) -> None:
        """Enter/toggle detail panel for the selected row."""
        detail = self.query_one("#detail-panel", DetailPanel)
        if self._mode == "streaming":
            self._enter_browse_mode()

        event = self.query_one("#log-list", LogListView).get_event_at_cursor()
        if event is None:
            return

        if detail.has_class("visible"):
            self._hide_detail()
        else:
            self._show_detail(event)

    def action_exit_browse(self) -> None:
        """Return to streaming mode: hide detail, scroll to end."""
        self._hide_detail()
        self._exit_browse_mode()

    def action_interrupt(self) -> None:
        """Quit on double Ctrl+C within the time window."""
        now = time.monotonic()
        if now - self._last_ctrl_c < self._CTRL_C_WINDOW:
            self.exit()
        else:
            self._last_ctrl_c = now
            self.notify("Press Ctrl+C again to quit", timeout=2)

    # ------------------------------------------------------------------
    # Browse / stream mode
    # ------------------------------------------------------------------

    def _enter_browse_mode(self) -> None:
        if self._mode == "browsing":
            return
        self._mode = "browsing"
        log_list = self.query_one("#log-list", LogListView)
        log_list.focus()
        # Place cursor at the last row
        if self._visible_events:
            log_list.move_cursor(row=len(self._visible_events) - 1)

    def _exit_browse_mode(self) -> None:
        self._mode = "streaming"
        log_list = self.query_one("#log-list", LogListView)
        log_list.scroll_end(animate=False)

    def _center_cursor(self, log_list: LogListView) -> None:
        """Scroll so the cursor row is in the middle of the 3 visible rows.

        TODO: scroll centering works in tmux but not reliably outside it.
        Needs investigation into Textual DataTable scroll coordinate system.
        """
        pass

    def _update_detail_for_cursor(self) -> None:
        detail = self.query_one("#detail-panel", DetailPanel)
        if not detail.has_class("visible"):
            return
        log_list = self.query_one("#log-list", LogListView)
        event = log_list.get_event_at_cursor()
        detail.set_event(event)
        self.call_after_refresh(self._center_cursor, log_list)

    # ------------------------------------------------------------------
    # DataTable row selection (Enter handled by DataTable in browse mode)
    # ------------------------------------------------------------------

    def on_log_list_view_event_selected(self, message: LogListView.EventSelected) -> None:
        """Handle Enter on a DataTable row — toggle detail panel."""
        detail = self.query_one("#detail-panel", DetailPanel)
        if detail.has_class("visible"):
            self._hide_detail()
        else:
            self._show_detail(message.event)

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

        matched = self._buffer.filter(self._filter)
        if matched:
            log_list.add_events_batch(matched)
            self._visible_events.extend(matched)

        if self._mode == "streaming":
            log_list.scroll_end(animate=False)

        self._update_status_bar(new_count=0)
