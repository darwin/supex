"""Radar CLI entry point."""

from __future__ import annotations

import asyncio
import glob as globmod
import os
import tomllib
from pathlib import Path
from typing import Annotated, Optional

import typer

from .models import FilterSpec, Level
from .tailer import TailSource

app = typer.Typer(
    name="radar",
    help="Supex Radar — single-host log aggregator with TUI.\n\nExamples:\n\n  radar watch                        # default supex logs\n\n  radar watch --plain                # plain stdout stream\n\n  radar watch --level ERROR          # only ERROR+ events\n\n  radar watch --source cli-driver    # single source\n\n  radar watch -c radar.toml          # custom config\n\n  radar watch .tmp/logs/*.log        # ad-hoc files",
    add_completion=False,
)

# ---------------------------------------------------------------------------
# Built-in default sources (post-log-layout-unify)
# ---------------------------------------------------------------------------

_DEFAULT_SOURCES: list[dict[str, str]] = [
    {"name": "mcp-protocol", "path": ".tmp/logs/mcp-protocol.jsonl", "parser": "jsonl"},
    {"name": "mcp-stderr", "path": ".tmp/logs/mcp-stderr.log", "parser": "pipe"},
    {"name": "cli-driver", "path": ".tmp/logs/cli-driver.log", "parser": "pipe"},
    {"name": "cli-stdout", "path": ".tmp/logs/cli-stdout.log", "parser": "plain"},
    {"name": "cli-stderr", "path": ".tmp/logs/cli-stderr.log", "parser": "pipe"},
    {"name": "runtime-console", "path": ".tmp/logs/runtime-console.log", "parser": "pipe"},
    {"name": "runtime-stdout", "path": ".tmp/logs/runtime-stdout.log", "parser": "plain"},
    {"name": "runtime-stderr", "path": ".tmp/logs/runtime-stderr.log", "parser": "plain"},
    {"name": "vcad-sidecar", "path": ".tmp/logs/vcad-sidecar-stderr.log", "parser": "pipe"},
    {"name": "vcad-events", "path": ".tmp/logs/vcad-events.jsonl", "parser": "jsonl"},
]

_LEVEL_NAMES = [lv.name for lv in Level]


def _resolve_workspace() -> Path:
    """Effective workspace root: $SUPEX_WORKSPACE or cwd."""
    ws = os.environ.get("SUPEX_WORKSPACE")
    return Path(ws) if ws else Path.cwd()


def _expand_glob(pattern: str, root: Path) -> list[Path]:
    """Expand a glob pattern relative to root directory. Returns sorted unique paths."""
    full = str(root / pattern)
    return sorted(set(Path(p) for p in globmod.glob(full)))


def _dedup_sources(sources: list[TailSource]) -> list[TailSource]:
    """Remove duplicate sources by resolved path, keeping the first occurrence."""
    seen: set[str] = set()
    result: list[TailSource] = []
    for s in sources:
        key = str(s.source_path.resolve())
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def _resolve_sources(
    mode: str,
    files: list[Path] | None,
    config_path: Path | None,
) -> tuple[list[TailSource], dict[str, str]]:
    """Resolve TailSource list and parser overrides for the selected mode."""
    if mode == "ad-hoc":
        assert files is not None
        sources = [TailSource(source=f.stem, source_path=f) for f in files]
        return _dedup_sources(sources), {}

    if mode == "config":
        assert config_path is not None
        return _load_config(config_path)

    # Default mode
    workspace = _resolve_workspace()
    sources: list[TailSource] = []
    parser_overrides: dict[str, str] = {}
    for src_def in _DEFAULT_SOURCES:
        path = workspace / src_def["path"]
        sources.append(TailSource(source=src_def["name"], source_path=path))
        parser_overrides[src_def["name"]] = src_def["parser"]
    return sources, parser_overrides


def _load_config(config_path: Path) -> tuple[list[TailSource], dict[str, str]]:
    """Load a TOML config file and resolve sources."""
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    workspace = Path(config.get("workspace", "."))
    if not workspace.is_absolute():
        workspace = (config_path.parent / workspace).resolve()

    sources: list[TailSource] = []
    parser_overrides: dict[str, str] = {}
    for src in config.get("source", []):
        pattern = src["path"]
        # Expand globs in config paths
        if any(c in pattern for c in ("*", "?", "[")):
            expanded = _expand_glob(pattern, workspace)
            for p in expanded:
                name = f"{src['name']}:{p.stem}" if len(expanded) > 1 else src["name"]
                sources.append(TailSource(source=name, source_path=p))
                if "parser" in src:
                    parser_overrides[name] = src["parser"]
        else:
            path = workspace / pattern
            sources.append(TailSource(source=src["name"], source_path=path))
            if "parser" in src:
                parser_overrides[src["name"]] = src["parser"]

    return _dedup_sources(sources), parser_overrides


def _build_initial_filter(
    level: str | None,
    source: list[str] | None,
) -> FilterSpec:
    """Build a FilterSpec from CLI pre-set filter options."""
    min_level = Level.DEBUG
    if level:
        level_upper = level.upper()
        try:
            min_level = Level[level_upper]
        except KeyError:
            typer.echo(
                f"Error: unknown level {level!r}. Choose from: {', '.join(_LEVEL_NAMES)}",
                err=True,
            )
            raise typer.Exit(code=1)

    sources: list[str] = []
    if source:
        for s in source:
            # Support comma-separated values in a single --source flag
            sources.extend(part.strip() for part in s.split(",") if part.strip())

    return FilterSpec(sources=sources, min_level=min_level)


