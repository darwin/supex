"""Pluggable summary renderers for log events.

Each source can register a custom renderer that produces a concise one-liner
from a LogEvent.  The summary is what both humans and agents see in the log
list view.  Raw detail is always available via detail panel toggle.

Renderer lookup uses ``event.source`` (logical source ID from config).

Hot-reload: renderer module files are watched for changes and re-imported
on save without restarting Radar.  On reload failure the last known-good
renderer is kept and a warning is recorded.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text

from radar.models import Level, LogEvent

log = logging.getLogger(__name__)

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
# RendererLoadResult
# ---------------------------------------------------------------------------


@dataclass
class RendererLoadResult:
    """Structured result from a renderer module load/reload attempt."""

    success: bool
    module_path: str
    source: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------
# RendererRegistry
# ---------------------------------------------------------------------------


class RendererRegistry:
    """Registry of source-specific summary renderers with hot-reload support.

    External renderer modules are Python files that define a module-level
    ``RENDERERS`` dict mapping source names to ``SummaryRenderer`` instances.
    The registry watches these files and reloads them on change.
    """

    def __init__(self) -> None:
        self._renderers: dict[str, SummaryRenderer] = {}
        self._default = DefaultSummaryRenderer()
        # hot-reload tracking: module_path -> list of source names it provides
        self._path_sources: dict[str, list[str]] = {}
        self._warnings: list[str] = []

    # -- dict-like interface for backward compatibility --

    def get(self, source: str, default: SummaryRenderer | None = None) -> SummaryRenderer:
        return self._renderers.get(source, default if default is not None else self._default)

    def __getitem__(self, source: str) -> SummaryRenderer:
        return self._renderers[source]

    def __contains__(self, source: str) -> bool:
        return source in self._renderers

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> int:
        return len(self._renderers)

    def __iter__(self):
        return iter(self._renderers)

    def items(self):
        return self._renderers.items()

    # -- registration --

    def register(self, source: str, renderer: SummaryRenderer) -> None:
        """Register a renderer for a source (built-in, not file-tracked)."""
        self._renderers[source] = renderer

    def load_module(self, module_path: str) -> list[RendererLoadResult]:
        """Load renderer module from *module_path* and register its RENDERERS.

        The module must define a module-level ``RENDERERS`` dict mapping source
        names to ``SummaryRenderer`` instances.

        Returns a list of :class:`RendererLoadResult` for each source found.
        """
        results: list[RendererLoadResult] = []
        abs_path = str(Path(module_path).resolve())

        try:
            module = self._import_file(abs_path)
        except Exception as exc:
            msg = f"Failed to load {module_path}: {exc}"
            log.warning(msg)
            self._warnings.append(msg)
            return [RendererLoadResult(success=False, module_path=abs_path, error=str(exc))]

        renderers_dict = getattr(module, "RENDERERS", None)
        if not isinstance(renderers_dict, dict):
            msg = f"Module {module_path} has no RENDERERS dict"
            log.warning(msg)
            self._warnings.append(msg)
            return [RendererLoadResult(success=False, module_path=abs_path, error=msg)]

        sources_for_path: list[str] = []
        for source, renderer in renderers_dict.items():
            if isinstance(renderer, SummaryRenderer):
                self._renderers[source] = renderer
                sources_for_path.append(source)
                results.append(RendererLoadResult(success=True, module_path=abs_path, source=source))
            else:
                msg = f"Source '{source}' renderer is not a SummaryRenderer: {type(renderer)}"
                log.warning(msg)
                self._warnings.append(msg)
                results.append(RendererLoadResult(success=False, module_path=abs_path, source=source, error=msg))

        if sources_for_path:
            self._path_sources[abs_path] = sources_for_path

        return results

    def reload_module(self, module_path: str) -> list[RendererLoadResult]:
        """Reload a previously loaded module, swapping renderers atomically.

        On failure the last known-good renderers are kept for all sources
        provided by this module.
        """
        abs_path = str(Path(module_path).resolve())
        old_sources = self._path_sources.get(abs_path, [])

        try:
            module = self._import_file(abs_path)
        except Exception as exc:
            msg = f"Reload failed for {module_path}: {exc}"
            log.warning(msg)
            self._warnings.append(msg)
            return [RendererLoadResult(success=False, module_path=abs_path, error=str(exc))]

        renderers_dict = getattr(module, "RENDERERS", None)
        if not isinstance(renderers_dict, dict):
            msg = f"Reload: module {module_path} has no RENDERERS dict"
            log.warning(msg)
            self._warnings.append(msg)
            return [RendererLoadResult(success=False, module_path=abs_path, error=msg)]

        # Validate all renderers before swapping any
        new_renderers: dict[str, SummaryRenderer] = {}
        for source, renderer in renderers_dict.items():
            if not isinstance(renderer, SummaryRenderer):
                # Partial failure — rollback to old
                msg = f"Reload: source '{source}' renderer is not a SummaryRenderer"
                log.warning(msg)
                self._warnings.append(msg)
                return [RendererLoadResult(success=False, module_path=abs_path, source=source, error=msg)]
            new_renderers[source] = renderer

        # Atomic swap: remove old sources, add new
        for s in old_sources:
            self._renderers.pop(s, None)
        for source, renderer in new_renderers.items():
            self._renderers[source] = renderer
        self._path_sources[abs_path] = list(new_renderers.keys())

        return [
            RendererLoadResult(success=True, module_path=abs_path, source=s)
            for s in new_renderers
        ]

    @property
    def watched_paths(self) -> set[str]:
        """Set of absolute module paths tracked for hot-reload."""
        return set(self._path_sources.keys())

    @property
    def warnings(self) -> list[str]:
        """Accumulated reload warnings (newest last)."""
        return self._warnings

    def pop_warnings(self) -> list[str]:
        """Return and clear accumulated warnings."""
        w = self._warnings
        self._warnings = []
        return w

    @staticmethod
    def _import_file(abs_path: str):
        """Import a Python file by absolute path, bypassing all caches."""
        import types

        mod_name = f"_radar_renderer_{Path(abs_path).stem}"
        sys.modules.pop(mod_name, None)

        with open(abs_path) as f:
            source = f.read()

        code = compile(source, abs_path, "exec")
        module = types.ModuleType(mod_name)
        module.__file__ = abs_path
        exec(code, module.__dict__)  # noqa: S102
        return module


# ---------------------------------------------------------------------------
# RendererReloader
# ---------------------------------------------------------------------------


@dataclass
class RendererReloader:
    """Polls renderer module files for changes and triggers reload.

    Designed to be driven by the TUI polling timer (call :meth:`check` each
    tick) or by an async loop (call :meth:`run`).
    """

    registry: RendererRegistry
    poll_interval: float = 1.0
    _mtimes: dict[str, float] = field(default_factory=dict, repr=False)

    def snapshot_mtimes(self) -> None:
        """Record current mtime for all watched paths."""
        for path in self.registry.watched_paths:
            try:
                self._mtimes[path] = os.path.getmtime(path)
            except OSError:
                pass

    def check(self) -> list[RendererLoadResult]:
        """Check all watched files for changes; reload if needed.

        Returns results only for files that were actually reloaded.
        """
        results: list[RendererLoadResult] = []
        for path in list(self.registry.watched_paths):
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            prev = self._mtimes.get(path)
            if prev is not None and mtime != prev:
                self._mtimes[path] = mtime
                results.extend(self.registry.reload_module(path))
            elif prev is None:
                self._mtimes[path] = mtime
        return results

    async def run(self) -> None:
        """Async poll loop — runs until cancelled."""
        import asyncio

        self.snapshot_mtimes()
        while True:
            await asyncio.sleep(self.poll_interval)
            self.check()


# ---------------------------------------------------------------------------
# Module-level registry instance and convenience functions
# ---------------------------------------------------------------------------

RENDERERS = RendererRegistry()
RENDERERS.register("mcp-protocol", MCPProtocolRenderer())
RENDERERS.register("runtime-console", ConsoleLogRenderer())

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
