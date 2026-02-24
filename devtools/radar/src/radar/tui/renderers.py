"""Pluggable summary renderers for log events.

Each source can register a custom renderer that produces a concise one-liner
from a LogEvent.  The summary is what both humans and agents see in the log
list view.  Raw detail is always available via detail panel toggle.

Renderer lookup uses ``event.source`` (logical source ID from config).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

from rich.text import Text

from radar.models import Level, LogEvent

# Level -> Rich style mapping
LEVEL_STYLES: dict[Level, str] = {
    Level.DEBUG: "dim",
    Level.INFO: "blue",
    Level.WARN: "yellow",
    Level.ERROR: "red",
    Level.FATAL: "bold red",
}


class SummaryRenderer(ABC):
    """Base class for source-specific summary renderers."""

    @abstractmethod
    def render(self, event: LogEvent) -> Text: ...


class DefaultSummaryRenderer(SummaryRenderer):
    """Default: timestamp | level (colored) | source | message (truncated)."""

    def render(self, event: LogEvent) -> Text:
        text = Text()
        text.append(event.timestamp.strftime("%H:%M:%S.%f")[:12], style="dim cyan")
        text.append(" ")
        text.append(f"{event.level.name:<5}", style=LEVEL_STYLES.get(event.level, ""))
        text.append(" ")
        text.append(f"{event.source:<20}", style="green")
        text.append(" ")
        text.append(event.message[:200])
        return text


class MCPProtocolRenderer(SummaryRenderer):
    """MCP JSONL: method name, tool, direction (req/res), duration."""

    def render(self, event: LogEvent) -> Text:
        text = Text()
        text.append(event.timestamp.strftime("%H:%M:%S.%f")[:12], style="dim cyan")
        text.append(" ")

        s = event.structured or {}

        if "params" in s:
            direction = "req"
        elif "result" in s or "error" in s:
            direction = "res"
        else:
            direction = "???"

        text.append(f"{direction:<3}", style=LEVEL_STYLES.get(event.level, ""))
        text.append(" ")

        method = s.get("method", "")
        if method:
            text.append(method, style="bold")
        else:
            text.append(event.message[:120])

        # Show tool name for tool calls
        params = s.get("params", {})
        if isinstance(params, dict) and "name" in params:
            text.append(f" ({params['name']})", style="yellow")

        return text


class ConsoleLogRenderer(SummaryRenderer):
    """Pipe-separated SketchUp console: level + source + message."""

    def render(self, event: LogEvent) -> Text:
        text = Text()
        text.append(event.timestamp.strftime("%H:%M:%S.%f")[:12], style="dim cyan")
        text.append(" ")
        text.append(f"{event.level.name:<5}", style=LEVEL_STYLES.get(event.level, ""))
        text.append(" ")
        text.append(event.message[:200])
        return text


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

RENDERERS: dict[str, SummaryRenderer] = {
    "mcp-protocol": MCPProtocolRenderer(),
    "runtime-console": ConsoleLogRenderer(),
}

_default_renderer = DefaultSummaryRenderer()


def get_renderer(source: str) -> SummaryRenderer:
    """Get renderer for a source, falling back to default."""
    return RENDERERS.get(source, _default_renderer)


def render_summary(event: LogEvent) -> Text:
    """Render event summary using the appropriate renderer."""
    return get_renderer(event.source).render(event)


def render_raw(event: LogEvent) -> Text:
    """Original raw text with metadata header.  No truncation.

    Always available via detail panel toggle -- not pluggable.
    """
    text = Text()
    text.append(f"EID: {event.eid}\n", style="dim")
    text.append(f"Source: {event.source} ({event.source_path})\n", style="dim")
    text.append(f"Timestamp: {event.timestamp.isoformat()}\n", style="dim")
    text.append(f"Level: {event.level.name}\n", style="dim")
    text.append("\u2500" * 40 + "\n", style="dim")
    text.append(event.raw)
    if event.structured:
        text.append("\n" + "\u2500" * 40 + "\n", style="dim")
        text.append(json.dumps(event.structured, indent=2, default=str), style="cyan")
    return text


def render_plain_line(event: LogEvent) -> str:
    """Format a single event for plain stdout mode (no Rich markup).

    Includes the short event ID for cross-reference with TUI search.
    """
    ts = event.timestamp.strftime("%H:%M:%S.%f")[:12]
    msg = event.message[:200]
    return f"[e:{event.eid}] {ts} {event.level.name:<5} {event.source:<20} {msg}"
