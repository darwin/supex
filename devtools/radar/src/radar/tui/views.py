"""TUI view components for Radar log aggregator.

Widgets:
- LogListView: scrollable DataTable of log events (virtual rendering)
- DetailPanel: expanded event view with summary/raw toggle
- FilterBar: source, level, regex inputs with debounced filtering
- RadarStatusBar: event counts, active sources, stream rate
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from radar.models import FilterSpec, Level, LogEvent
from radar.tui.renderers import LEVEL_STYLES, render_raw, render_summary

if TYPE_CHECKING:
    from textual.app import ComposeResult

# ---------------------------------------------------------------------------
# LogListView
# ---------------------------------------------------------------------------

_COLUMNS = [
    ("EID", 7),
    ("Time", 13),
    ("Level", 6),
    ("Source", 21),
    ("Message", None),  # auto-fill remaining width
]


class LogListView(DataTable):
    """Virtual-scrolling log event list backed by a DataTable."""

    class EventSelected(Message):
        """Posted when the user presses Enter on a row."""

        def __init__(self, event: LogEvent) -> None:
            super().__init__()
            self.event = event

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._events: list[LogEvent] = []
        self._eid_to_index: dict[str, int] = {}
        self.cursor_type = "none"  # streaming mode default
        self.zebra_stripes = True

    def on_mount(self) -> None:
        for label, width in _COLUMNS:
            if width is not None:
                self.add_column(label, width=width, key=label)
            else:
                self.add_column(label, key=label)

    @staticmethod
    def _make_row(event: LogEvent) -> tuple:
        """Build a row tuple for a single event."""
        level_style = LEVEL_STYLES.get(event.level, "")
        return (
            Text(event.eid, style="dim"),
            Text(event.timestamp.strftime("%H:%M:%S.%f")[:12], style="dim cyan"),
            Text(f"{event.level.name:<5}", style=level_style),
            Text(event.source, style="green"),
            event.message[:200],
        )

    def add_event(self, event: LogEvent) -> None:
        """Append a single event as a new row."""
        self._events.append(event)
        self._eid_to_index[event.eid] = len(self._events) - 1
        self.add_row(*self._make_row(event), key=event.eid)

    def add_events_batch(self, events: list[LogEvent]) -> None:
        """Append multiple events efficiently in a single batch."""
        if not events:
            return
        base_idx = len(self._events)
        rows = []
        for i, event in enumerate(events):
            self._events.append(event)
            self._eid_to_index[event.eid] = base_idx + i
            rows.append(self._make_row(event))
        self.add_rows(rows)

    def clear_events(self) -> None:
        """Remove all rows and reset event tracking."""
        self.clear()
        self._events.clear()
        self._eid_to_index.clear()

    def get_event_at_cursor(self) -> LogEvent | None:
        """Return the LogEvent under the current cursor position."""
        if not self._events:
            return None
        idx = self.cursor_row
        if 0 <= idx < len(self._events):
            return self._events[idx]
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Forward row selection as an EventSelected message."""
        idx = event.cursor_row
        if 0 <= idx < len(self._events):
            self.post_message(self.EventSelected(self._events[idx]))


# ---------------------------------------------------------------------------
# DetailPanel
# ---------------------------------------------------------------------------


class DetailPanel(Static):
    """Expanded view of a single event.  Toggles between summary and raw.

    Lazy rendering: content is only computed when the panel is visible.
    Setting an event while hidden just stores the reference; the actual
    render happens when the panel becomes visible.
    """

    show_raw: reactive[bool] = reactive(False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._event: LogEvent | None = None
        self._dirty = False

    def set_event(self, event: LogEvent | None) -> None:
        self._event = event
        self._dirty = True
        if self.has_class("visible"):
            self._render_now()

    def toggle_view(self) -> None:
        self.show_raw = not self.show_raw

    def watch_show_raw(self, _value: bool) -> None:
        self._dirty = True
        if self.has_class("visible"):
            self._render_now()

    def on_show(self) -> None:
        if self._dirty:
            self._render_now()

    def _render_now(self) -> None:
        self._dirty = False
        if self._event is None:
            self.update("")
            return
        if self.show_raw:
            self.update(render_raw(self._event))
        else:
            self.update(render_summary(self._event))


# ---------------------------------------------------------------------------
# FilterBar
# ---------------------------------------------------------------------------

_LEVEL_NAMES = {"DEBUG", "INFO", "WARN", "ERROR", "FATAL"}


class FilterBar(Widget):
    """Filter controls: source, level, and regex pattern.

    Posts a ``FilterBar.Changed`` message (debounced ~200ms) when any input
    changes.
    """

    class Changed(Message):
        """Posted when filter criteria change."""

        def __init__(self, spec: FilterSpec) -> None:
            super().__init__()
            self.spec = spec

    def compose(self) -> ComposeResult:
        with Horizontal(id="filter-inputs"):
            yield Input(placeholder="source (comma-sep)", id="filter-source")
            yield Input(placeholder="level (DEBUG..FATAL)", id="filter-level")
            yield Input(placeholder="regex pattern", id="filter-pattern")

    def on_mount(self) -> None:
        self._debounce_timer = None

    def set_initial_values(self, *, sources: str, level: str, pattern: str) -> None:
        """Pre-populate filter inputs from CLI flags (call before or during mount)."""
        if sources:
            self.query_one("#filter-source", Input).value = sources
        if level:
            self.query_one("#filter-level", Input).value = level
        if pattern:
            self.query_one("#filter-pattern", Input).value = pattern

    @on(Input.Changed)
    def _on_input_changed(self, _event: Input.Changed) -> None:
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        self._debounce_timer = self.set_timer(0.2, self._emit_filter)

    def _emit_filter(self) -> None:
        source_input = self.query_one("#filter-source", Input).value.strip()
        level_input = self.query_one("#filter-level", Input).value.strip().upper()
        pattern_input = self.query_one("#filter-pattern", Input).value.strip()

        sources = [s.strip() for s in source_input.split(",") if s.strip()] if source_input else []
        min_level = Level.DEBUG
        if level_input in _LEVEL_NAMES:
            min_level = Level[level_input]

        compiled = None
        if pattern_input:
            try:
                compiled = re.compile(pattern_input)
            except re.error:
                pass

        self.post_message(self.Changed(FilterSpec(sources=sources, min_level=min_level, pattern=compiled)))


# ---------------------------------------------------------------------------
# RadarStatusBar
# ---------------------------------------------------------------------------


class RadarStatusBar(Static):
    """Bottom status line: total events, filtered count, sources, rate."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._total = 0
        self._filtered = 0
        self._sources: set[str] = set()
        self._mode = "streaming"
        self._rate_window: list[float] = []

    def update_stats(
        self,
        *,
        total: int,
        filtered: int,
        sources: set[str],
        mode: str,
        new_count: int = 0,
    ) -> None:
        now = time.monotonic()
        if new_count > 0:
            self._rate_window.extend([now] * new_count)
        cutoff = now - 5.0
        self._rate_window = [t for t in self._rate_window if t > cutoff]
        rate = len(self._rate_window) / 5.0

        self._total = total
        self._filtered = filtered
        self._sources = sources
        self._mode = mode

        text = Text()
        text.append(f" Total: {total}", style="bold")
        text.append(f"  Shown: {filtered}", style="dim")
        text.append(f"  Sources: {len(sources)}", style="dim")
        text.append(f"  Rate: {rate:.1f}/s", style="dim")
        text.append(f"  [{mode}]", style="bold cyan")
        self.update(text)