# ---------------------------------------------------------------------------
# Launch helpers
# ---------------------------------------------------------------------------


def _do_watch(
    sources: list[TailSource],
    parser_overrides: dict[str, str],
    *,
    plain: bool,
    pane_name: str,
    capacity: int,
    initial_filter: FilterSpec,
) -> None:
    """Actually start the ingest pipeline and TUI / plain stream."""
    from .buffer import ObservableBuffer
    from .ingest import IngestPipeline
    from .tailer import MultiTailer

    buffer = ObservableBuffer(capacity=capacity)
    tailer = MultiTailer(sources)
    pipeline = IngestPipeline(tailer, buffer, parser_overrides=parser_overrides)

    if plain:
        asyncio.run(_run_plain(pipeline, buffer, initial_filter))
    else:
        _run_tui(pipeline, buffer, pane_name, initial_filter)


async def _run_plain(pipeline, buffer, initial_filter: FilterSpec) -> None:
    """Stream events to stdout in plain text."""
    from .tui.renderers import render_plain_line

    task = asyncio.create_task(pipeline.run())
    try:
        while True:
            events = buffer.drain_pending()
            for event in events:
                if initial_filter.matches(event):
                    typer.echo(render_plain_line(event))
            await asyncio.sleep(0.1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def _run_tui(pipeline, buffer, pane_name: str, initial_filter: FilterSpec) -> None:
    """Launch the Textual TUI application."""
    from .tui.app import RadarApp

    tui_app = RadarApp(
        pipeline=pipeline,
        buffer=buffer,
        pane_name=pane_name,
        initial_filter=initial_filter,
    )
    tui_app.run()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@app.command()
def watch(
    files: Annotated[
        Optional[list[Path]],
        typer.Argument(
            help="Ad-hoc log files to watch (skips config/default sources). "
            "Supports shell glob expansion, e.g. .tmp/logs/*.log",
        ),
    ] = None,
    config: Annotated[
        Optional[Path],
        typer.Option(
            "--config", "-c",
            help="TOML config file with [[source]] entries. "
            "Overrides built-in defaults.",
        ),
    ] = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Plain stdout stream (no TUI). Useful for piping or agent consumption.",
        ),
    ] = False,
    level: Annotated[
        Optional[str],
        typer.Option(
            "--level", "-l",
            help=f"Minimum log level filter ({'/'.join(_LEVEL_NAMES)}). "
            "Events below this level are hidden.",
        ),
    ] = None,
    source: Annotated[
        Optional[list[str]],
        typer.Option(
            "--source", "-s",
            help="Filter by logical source ID (repeatable, comma-separated). "
            "Use source names from config, e.g. cli-driver, mcp-protocol.",
        ),
    ] = None,
    capacity: Annotated[
        int,
        typer.Option(
            "--capacity",
            help="Ring buffer capacity (max events in memory).",
            min=100,
        ),
    ] = 10_000,
    pane_name: Annotated[
        str,
        typer.Option("--pane-name", help="tmux pane title (TUI mode)."),
    ] = "radar",
) -> None:
    """Watch log files with live tail streaming.

    \b
    Modes:
      radar watch                     Default: standard supex log sources
      radar watch <files...>          Ad-hoc: watch specific files
      radar watch -c radar.toml       Config: custom source list
    \b
    Filtering:
      --level ERROR                   Show only ERROR and FATAL events
      --source cli-driver             Show only cli-driver source
      --source cli-driver,mcp-stderr  Comma-separated sources
      -s cli-driver -s mcp-stderr     Repeated --source flags
    \b
    Output:
      --plain                         Stream to stdout (no TUI)
      --capacity 50000                Increase ring buffer size
    """
    has_files = bool(files)

    if has_files and config is not None:
        typer.echo(
            "Error: cannot combine ad-hoc files with --config. "
            "Use either positional files or --config, not both.",
            err=True,
        )
        raise typer.Exit(code=1)

    if has_files:
        assert files is not None
        mode = "ad-hoc"
        typer.echo(f"[radar] ad-hoc mode: watching {len(files)} file(s)")
    elif config is not None:
        mode = "config"
        typer.echo(f"[radar] config mode: {config}")
    else:
        mode = "default"
        typer.echo("[radar] default mode: watching standard supex logs")

    initial_filter = _build_initial_filter(level, source)

    filter_parts: list[str] = []
    if initial_filter.min_level > Level.DEBUG:
        filter_parts.append(f"level>={initial_filter.min_level.name}")
    if initial_filter.sources:
        filter_parts.append(f"sources={','.join(initial_filter.sources)}")
    filter_desc = f", filter=[{' '.join(filter_parts)}]" if filter_parts else ""

    typer.echo(f"[radar] mode={mode}, plain={plain}, capacity={capacity}{filter_desc}")

    sources, parser_overrides = _resolve_sources(mode, files, config)
    _do_watch(
        sources,
        parser_overrides,
        plain=plain,
        pane_name=pane_name,
        capacity=capacity,
        initial_filter=initial_filter,
    )


@app.command()
def parse(
    file: Annotated[
        Path,
        typer.Argument(help="Log file to parse and dump"),
    ],
) -> None:
    """Parse a log file and dump structured events (smoke-test helper)."""
    if not file.exists():
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(code=1)

    # Scaffold placeholder — actual parser pipeline in later phases
    typer.echo(f"[radar] parse: {file}")


def main() -> None:
    app()
